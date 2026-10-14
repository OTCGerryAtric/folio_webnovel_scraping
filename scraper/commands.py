"""The book subcommands: `python scrape.py <command> <book> ...`.

Parsing and reporting live here; the work itself is in `stages`.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scraper.book import (
    BOOKS_DIR,
    Book,
    describe_ranges,
    find_book,
    list_books,
    missing_numbers,
    raw_file_name,
    safe_folder_name,
)
from scraper.bookpage import parse_book_page, site_phrase
from scraper.fetch import fetch_page
from scraper.run import build_fetcher

COMMANDS = ("add", "books", "status", "download", "clean", "review", "build", "update")


def book_fetcher(settings):
    return build_fetcher(settings, file_name=raw_file_name)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scrape.py",
        description="Work with the books kept in the books folder.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="create a book from its page on the source site")
    add.add_argument("page_url", nargs="?", help="the book's main page")
    add.add_argument("--name", help="folder name (default: the book's title)")
    add.add_argument("--url", dest="url_template", help="chapter URL with {n}, for sites without book details")
    add.add_argument("--title", help="the book's title, when adding with --url")

    sub.add_parser("books", help="list the books")

    status = sub.add_parser("status", help="what is downloaded, cleaned and built")
    status.add_argument("book")
    status.add_argument("--offline", action="store_true", help="do not check the site")

    return parser


def run_command(
    argv: list[str],
    fetcher_factory=book_fetcher,
    get_page=fetch_page,
    root: Path | str = BOOKS_DIR,
    report=None,
) -> int:
    report = report or (lambda message: print(message, file=sys.stderr))
    args = build_parser().parse_args(argv)
    root = Path(root)
    handler = _HANDLERS[args.command]
    try:
        return handler(args, root=root, fetcher_factory=fetcher_factory, get_page=get_page, report=report)
    except ValueError as exc:
        report(f"error: {exc}")
        return 2


# --- add ----------------------------------------------------------------------


def _add(args, root, get_page, report, **_):
    if args.url_template:
        title = args.title or args.name
        if not title:
            raise ValueError("Adding with --url needs --title (or --name).")
        values = {"title": title, "url_template": args.url_template}
        summary = title
    elif args.page_url:
        html = get_page(args.page_url)
        if html is None:
            raise ValueError(f"Could not fetch {args.page_url}")
        info = parse_book_page(html, args.page_url)
        title = info.title
        values = {
            "title": info.title,
            "author": info.author,
            "source": args.page_url,
            "url_template": info.url_template,
            "remove_phrases": [site_phrase(args.page_url)],
        }
        by = f", by {info.author}" if info.author else ""
        state = f" ({info.status})" if info.status else ""
        summary = f"{info.title}{by}{state}"
        if info.latest:
            updated = f", last updated {info.updated}" if info.updated else ""
            summary += f"\n  {info.latest} chapters on the site{updated}"
    else:
        raise ValueError("Give the book page URL, or --url with a {n} template and --title.")

    folder = safe_folder_name(args.name or title)
    if not folder:
        raise ValueError(f"Cannot make a folder name from {args.name or title!r}. Pass --name.")
    book = Book(root / folder)
    book.create(values)

    report(f"Added {book.name}")
    report(f"  {summary}")
    report(f"  {book.config_path}")
    report(f'Next: python scrape.py download "{book.name}"')
    return 0


# --- books and status ---------------------------------------------------------


def _books(args, root, report, **_):
    books = list_books(root)
    if not books:
        report("No books yet. Add one with: python scrape.py add <book page url>")
        return 0
    for book in books:
        raw, cleaned = book.raw_numbers(), book.cleaned_numbers()
        report(f"{book.name}: downloaded {describe_ranges(raw)}, cleaned {len(cleaned)} chapter(s)")
    return 0


def _status(args, root, get_page, report, **_):
    from scraper.stages import site_latest

    book = find_book(args.book, root)
    settings = book.settings()
    raw, cleaned = book.raw_numbers(), book.cleaned_numbers()

    latest = None if args.offline else site_latest(settings, get_page)
    last_known = max([*raw, latest or 0])

    report(book.name)
    if settings.title or settings.author:
        by = f", by {settings.author}" if settings.author else ""
        report(f"  {settings.title or book.name}{by}")
    report(f"  downloaded  {describe_ranges(raw)}")
    missing = missing_numbers(raw, settings.start, last_known) if last_known else []
    if missing:
        report(f"  missing     {describe_ranges(missing)}")
    report(f"  cleaned     {describe_ranges(cleaned)}")
    outputs = book.outputs()
    report(f"  built       {', '.join(p.name for p in outputs) if outputs else 'nothing yet'}")

    if args.offline:
        report("  site        not checked (--offline)")
    elif not settings.source:
        report("  site        not checked: book.toml has no source page")
    elif latest is None:
        report("  site        could not be reached, or lists no latest chapter")
    else:
        new = len([n for n in missing_numbers(raw, settings.start, latest) if n > max(raw, default=0)])
        report(f"  site        latest {latest}, {new} new")
    return 0


_HANDLERS = {
    "add": _add,
    "books": _books,
    "status": _status,
}
