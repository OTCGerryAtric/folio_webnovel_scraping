"""What the library and book pages show: summaries, the chapter map,
built files, the site's latest chapter (cached), and covers."""

from __future__ import annotations

import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from scraper.book import Book, missing_numbers
from scraper.bookpage import parse_book_page
from scraper.fetch import DEFAULT_USER_AGENT
from scraper.stages import site_latest

_RANGE_RE = re.compile(r"(\d+)-(\d+)$")
_MAGIC = ((b"\xff\xd8", ".jpg"), (b"\x89PNG", ".png"), (b"GIF8", ".gif"))


def chapter_map(raw, cleaned, start: int, latest: int | None) -> list[list]:
    """Every chapter's state from `start` on, as runs of `[state, first, last]`.

    `cleaned` and `raw` are held; `missing` is a gap below the newest held;
    `new` is above it, up to the site's latest.
    """
    held, done = set(raw), set(cleaned)
    top = max([*held, latest or 0])
    newest = max(held, default=start - 1)
    runs: list[list] = []
    for number in range(start, top + 1):
        if number in held:
            state = "cleaned" if number in done else "raw"
        else:
            state = "new" if number > newest else "missing"
        if runs and runs[-1][0] == state and runs[-1][2] == number - 1:
            runs[-1][2] = number
        else:
            runs.append([state, number, number])
    return runs


def file_info(path: Path) -> dict:
    stat = path.stat()
    match = _RANGE_RE.search(path.stem)
    return {
        "name": path.name,
        "format": path.suffix.lower().lstrip("."),
        "size": stat.st_size,
        "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        "first": int(match.group(1)) if match else None,
        "last": int(match.group(2)) if match else None,
    }


class SiteCache:
    """The site's latest chapter per book, asked for at most once per `ttl` seconds."""

    def __init__(self, get_page, ttl: float = 900.0, clock=time.monotonic):
        self._get_page, self._ttl, self._clock = get_page, ttl, clock
        self._seen: dict[str, tuple[float, int | None]] = {}
        self._lock = threading.Lock()

    def peek(self, name: str) -> int | None:
        """What the last check found, without checking."""
        with self._lock:
            entry = self._seen.get(name)
        return entry[1] if entry else None

    def check(self, book: Book, settings, fresh: bool = False) -> int | None:
        with self._lock:
            entry = self._seen.get(book.name)
        if entry and not fresh and self._clock() - entry[0] < self._ttl:
            return entry[1]
        latest = site_latest(settings, self._get_page)
        with self._lock:
            self._seen[book.name] = (self._clock(), latest)
        return latest


def summary(book: Book, site: SiteCache) -> dict:
    """A book as the library shows it. A folder without settings is listed, not an error."""
    raw, cleaned = book.raw_numbers(), book.cleaned_numbers()
    data = {
        "name": book.name, "title": book.name, "author": None, "source": None,
        "ready": True, "error": None,
        "downloaded": len(raw), "cleaned": len(cleaned),
        "first": min(raw, default=None), "last": max(raw, default=None),
        "missing": 0, "latest": site.peek(book.name), "new": 0, "build_every": 0,
        "outputs": [file_info(p) for p in book.outputs()],
        "has_cover": book.cover_path is not None,
    }
    try:
        settings = book.settings()
    except ValueError as exc:
        data.update(ready=False, error=str(exc))
        return data
    data.update(
        title=settings.title or book.name,
        author=settings.author,
        source=settings.source,
        build_every=settings.build_every,
        missing=len(missing_numbers(raw, settings.start, max(raw))) if raw else 0,
    )
    if data["latest"]:
        data["new"] = max(data["latest"] - max(raw, default=settings.start - 1), 0)
    return data


def fetch_bytes(url: str) -> bytes | None:
    try:
        response = requests.get(url, timeout=20, headers={"User-Agent": DEFAULT_USER_AGENT})
    except requests.RequestException:
        return None
    return response.content if response.ok else None


def save_cover(book: Book, url: str, get_bytes) -> Path | None:
    """Fetch an image to `cover.<ext>`, the type judged by its content, not its name."""
    data = get_bytes(url) or b""
    suffix = _image_suffix(data)
    if suffix is None:
        return None
    path = book.folder / f"cover{suffix}"
    path.write_bytes(data)
    return path


def ensure_cover(book: Book, get_page, get_bytes) -> None:
    """One attempt at a cover for a book that has a source page but no cover."""
    if book.cover_path is not None:
        return
    try:
        source = book.settings().source
        html = get_page(source) if source else None
        cover = parse_book_page(html, source).cover if html else None
    except ValueError:
        return
    if cover:
        save_cover(book, cover, get_bytes)


def _image_suffix(data: bytes) -> str | None:
    for magic, suffix in _MAGIC:
        if data.startswith(magic):
            return suffix
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return None
