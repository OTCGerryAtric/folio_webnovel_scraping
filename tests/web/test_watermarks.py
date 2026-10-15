"""Tests for the watermark studio's working parts."""
import re

import pytest

from scraper.extract import Page
from scraper.web.watermarks import review_rows, suggest_pattern
from scraper.web.watermarks import test_pattern as try_pattern

MARK = "Read more at FreeWebNovel.Com today."


def pages(n=60):
    """Chapters of 64 sentences, one of them the watermark, as in a real book."""
    filler = " ".join(f"Line {k} of the tale." for k in range(60))
    return [
        Page(number=i, title=None,
             body=f"Story {i} begins here plainly. {MARK}\n\nMore story {i} follows on. {filler}")
        for i in range(1, n + 1)
    ]


def test_rows_have_context_and_respect_ignore():
    rows = review_rows(pages(5), min_chapters=4, ignore=[])
    mark = next(r for r in rows if r["text"] == MARK)
    assert mark["chapters"] == 5
    assert len(mark["contexts"]) == 2 and MARK in mark["contexts"][0]["text"]

    rows = review_rows(pages(5), min_chapters=4, ignore=[MARK])
    assert MARK not in [r["text"] for r in rows]


def test_pattern_test_counts_and_highlights():
    result = try_pattern(pages(60), "freewebnovel")

    assert result["sentences"] == 60 and result["chapters"] == 60
    first = result["examples"][0]
    assert first["text"][first["start"]:first["end"]].lower() == "freewebnovel"


@pytest.mark.parametrize("pattern, message", [
    ("", "Enter a pattern"),
    ("(oops", "not a valid pattern"),
    ("x*", "matches empty text"),
    ("tale", "more specific"),
])
def test_bad_patterns_are_refused(pattern, message):
    with pytest.raises(ValueError, match=message):
        try_pattern(pages(60), pattern)


def test_a_fairly_broad_pattern_is_allowed_with_a_warning():
    result = try_pattern(pages(60), "story")

    assert result["sentences"] == 120 and "warning" in result and "3%" in result["warning"]
    assert "warning" not in try_pattern(pages(60), "freewebnovel")


def test_suggested_pattern_matches_however_it_is_punctuated():
    pattern = suggest_pattern(MARK)

    assert re.search(pattern, "read more at freewebnovel com today", re.IGNORECASE)
    assert not re.search(pattern, "read more today", re.IGNORECASE)
