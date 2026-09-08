"""Tests for the run loop, against a stubbed fetcher. No network."""
import pytest

from scraper.config import build_settings
from scraper.fetch import FetchResult
from scraper.run import collect_pages


class StubFetcher:
    """Serves canned HTML by page number; anything else is a miss."""

    def __init__(self, pages: dict, explode_on=None):
        self.pages = pages
        self.explode_on = explode_on
        self.asked = []

    def fetch(self, url, number):
        self.asked.append(number)
        if self.explode_on is not None and number == self.explode_on:
            raise KeyboardInterrupt
        html = self.pages.get(number)
        if html is None:
            return None
        return FetchResult(number=number, url=url, html=html, from_cache=False)


def body(text):
    return f"<html><body><div id='c'><p>{text}</p></div></body></html>"


def settings(**overrides):
    args = {"url_template": "http://example.com/{n}", "out": "b.md", "content_selector": "#c"}
    args.update(overrides)
    return build_settings(args)


# --- bounded ranges ---------------------------------------------------------


def test_a_bounded_range_collects_every_page_in_order():
    fetcher = StubFetcher({1: body("one"), 2: body("two"), 3: body("three")})

    pages = collect_pages(settings(start=1, end=3), fetcher)

    assert [p.body for p in pages] == ["one", "two", "three"]


def test_collected_pages_carry_their_number():
    fetcher = StubFetcher({5: body("five"), 6: body("six")})

    pages = collect_pages(settings(start=5, end=6), fetcher)

    assert [p.number for p in pages] == [5, 6]


def test_a_gap_in_a_bounded_range_is_skipped_not_fatal():
    fetcher = StubFetcher({1: body("one"), 3: body("three")})

    pages = collect_pages(settings(start=1, end=3), fetcher)

    assert [p.body for p in pages] == ["one", "three"]
    assert fetcher.asked == [1, 2, 3]


def test_the_step_is_honoured():
    fetcher = StubFetcher({1: body("one"), 3: body("three"), 5: body("five")})

    collect_pages(settings(start=1, end=5, step=2), fetcher)

    assert fetcher.asked == [1, 3, 5]


# --- open-ended runs --------------------------------------------------------


def test_an_open_ended_run_stops_after_consecutive_misses():
    fetcher = StubFetcher({1: body("one"), 2: body("two")})

    pages = collect_pages(settings(start=1, max_misses=3), fetcher)

    assert [p.body for p in pages] == ["one", "two"]
    assert fetcher.asked == [1, 2, 3, 4, 5]


def test_an_isolated_gap_does_not_end_an_open_ended_run():
    fetcher = StubFetcher({1: body("one"), 3: body("three")})

    pages = collect_pages(settings(start=1, max_misses=3), fetcher)

    assert [p.body for p in pages] == ["one", "three"]


def test_the_miss_streak_resets_after_a_hit():
    fetcher = StubFetcher({1: body("one"), 4: body("four")})

    pages = collect_pages(settings(start=1, max_misses=3), fetcher)

    assert [p.body for p in pages] == ["one", "four"]
    assert fetcher.asked == [1, 2, 3, 4, 5, 6, 7]


# --- empty extractions ------------------------------------------------------


def test_a_page_that_extracts_to_nothing_counts_as_a_miss():
    fetcher = StubFetcher(
        {1: body("one"), 2: "<html><body><div id='c'></div></body></html>", 3: body("three")}
    )

    pages = collect_pages(settings(start=1, end=3), fetcher)

    assert [p.body for p in pages] == ["one", "three"]


def test_a_run_that_finds_nothing_returns_nothing():
    pages = collect_pages(settings(start=1, end=3), StubFetcher({}))

    assert pages == []


# --- interruption -----------------------------------------------------------


def test_an_interrupt_keeps_what_was_already_collected():
    fetcher = StubFetcher({1: body("one"), 2: body("two")}, explode_on=3)

    pages = collect_pages(settings(start=1, end=10), fetcher)

    assert [p.body for p in pages] == ["one", "two"]


# --- reporting --------------------------------------------------------------


def test_progress_is_reported_for_each_page():
    messages = []
    fetcher = StubFetcher({1: body("one"), 2: body("two")})

    collect_pages(settings(start=1, end=2), fetcher, log=messages.append)

    assert any("1" in m for m in messages)
    assert any("2" in m for m in messages)


def test_a_bad_selector_stops_the_run_immediately():
    fetcher = StubFetcher({1: body("one")})

    with pytest.raises(ValueError, match="selector"):
        collect_pages(settings(start=1, end=3, content_selector="<<<bad>>>"), fetcher)
