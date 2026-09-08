"""Walk a numbered URL series, extract the text, join it into one document.

    python scrape.py --url "https://example.com/page-{n}" --start 1 --end 50 --out book.md

The tool is source-agnostic: it knows nothing about any particular site,
and every site-specific detail is yours to supply. Point it only at
material you have the right to copy.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from scraper.assemble import SUPPORTED_FORMATS, write_document
from scraper.boilerplate import clean_pages
from scraper.config import build_settings, load_site_config
from scraper.run import build_fetcher, collect_pages

EXAMPLES = """
examples (PowerShell):

  # fifty numbered pages into one Markdown file
  python scrape.py --url "https://example.com/page-{n}" --start 1 --end 50 --out book.md

  # keep going until the pages run out, using an explicit content selector
  python scrape.py --url "https://example.com/part-{n}" --selector "div.entry" --out book.epub

  # reuse a saved source
  python scrape.py --site sites/example.toml --out book.txt

The output format follows the extension: .md, .txt or .epub.
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="scrape.py",
        description=__doc__,
        epilog=EXAMPLES,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        "--url", dest="url_template",
        help="URL with an {n} placeholder for the number that changes",
    )
    parser.add_argument("--out", help="output file; the extension picks the format")
    parser.add_argument("--site", help="TOML file holding settings for a source")

    parser.add_argument("--start", type=int, help="first number (default 1)")
    parser.add_argument(
        "--end", type=int,
        help="last number; omit to keep going until the pages run out",
    )
    parser.add_argument("--step", type=int, help="increment between numbers (default 1)")

    parser.add_argument(
        "--selector", dest="content_selector",
        help="CSS selector for the main text; omit to detect it automatically",
    )
    parser.add_argument(
        "--title-selector", dest="title_selector",
        help="CSS selector for each page's title",
    )
    parser.add_argument(
        "--remove", dest="remove_selectors", action="append", metavar="CSS",
        help="CSS selector to strip before extracting; repeatable",
    )

    parser.add_argument(
        "--no-dedupe", dest="dedupe", action="store_false", default=None,
        help="keep blocks that repeat across pages, instead of stripping them",
    )
    parser.add_argument(
        "--dedupe-threshold", dest="dedupe_threshold", type=float, metavar="FRACTION",
        help="fraction of pages a block must appear on to count as boilerplate"
             " (default 0.6)",
    )
    parser.add_argument(
        "--strip-regex", dest="strip_patterns", action="append", metavar="REGEX",
        help="drop any block matching this pattern; repeatable",
    )

    parser.add_argument("--title", help="title for the finished document")
    parser.add_argument(
        "--delay", type=float, help="seconds to wait between requests (default 1.5)",
    )
    parser.add_argument(
        "--max-misses", dest="max_misses", type=int,
        help="consecutive empty pages that end an open-ended run (default 3)",
    )
    parser.add_argument(
        "--max-retries", dest="max_retries", type=int,
        help="attempts per page before giving up on it (default 3)",
    )
    parser.add_argument("--timeout", type=float, help="per-request timeout in seconds")
    parser.add_argument("--cache-dir", dest="cache_dir", help="where to keep fetched pages")
    parser.add_argument(
        "--refresh", action="store_true", default=None,
        help="ignore the cache and fetch every page again",
    )
    parser.add_argument(
        "--verbose", action="store_true", default=None, help="report each URL as it is fetched",
    )

    return parser


def parse_args(argv: list[str] | None = None) -> dict:
    """Parse arguments into a plain dict, leaving unset options as None.

    Unset means None rather than a default so that a site file can supply
    the value; defaults are applied later, in `build_settings`.
    """
    return vars(build_parser().parse_args(argv))


def main(argv: list[str] | None = None, fetcher_factory=build_fetcher) -> int:
    args = parse_args(argv)
    site = args.pop("site", None)

    def report(message: str) -> None:
        print(message, file=sys.stderr)

    try:
        config = load_site_config(site) if site else {}
        settings = build_settings(args, config)
        _check_output_format(settings.out)
    except ValueError as exc:
        report(f"error: {exc}")
        return 2

    report(f"Reading {settings.url_for(settings.start)} onwards")
    report(f"Cache: {settings.cache_path}")

    pages = collect_pages(settings, fetcher_factory(settings), log=report)

    if not pages:
        report("error: no pages were collected, so nothing was written.")
        return 1

    collected = len(pages)
    pages, removals = clean_pages(
        pages,
        dedupe=settings.dedupe,
        threshold=settings.dedupe_threshold,
        patterns=settings.strip_patterns,
    )
    _report_removals(removals, collected, report)
    _warn_if_emptied(pages, report)

    try:
        written = write_document(pages, settings.out, title=settings.title)
    except (ValueError, OSError) as exc:
        report(f"error: could not write {settings.out}: {exc}")
        return 2

    report(f"Wrote {len(pages)} page(s) to {written}")
    return 0


def _report_removals(removals, total: int, report) -> None:
    """Say what was stripped. Text disappearing silently is how trust goes."""
    if not removals:
        return
    report(f"Removed {len(removals)} boilerplate block(s):")
    for removal in removals:
        report(f"  on {removal.pages}/{total} pages: {removal.text}")


def _warn_if_emptied(pages, report) -> None:
    """An emptied page means the threshold was too aggressive. Say so."""
    emptied = [p.number for p in pages if p.is_empty]
    if emptied:
        report(
            f"warning: {len(emptied)} page(s) were left with no text "
            f"(first: {emptied[0]}). Try --dedupe-threshold with a higher "
            f"value, or --no-dedupe. Re-running costs nothing: the pages "
            f"are cached."
        )


def _check_output_format(out: str) -> None:
    """Fail before fetching anything, not after."""
    suffix = Path(out).suffix.lower()
    if suffix not in SUPPORTED_FORMATS:
        raise ValueError(
            f"Unsupported output format {suffix or out!r}. "
            f"Use one of: {', '.join(sorted(SUPPORTED_FORMATS))}"
        )


if __name__ == "__main__":
    raise SystemExit(main())
