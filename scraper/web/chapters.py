"""The reader's view of a book: its cleaned chapters, as escaped HTML paragraphs.

Reads only 02 Cleaned, so a book can be read with gaps and with nothing
built. A paragraph is a non-empty block of the chapter body - the file
after its `# title` line, split on blank lines - here, in positions and
in the browser alike.
"""

from __future__ import annotations

import hashlib

from scraper.assemble import block_html
from scraper.book import Book


def chapter_version(text: str) -> str:
    """Changes whenever a re-clean changes the chapter."""
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:12]


def split_chapter(text: str) -> tuple[str | None, list[str]]:
    first, _, rest = text.partition("\n")
    if first.startswith("# "):
        title, body = first[2:].strip() or None, rest
    else:
        title, body = None, text
    return title, [block.strip("\n") for block in body.split("\n\n") if block.strip()]


def _text(book: Book, number: int) -> str | None:
    try:
        return book.cleaned_path(number).read_text(encoding="utf-8")
    except FileNotFoundError:  # not cleaned, or gone for a moment mid re-clean
        return None


def list_chapters(book: Book) -> list[dict]:
    chapters = []
    for number in book.cleaned_numbers():
        text = _text(book, number)
        if text is None:
            continue
        title, paragraphs = split_chapter(text)
        chapters.append({"number": number, "title": title, "words": sum(len(p.split()) for p in paragraphs)})
    return chapters


def load_chapter(book: Book, number: int) -> tuple[str, list[str]] | None:
    """The chapter's version and its paragraphs as text, for finding a place in it."""
    text = _text(book, number)
    if text is None:
        return None
    return chapter_version(text), split_chapter(text)[1]


def read_chapter(book: Book, number: int) -> dict | None:
    text = _text(book, number)
    if text is None:
        return None
    title, paragraphs = split_chapter(text)
    numbers = book.cleaned_numbers()
    before = [n for n in numbers if n < number]
    after = [n for n in numbers if n > number]
    return {
        "number": number,
        "title": title,
        "version": chapter_version(text),
        "paragraphs": [block_html(p) for p in paragraphs],
        "prev": before[-1] if before else None,
        "next": after[0] if after else None,
    }
