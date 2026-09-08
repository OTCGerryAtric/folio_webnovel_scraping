"""The run loop: walk the numbers, fetch, extract, collect.

Kept apart from argument parsing so it can be driven by a stub fetcher
in the tests.
"""

from __future__ import annotations

import dataclasses

from scraper.config import Settings
from scraper.extract import Page, extract_page
from scraper.fetch import Fetcher


def build_fetcher(settings: Settings) -> Fetcher:
    return Fetcher(
        cache_dir=settings.cache_path,
        delay=settings.delay,
        max_retries=settings.max_retries,
        backoff=settings.backoff,
        refresh=settings.refresh,
        timeout=settings.timeout,
    )


def collect_pages(settings: Settings, fetcher, log=None) -> list[Page]:
    """Fetch and extract every page in the configured range.

    An open-ended run stops once `max_misses` pages in a row come back
    missing or empty. A bounded run reports gaps and carries on to the end.
    """
    report = log or (lambda message: None)
    pages: list[Page] = []
    misses = 0

    try:
        for number in settings.numbers:
            result = fetcher.fetch(settings.url_for(number), number=number)

            page = None
            if result is not None:
                page = extract_page(
                    result.html,
                    content_selector=settings.content_selector,
                    title_selector=settings.title_selector,
                    remove_selectors=settings.remove_selectors,
                )

            if page is None or page.is_empty:
                misses += 1
                reason = "not found" if result is None else "no text found"
                report(f"  {number}: {reason}")
                if settings.end is None and misses >= settings.max_misses:
                    report(
                        f"Stopping: {misses} pages in a row came back empty."
                    )
                    break
                continue

            misses = 0
            page = dataclasses.replace(page, number=number)
            pages.append(page)
            source = "cached" if result.from_cache else "fetched"
            report(f"  {number}: {page.title or 'untitled'} ({len(page.body)} chars, {source})")

    except KeyboardInterrupt:
        report(f"\nInterrupted. Keeping the {len(pages)} page(s) already collected.")

    return pages
