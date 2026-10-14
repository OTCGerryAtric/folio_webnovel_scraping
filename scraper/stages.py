"""A book's stages: download, clean, build.

Each works on a `Book` folder. Download is the only one that touches the
network; clean and build are local, so they can be re-run freely.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from pathlib import Path

from scraper.assemble import write_document
from scraper.boilerplate import Removal, clean_pages
from scraper.book import Book
from scraper.bookpage import parse_book_page
from scraper.config import Settings
from scraper.extract import Page, extract_page
from scraper.overlap import Trim, trim_overlap
from scraper.phrases import remove_phrases
from scraper.retitle import apply_titles, load_titles
from scraper.titles import tidy_titles


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
    misses = blanks = 0
    number = settings.start

    try:
        while end is None or number <= end:
            if number not in held:
                result = fetcher.fetch(settings.url_for(number), number=number)
                if result is None or _is_blank(result.html, settings):
                    if result is not None:
                        # A "not found" page served as a normal one: not a chapter.
                        book.raw_path(number).unlink(missing_ok=True)
                        blanks += 1
                    misses += 1
                    report(f"  {number}: {'not found' if result is None else 'no text found'}")
                    if end is None and misses >= settings.max_misses:
                        report(f"Stopping: {misses} pages in a row came back empty.")
                        break
                    # Pages that arrive but hold no text, one after another, mean
                    # the content selector no longer fits the site - carrying on
                    # would fetch and throw away every page up to the end.
                    if end is not None and blanks >= settings.max_misses:
                        report(
                            f"Stopping: {blanks} pages in a row arrived with no text. "
                            f"Check content_selector in {book.config_path}."
                        )
                        break
                else:
                    misses = blanks = 0
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


# --- clean --------------------------------------------------------------------


@dataclass(frozen=True)
class CleanResult:
    pages: list[Page]
    removals: list[Removal]
    trims: list[Trim]
    retitled: int
    skipped: list[int]


def clean(book: Book, settings: Settings) -> CleanResult:
    """Rebuild the cleaned folder from the raw one.

    Works over the whole book at once, because furniture is recognised by
    repeating across chapters and a recap by matching the chapter before.
    Everything in the cleaned folder is replaced, so a change of rules
    applies everywhere and nothing stale is left for build to pick up.
    """
    pages, skipped = [], []
    for number in book.raw_numbers():
        page = extract_page(
            book.raw_path(number).read_text(encoding="utf-8"),
            content_selector=settings.content_selector,
            title_selector=settings.title_selector,
            remove_selectors=settings.remove_selectors,
        )
        if page.is_empty:
            skipped.append(number)
            continue
        pages.append(dataclasses.replace(page, number=number))

    pages, phrase_removals = remove_phrases(pages, settings.remove_phrases)
    pages, furniture = clean_pages(
        pages,
        dedupe=settings.dedupe,
        threshold=settings.dedupe_threshold,
        patterns=settings.strip_patterns,
    )
    trims = []
    if settings.trim_overlap:
        pages, trims = trim_overlap(pages, window=settings.overlap_window)
    pages = tidy_titles(pages, settings.title)
    retitled = 0
    if book.titles_path.exists():
        pages, retitled = apply_titles(pages, load_titles(book.titles_path))

    _write_cleaned(book, pages)
    return CleanResult(pages, phrase_removals + furniture, trims, retitled, skipped)


def read_cleaned(book: Book, start: int | None = None, end: int | None = None) -> list[Page]:
    """Read cleaned chapters back. The first line of each is `# <title>`."""
    pages = []
    for number in book.cleaned_numbers():
        if (start is not None and number < start) or (end is not None and number > end):
            continue
        text = book.cleaned_path(number).read_text(encoding="utf-8")
        first, _, rest = text.partition("\n")
        if first.startswith("# "):
            title, body = first[2:].strip() or None, rest
        else:
            title, body = None, text
        pages.append(Page(number=number, title=title, body=body.strip("\n")))
    return pages


def _write_cleaned(book: Book, pages: list[Page]) -> None:
    book.cleaned_dir.mkdir(parents=True, exist_ok=True)
    for old in book.cleaned_dir.glob("*.md"):
        old.unlink()
    for page in pages:
        title = page.title or f"Chapter {page.number}"
        book.cleaned_path(page.number).write_text(f"# {title}\n\n{page.body}\n", encoding="utf-8")


# --- build --------------------------------------------------------------------


def build(
    book: Book,
    settings: Settings,
    fmt: str = "epub",
    start: int | None = None,
    end: int | None = None,
) -> Path:
    """Join cleaned chapters into `03 Output/<name> <first>-<last>.<fmt>`."""
    pages = read_cleaned(book, start, end)
    if not pages:
        span = "" if start is None and end is None else f" in {start or 1}-{end or 'end'}"
        raise ValueError(f"{book.name} has no cleaned chapters{span}. Run clean first.")
    path = book.output_dir / f"{book.name} {pages[0].number}-{pages[-1].number}.{fmt.lower().lstrip('.')}"
    return write_document(pages, path, title=settings.title or book.name)
