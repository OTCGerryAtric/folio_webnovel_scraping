"""A book's folder: where its stages keep their files, and its settings.

    books/<name>/
      book.toml     settings
      01 Raw/       pages as the site sent them
      02 Cleaned/   cleaned chapters
      03 Output/    built documents

The folder name is the user's to choose; the full title lives in
`book.toml`. Stage folders are numbered so Explorer lists them in the
order the work flows.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from scraper.config import Settings, build_settings, load_site_config

BOOKS_DIR = Path("books")

CONFIG_FILE = "book.toml"
TITLES_FILE = "titles.json"
RAW_DIR = "01 Raw"
CLEANED_DIR = "02 Cleaned"
OUTPUT_DIR = "03 Output"
COVER_NAMES = ("cover.jpg", "cover.jpeg", "cover.png", "cover.webp", "cover.gif")
ACTIVITY_FILE = ".activity.jsonl"

_FORBIDDEN_RE = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
_SPACES_RE = re.compile(r"\s+")


def chapter_file(number: int, suffix: str) -> str:
    """Padded so a folder of chapters sorts correctly in Explorer."""
    return f"{number:04d}{suffix}"


def raw_file_name(number: int) -> str:
    return chapter_file(number, ".html")


def safe_folder_name(name: str) -> str:
    """Drop what Windows will not allow in a folder name."""
    name = _SPACES_RE.sub(" ", _FORBIDDEN_RE.sub("", name))
    return name.strip(" .")


def describe_ranges(numbers) -> str:
    """`[1, 2, 3, 7]` reads as `1-3, 7`."""
    numbers = sorted(numbers)
    if not numbers:
        return "none"
    spans = []
    first = last = numbers[0]
    for number in numbers[1:]:
        if number == last + 1:
            last = number
            continue
        spans.append((first, last))
        first = last = number
    spans.append((first, last))
    return ", ".join(str(a) if a == b else f"{a}-{b}" for a, b in spans)


def missing_numbers(numbers, start: int, end: int) -> list[int]:
    held = set(numbers)
    return [n for n in range(start, end + 1) if n not in held]


class Book:
    def __init__(self, folder: Path | str):
        self.folder = Path(folder)

    def __repr__(self) -> str:
        return f"Book({self.folder!r})"

    @property
    def name(self) -> str:
        return self.folder.name

    @property
    def config_path(self) -> Path:
        return self.folder / CONFIG_FILE

    @property
    def titles_path(self) -> Path:
        return self.folder / TITLES_FILE

    @property
    def raw_dir(self) -> Path:
        return self.folder / RAW_DIR

    @property
    def cleaned_dir(self) -> Path:
        return self.folder / CLEANED_DIR

    @property
    def output_dir(self) -> Path:
        return self.folder / OUTPUT_DIR

    @property
    def cover_path(self) -> Path | None:
        """The book's cover image, if it has one."""
        return next((self.folder / n for n in COVER_NAMES if (self.folder / n).is_file()), None)

    @property
    def activity_path(self) -> Path:
        """Where the web app records the jobs run on this book."""
        return self.folder / ACTIVITY_FILE

    def raw_path(self, number: int) -> Path:
        return self.raw_dir / chapter_file(number, ".html")

    def cleaned_path(self, number: int) -> Path:
        return self.cleaned_dir / chapter_file(number, ".md")

    def raw_numbers(self) -> list[int]:
        return _numbers_in(self.raw_dir, ".html")

    def cleaned_numbers(self) -> list[int]:
        return _numbers_in(self.cleaned_dir, ".md")

    def outputs(self) -> list[Path]:
        if not self.output_dir.is_dir():
            return []
        return sorted(p for p in self.output_dir.iterdir() if p.is_file())

    def has_config(self) -> bool:
        return self.config_path.exists()

    def create(self, values: dict) -> None:
        """Write `book.toml` and make the stage folders.

        A folder made by hand is fine; settings already there are not
        overwritten.
        """
        if self.has_config():
            raise ValueError(f"{self.name} already has a book.toml: {self.config_path}")
        for folder in (self.raw_dir, self.cleaned_dir, self.output_dir):
            folder.mkdir(parents=True, exist_ok=True)
        lines = [f"{key} = {_toml_value(value)}" for key, value in values.items() if value is not None]
        self.config_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def settings(self, **overrides) -> Settings:
        """This book's settings, with any non-None overrides on top.

        Pages always go to and come from the book's own raw folder.
        """
        if not self.has_config():
            raise ValueError(
                f"{self.name} has no book.toml yet. Create it with: "
                f'python scrape.py add <book page url> --name "{self.name}"'
            )
        args = {k: v for k, v in overrides.items() if v is not None}
        args["cache_dir"] = str(self.raw_dir)
        return build_settings(args, load_site_config(self.config_path), require_out=False)


def list_books(root: Path | str = BOOKS_DIR) -> list[Book]:
    root = Path(root)
    if not root.is_dir():
        return []
    return [
        Book(p) for p in sorted(root.iterdir(), key=lambda p: p.name.casefold())
        if p.is_dir() and not p.name.startswith(".")
    ]


def find_book(name: str, root: Path | str = BOOKS_DIR) -> Book:
    """Find a book by its folder name, or any unambiguous start of it, in any case."""
    books = list_books(root)
    wanted = name.casefold().strip()

    exact = [b for b in books if b.name.casefold() == wanted]
    if exact:
        return exact[0]

    matches = [b for b in books if b.name.casefold().startswith(wanted)]
    if len(matches) == 1:
        return matches[0]
    if matches:
        raise ValueError(f"{name!r} could mean: {', '.join(b.name for b in matches)}")

    known = ", ".join(b.name for b in books) or "none yet"
    raise ValueError(f"No book called {name!r}. Books: {known}")


def _numbers_in(folder: Path, suffix: str) -> list[int]:
    if not folder.is_dir():
        return []
    return sorted(int(p.stem) for p in folder.glob(f"*{suffix}") if p.stem.isdigit())


def _toml_value(value) -> str:
    """Enough TOML for a settings file. A JSON string is a valid TOML basic string."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_toml_value(v) for v in value) + "]"
    raise TypeError(f"Cannot write {value!r} to book.toml")
