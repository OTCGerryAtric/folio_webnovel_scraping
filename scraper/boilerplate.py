"""Strip site furniture from extracted pages.

Two mechanisms, both working on whole blocks:

- Repetition. A block appearing on most pages is chrome, not prose. Real
  writing is virtually never byte-identical across most of a run, whereas
  a navigation line or a reader-settings widget is identical every time.
- Patterns. For furniture that varies per page - a heading carrying the
  page number, say - repetition cannot see it, so the user supplies a
  regular expression instead.

Pure functions over a list of `Page`. No network, no filesystem.
"""

from __future__ import annotations

import dataclasses
import re
from dataclasses import dataclass

from scraper.extract import Page

DEFAULT_THRESHOLD = 0.6
DEFAULT_MIN_PAGES = 3

_SUMMARY_LENGTH = 80
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Removal:
    """One block that was dropped, and why. Reported so nothing vanishes silently."""

    text: str
    pages: int
    reason: str


def clean_pages(
    pages: list[Page],
    dedupe: bool = True,
    threshold: float = DEFAULT_THRESHOLD,
    min_pages: int = DEFAULT_MIN_PAGES,
    patterns=(),
) -> tuple[list[Page], list[Removal]]:
    """Remove boilerplate, returning the cleaned pages and what was dropped."""
    compiled = _compile(patterns)

    if not pages:
        return [], []

    removals: list[Removal] = []
    pages, pattern_removals = _strip_patterns(pages, compiled)
    removals.extend(pattern_removals)

    if dedupe and len(pages) >= min_pages:
        pages, repeat_removals = _strip_repeated(pages, threshold)
        removals.extend(repeat_removals)

    removals.sort(key=lambda r: r.pages, reverse=True)
    return pages, removals


# --- patterns ---------------------------------------------------------------


def _compile(patterns) -> list:
    compiled = []
    for pattern in patterns or ():
        try:
            compiled.append(re.compile(pattern, re.MULTILINE))
        except re.error as exc:
            raise ValueError(f"Invalid strip pattern {pattern!r}: {exc}") from exc
    return compiled


def _strip_patterns(pages: list[Page], compiled: list) -> tuple[list[Page], list[Removal]]:
    if not compiled:
        return pages, []

    hits = {pattern.pattern: 0 for pattern in compiled}
    cleaned = []

    for page in pages:
        kept, matched = [], set()
        for block in _blocks(page):
            hit = next((p for p in compiled if p.search(block)), None)
            if hit is None:
                kept.append(block)
            else:
                matched.add(hit.pattern)
        for pattern in matched:
            hits[pattern] += 1
        cleaned.append(_rebuild(page, kept))

    removals = [
        Removal(text=f"pattern {pattern}", pages=count, reason=f"matched pattern {pattern!r}")
        for pattern, count in hits.items()
        if count
    ]
    return cleaned, removals


# --- repetition -------------------------------------------------------------


def _strip_repeated(pages: list[Page], threshold: float) -> tuple[list[Page], list[Removal]]:
    counts: dict[str, int] = {}
    originals: dict[str, str] = {}

    for page in pages:
        for key, block in {_key(b): b for b in _blocks(page)}.items():
            counts[key] = counts.get(key, 0) + 1
            originals.setdefault(key, block)

    threshold_count = threshold * len(pages)
    repeated = {
        key for key, count in counts.items()
        if count >= threshold_count and not _is_scene_break(key)
    }
    if not repeated:
        return pages, []

    cleaned = [
        _rebuild(page, [b for b in _blocks(page) if _key(b) not in repeated])
        for page in pages
    ]
    removals = [
        Removal(text=_summarise(originals[key]), pages=counts[key], reason="repeated")
        for key in repeated
    ]
    return cleaned, removals


# --- helpers ----------------------------------------------------------------


def _blocks(page: Page) -> list[str]:
    return [b for b in page.body.split("\n\n") if b.strip()]


def _rebuild(page: Page, blocks: list[str]) -> Page:
    return dataclasses.replace(page, body="\n\n".join(blocks))


def _is_scene_break(block: str) -> bool:
    """A divider such as `* * *` or `♢♢♢♢` repeats on most pages, but it is
    part of the story's structure. Site furniture always has words in it."""
    return not any(character.isalnum() for character in block)


def _key(block: str) -> str:
    """Compare on collapsed whitespace, so trivial layout differences match."""
    return _WHITESPACE_RE.sub(" ", block).strip()


def _summarise(block: str) -> str:
    """Keep report lines readable however long the removed block was.

    Deliberately ASCII: this goes to the console, and a Windows terminal in
    a legacy code page raises on characters it cannot encode.
    """
    text = _key(block)
    if len(text) <= _SUMMARY_LENGTH:
        return text
    return text[: _SUMMARY_LENGTH - 3].rstrip() + "..."
