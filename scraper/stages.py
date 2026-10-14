"""A book's stages: download, clean, build.

Each works on a `Book` folder. Download is the only one that touches the
network; clean and build are local, so they can be re-run freely.
"""

from __future__ import annotations

from scraper.book import Book
from scraper.bookpage import parse_book_page
from scraper.config import Settings
from scraper.extract import extract_page


# --- download -----------------------------------------------------------------


def download(book: Book, settings: Settings, fetcher, latest: int | None = None, log=None) -> list[int]:
    """Fetch the chapters not yet in the raw folder. Returns the numbers fetched.

    With an end (`--end`, or the site's latest chapter) every number up to it
    is tried and gaps are skipped. Without one, the run stops after
    `max_misses` misses in a row.
    """
    report = log or (lambda message: None)
    held = set() if settings.refresh else set(book.raw_numbers())
    end = settings.end if settings.end is not None else latest
    fetched: list[int] = []
    misses = 0
    number = settings.start

    try:
        while end is None or number <= end:
            if number not in held:
                result = fetcher.fetch(settings.url_for(number), number=number)
                if result is None or _is_blank(result.html, settings):
                    if result is not None:
                        # A "not found" page served as a normal one: not a chapter.
                        book.raw_path(number).unlink(missing_ok=True)
                    misses += 1
                    report(f"  {number}: {'not found' if result is None else 'no text found'}")
                    if end is None and misses >= settings.max_misses:
                        report(f"Stopping: {misses} pages in a row came back empty.")
                        break
                else:
                    misses = 0
                    fetched.append(number)
                    report(f"  {number}{f'/{end}' if end else ''}: downloaded")
            number += settings.step
    except KeyboardInterrupt:
        report(f"\nInterrupted. Keeping the {len(fetched)} chapter(s) already downloaded.")

    return fetched


def site_latest(settings: Settings, get_page) -> int | None:
    """The newest chapter the site lists, or None if that cannot be found out."""
    if not settings.source:
        return None
    html = get_page(settings.source)
    if html is None:
        return None
    try:
        return parse_book_page(html, settings.source).latest
    except ValueError:
        return None


def _is_blank(html: str, settings: Settings) -> bool:
    return extract_page(
        html,
        content_selector=settings.content_selector,
        title_selector=settings.title_selector,
        remove_selectors=settings.remove_selectors,
    ).is_empty
