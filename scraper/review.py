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
    key: str = ""


def repeated_sentences(
    pages: list[Page], min_chapters: int = 4, limit: int = 60, ignore=()
) -> list[Repeat]:
    """Sentences found in at least `min_chapters` chapters, most common first.

    Sentences in `ignore` - the author's own habits, once someone has said
    so - are left out, however they are punctuated or capitalised.
    """
    skip = {normalise(text) for text in ignore}
    counts: Counter = Counter()
    first_seen: dict[str, tuple[str, int | None]] = {}

    for page in pages:
        keys = set()
        for block in page.body.split("\n\n"):
            for sentence in split_sentences(block):
                key = normalise(sentence)
                if len(key) < _MIN_LENGTH or key in skip:
                    continue
                keys.add(key)
                first_seen.setdefault(key, (sentence.strip(), page.number))
        counts.update(keys)

    repeats = [
        Repeat(text=first_seen[key][0], chapters=count, first=first_seen[key][1], key=key)
        for key, count in counts.most_common()
        if count >= min_chapters
    ]
    return repeats[:limit]


def split_sentences(block: str) -> list[str]:
    return _SPLIT_RE.split(block)


def normalise(text: str) -> str:
    """Lower case, punctuation as spaces: the form sentences are compared in."""
    text = text.translate(_TYPOGRAPHIC).lower()
    return _WHITESPACE_RE.sub(" ", _NOT_PLAIN_RE.sub(" ", text)).strip()
