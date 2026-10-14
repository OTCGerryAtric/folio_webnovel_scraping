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
from scraper.reporting import report_removals, report_trims, warn_if_emptied
from scraper.review import repeated_sentences
from scraper.run import build_fetcher
from scraper.stages import build, clean, download, read_cleaned, site_latest

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

    down = sub.add_parser("download", help="fetch the chapters not yet downloaded")
    down.add_argument("book")
    down.add_argument("--start", type=int, help="first chapter (default: from book.toml, else 1)")
    down.add_argument("--end", type=int, help="last chapter (default: the site's latest)")
    down.add_argument("--refresh", action="store_true", default=None, help="fetch held chapters again")

    cleaner = sub.add_parser("clean", help="rebuild the cleaned chapters from the raw pages")
    cleaner.add_argument("book")
    cleaner.add_argument("--no-dedupe", dest="dedupe", action="store_false", default=None,
                         help="keep blocks that repeat across chapters")

    review = sub.add_parser("review", help="list sentences repeated across chapters")
    review.add_argument("book")
    review.add_argument("--min-chapters", type=int, default=4,
                        help="how many chapters a sentence must appear in (default 4)")

    builder = sub.add_parser("build", help="join the cleaned chapters into one file")
    builder.add_argument("book")
    builder.add_argument("--format", default="epub", help="epub, pdf, md or txt (default epub)")
    builder.add_argument("--from", dest="start", type=int, help="first chapter")
    builder.add_argument("--to", dest="end", type=int, help="last chapter")

    update = sub.add_parser("update", help="download what is new, clean, and build the new chapters")
    update.add_argument("book")
    update.add_argument("--format", default="epub", help="epub, pdf, md or txt (default epub)")

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
    except (ValueError, OSError) as exc:
        # OSError: on Windows, an epub open in a reader cannot be replaced.
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
        phrase = site_phrase(args.page_url)
        values = {
            "title": info.title,
            "author": info.author,
            "source": args.page_url,
            "url_template": info.url_template,
            "remove_phrases": [phrase] if phrase else None,
        }
        by = f", by {info.author}" if info.author else ""
        state = f" ({info.status})" if info.status else ""
        summary = f"{info.title}{by}{state}"
        if info.latest:
            updated = f", last updated {info.updated}" if info.updated else ""
            summary += f"\n  {info.latest} chapters on the site{updated}"
        summary += f"\n  chapters at {info.url_template}"
        if phrase:
            summary += "\n  sentences naming the site will be removed (remove_phrases in book.toml)"
        else:
            summary += "\n  the site's name is too short to remove safely; add remove_phrases by hand"
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


# --- the stages ---------------------------------------------------------------


def _download(args, root, fetcher_factory, get_page, report, **_):
    book = find_book(args.book, root)
    settings = book.settings(start=args.start, end=args.end, refresh=args.refresh)
    fetched = _fetch_new(book, settings, fetcher_factory, get_page, report)
    report(f"Downloaded {len(fetched)} chapter(s). Held: {describe_ranges(book.raw_numbers())}")
    return 0


def _clean(args, root, report, **_):
    book = find_book(args.book, root)
    _run_clean(book, book.settings(dedupe=args.dedupe), report)
    return 0


def _review(args, root, report, **_):
    book = find_book(args.book, root)
    pages = read_cleaned(book)
    if not pages:
        raise ValueError(f"{book.name} has no cleaned chapters. Run clean first.")
    repeats = repeated_sentences(pages, min_chapters=args.min_chapters)
    if not repeats:
        report(f"No sentence appears in {args.min_chapters} or more chapters.")
        return 0
    report(f"Sentences in {args.min_chapters}+ of {len(pages)} chapters (first chapter in brackets):")
    for repeat in repeats:
        report(f"  {repeat.chapters:5}  {repeat.text}  [{repeat.first}]")
    report("Anything here that is not the story can go in remove_phrases in book.toml.")
    return 0


def _build(args, root, report, **_):
    book = find_book(args.book, root)
    path = build(book, book.settings(), fmt=args.format, start=args.start, end=args.end)
    count = len(read_cleaned(book, args.start, args.end))
    report(f"Wrote {count} chapter(s) to {path}")
    return 0


def _update(args, root, fetcher_factory, get_page, report, **_):
    book = find_book(args.book, root)
    settings = book.settings()
    fetched = _fetch_new(book, settings, fetcher_factory, get_page, report)
    if not fetched:
        report(f"Up to date: no new chapters. Held: {describe_ranges(book.raw_numbers())}")
        return 0
    _run_clean(book, settings, report)
    path = build(book, settings, fmt=args.format, start=min(fetched), end=max(fetched))
    report(f"Wrote {len(fetched)} new chapter(s) to {path}")
    return 0


def _fetch_new(book, settings, fetcher_factory, get_page, report) -> list[int]:
    latest = None
    if settings.end is None:
        latest = site_latest(settings, get_page)
        if latest:
            report(f"The site lists {latest} chapters.")
    return download(book, settings, fetcher_factory(settings), latest=latest, log=report)


def _run_clean(book, settings, report) -> None:
    result = clean(book, settings)
    if result.skipped:
        report(f"Skipped {len(result.skipped)} raw page(s) with no text: {describe_ranges(result.skipped)}")
    report_removals(result.removals, len(result.pages), report)
    report_trims(result.trims, report)
    if result.retitled:
        report(f"Titles: {result.retitled} chapter(s) took a title from titles.json.")
    warn_if_emptied(result.pages, report)
    report(f"Cleaned {len(result.pages)} chapter(s) into {book.cleaned_dir}")


_HANDLERS = {
    "add": _add,
    "books": _books,
    "status": _status,
    "download": _download,
    "clean": _clean,
    "review": _review,
    "build": _build,
    "update": _update,
}
