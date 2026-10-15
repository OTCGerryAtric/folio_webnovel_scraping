"""Read a book's details from its main page on the source site.

Many novel sites publish them as `og:novel:*` meta tags: the name, the
author, where chapter 1 is, and the latest chapter. (The site spells it
`lastest_chapter_url`; the correct spelling is accepted too.)

Pure functions of HTML text. No network, no filesystem.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from scraper.config import PLACEHOLDER

_LAST_NUMBER_RE = re.compile(r"\d+(?!.*\d)")

# Shorter site names match too much ordinary text to remove sentences safely.
_MIN_SITE_NAME = 5


@dataclass(frozen=True)
class BookInfo:
    title: str
    author: str | None
    url_template: str
    latest: int | None
    status: str | None
    updated: str | None
    cover: str | None = None


def parse_book_page(html: str, page_url: str) -> BookInfo:
    soup = BeautifulSoup(html, "lxml")

    def meta(key: str) -> str | None:
        tag = soup.find("meta", attrs={"property": f"og:novel:{key}"})
        value = (tag.get("content") or "").strip() if tag else ""
        return value or None

    title, read_url = meta("novel_name"), meta("read_url")
    if not title or not read_url:
        raise ValueError(
            f"{page_url} does not list the book's details, so it cannot be "
            f"added from its page. Add it with --url (a chapter URL with {{n}} "
            f"for the number) and --title instead."
        )

    image = soup.find("meta", attrs={"property": "og:image"})
    cover = (image.get("content") or "").strip() if image else ""

    return BookInfo(
        title=title,
        author=meta("author"),
        url_template=template_from_chapter_url(urljoin(page_url, read_url)),
        latest=chapter_from_url(meta("lastest_chapter_url") or meta("latest_chapter_url")),
        status=meta("status"),
        updated=meta("update_time"),
        cover=urljoin(page_url, cover) if cover else None,
    )


def template_from_chapter_url(url: str) -> str:
    """`.../chapter-1` becomes `.../chapter-{n}`: the last number is the chapter."""
    if not _LAST_NUMBER_RE.search(url):
        raise ValueError(f"No chapter number in {url!r}")
    return _LAST_NUMBER_RE.sub(PLACEHOLDER, url, count=1)


def chapter_from_url(url: str | None) -> int | None:
    match = _LAST_NUMBER_RE.search(url or "")
    return int(match.group()) if match else None


def site_phrase(url: str) -> str | None:
    """A pattern for the site's own name, however the watermark spaces it.

    `freewebnovel.com` gives a pattern matching "freewebnovel", "Free Web
    Novel" and "freewebnovel.com" alike. The name is the label before the
    domain ending, so `m.` or `s2.` subdomains are ignored. A name too short
    to be safe gives None: a pattern for "ab" would match ordinary words.
    """
    labels = (urlparse(url).hostname or "").split(".")
    name = labels[-2] if len(labels) >= 2 else labels[0]
    letters = [c for c in name if c.isalnum()]
    if len(letters) < _MIN_SITE_NAME:
        return None
    return r"[\W_]*".join(re.escape(c) for c in letters)
