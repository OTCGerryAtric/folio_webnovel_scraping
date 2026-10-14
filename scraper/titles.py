"""Tidy chapter titles taken from a page's <title>.

A scraped title arrives wrapped in the book's name and the site's:

    <Book Title> - Chapter 1 - 1 - Beast Tamer Ren Patinder | Free Web Novel

Tidying leaves the author's own chapter name whole, however long:

    Chapter 1 - Beast Tamer Ren Patinder

Pure functions. No network, no filesystem.
"""

from __future__ import annotations

import dataclasses
import re

from scraper.extract import Page

_SEPARATORS = " -–—:|"
_SITE_SUFFIX_RE = re.compile(r"\s+\|\s+[^|]*$")
_DOUBLED_NUMBER_RE = re.compile(r"^(Chapter\s+(\d+))\s*[-:]\s*\2\s*[-:]\s*", re.IGNORECASE)


def tidy_title(title: str | None, book_title: str | None = None) -> str | None:
    if not title:
        return title
    text = title.strip()

    if book_title and text.casefold().startswith(book_title.casefold()):
        rest = text[len(book_title):].lstrip(_SEPARATORS)
        if rest:
            text = rest

    text = _SITE_SUFFIX_RE.sub("", text)
    text = _DOUBLED_NUMBER_RE.sub(r"\1 - ", text)
    return text.strip() or title.strip()


def tidy_titles(pages: list[Page], book_title: str | None) -> list[Page]:
    return [dataclasses.replace(p, title=tidy_title(p.title, book_title)) for p in pages]
