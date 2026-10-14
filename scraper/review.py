"""Find sentences that recur across many chapters.

Repetition alone cannot tell junk from an author's habits - "Ren shook his
head." recurs in 18 chapters of one book - so this is a report for the
user to read, not something that removes text. Anything unwanted goes into
the book's `remove_phrases`.

Pure functions over a list of `Page`. No network, no filesystem.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass

from scraper.extract import Page

# Shorter than this and a sentence recurs in any book by chance.
_MIN_LENGTH = 15

# Sentence ends as `phrases` sees them, so the report and the removal agree.
_SPLIT_RE = re.compile(r'(?<=[.!?"”’…*_)\]])\s+')
_NOT_PLAIN_RE = re.compile(r"[^a-z0-9 ]+")
_WHITESPACE_RE = re.compile(r"\s+")
_TYPOGRAPHIC = str.maketrans({
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "…": "...", "–": "-", "—": "-",
})


@dataclass(frozen=True)
class Repeat:
    text: str
    chapters: int
    first: int | None


def repeated_sentences(pages: list[Page], min_chapters: int = 4, limit: int = 60) -> list[Repeat]:
    counts: Counter = Counter()
    first_seen: dict[str, tuple[str, int | None]] = {}

    for page in pages:
        keys = set()
        for block in page.body.split("\n\n"):
            for sentence in _SPLIT_RE.split(block):
                key = _normalise(sentence)
                if len(key) < _MIN_LENGTH:
                    continue
                keys.add(key)
                first_seen.setdefault(key, (sentence.strip(), page.number))
        counts.update(keys)

    repeats = [
        Repeat(text=_console_safe(first_seen[key][0]), chapters=count, first=first_seen[key][1])
        for key, count in counts.most_common()
        if count >= min_chapters
    ]
    return repeats[:limit]


def _normalise(text: str) -> str:
    return _WHITESPACE_RE.sub(" ", _NOT_PLAIN_RE.sub(" ", text.lower())).strip()


def _console_safe(text: str) -> str:
    """Typographic punctuation to ASCII; anything else unprintable becomes '?'."""
    return text.translate(_TYPOGRAPHIC).encode("ascii", "replace").decode("ascii")
