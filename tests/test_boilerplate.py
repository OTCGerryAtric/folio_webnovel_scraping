"""Tests for removing boilerplate after extraction.

Two mechanisms: blocks that repeat across most pages, and blocks matching
a pattern the user supplied.
"""
import pytest

from scraper.boilerplate import clean_pages
from scraper.extract import Page


def pg(number, *blocks):
    return Page(number=number, title=f"Chapter {number}", body="\n\n".join(blocks))


def bodies(pages):
    return [p.body for p in pages]


# --- repeated blocks --------------------------------------------------------


def test_a_scene_break_repeated_on_every_page_is_kept():
    pages = [
        pg(n, "Prev Chapter", f"Scene one of {n}.", "♢♢♢♢", f"Scene two of {n}.", "* * *", "---")
        for n in (1, 2, 3)
    ]

    cleaned, removals = clean_pages(pages)

    assert bodies(cleaned)[0] == "Scene one of 1.\n\n♢♢♢♢\n\nScene two of 1.\n\n* * *\n\n---"
    assert [r.text for r in removals] == ["Prev Chapter"]


def test_a_block_on_every_page_is_removed():
    pages = [pg(n, "Prev Chapter", f"The prose of chapter {n}.") for n in (1, 2, 3)]

    cleaned, _ = clean_pages(pages)

    assert bodies(cleaned) == [
        "The prose of chapter 1.",
        "The prose of chapter 2.",
        "The prose of chapter 3.",
    ]


def test_prose_unique_to_one_page_is_kept():
    pages = [pg(n, "Nav", f"Body {n}.") for n in range(1, 6)]

    cleaned, _ = clean_pages(pages)

    assert all(f"Body {i}." in cleaned[i - 1].body for i in range(1, 6))


def test_a_block_at_the_threshold_is_removed():
    # Present on 8 of 12 pages: 0.667, at or above the 0.6 default.
    pages = [pg(n, "Chrome", f"Body {n}.") for n in range(1, 9)]
    pages += [pg(n, f"Body {n}.") for n in range(9, 13)]

    cleaned, _ = clean_pages(pages)

    assert all("Chrome" not in p.body for p in cleaned)


def test_a_block_below_the_threshold_is_kept():
    # Present on 7 of 12 pages: 0.583, below the 0.6 default.
    pages = [pg(n, "Chrome", f"Body {n}.") for n in range(1, 8)]
    pages += [pg(n, f"Body {n}.") for n in range(8, 13)]

    cleaned, _ = clean_pages(pages)

    assert sum("Chrome" in p.body for p in cleaned) == 7


def test_the_threshold_is_configurable():
    pages = [pg(n, "Chrome", f"Body {n}.") for n in range(1, 8)]
    pages += [pg(n, f"Body {n}.") for n in range(8, 13)]

    cleaned, _ = clean_pages(pages, threshold=0.5)

    assert all("Chrome" not in p.body for p in cleaned)


def test_whitespace_differences_do_not_prevent_a_match():
    pages = [
        pg(1, "Prev   Chapter", "Body 1."),
        pg(2, "Prev Chapter", "Body 2."),
        pg(3, "Prev\nChapter", "Body 3."),
    ]

    cleaned, _ = clean_pages(pages)

    assert bodies(cleaned) == ["Body 1.", "Body 2.", "Body 3."]


def test_too_few_pages_to_judge_leaves_everything_alone():
    pages = [pg(1, "Shared line", "Body 1."), pg(2, "Shared line", "Body 2.")]

    cleaned, _ = clean_pages(pages)

    assert all("Shared line" in p.body for p in cleaned)


def test_deduplication_can_be_turned_off():
    pages = [pg(n, "Prev Chapter", f"Body {n}.") for n in (1, 2, 3)]

    cleaned, _ = clean_pages(pages, dedupe=False)

    assert all("Prev Chapter" in p.body for p in cleaned)


# --- reporting --------------------------------------------------------------


def test_removals_are_reported_with_a_page_count():
    pages = [pg(n, "Prev Chapter", f"Body {n}.") for n in (1, 2, 3)]

    _, removals = clean_pages(pages)

    assert len(removals) == 1
    assert removals[0].pages == 3
    assert "Prev Chapter" in removals[0].text


def test_nothing_to_remove_is_reported_as_nothing():
    pages = [pg(n, f"Body {n}.") for n in (1, 2, 3)]

    _, removals = clean_pages(pages)

    assert removals == []


def test_a_long_removed_block_is_summarised_for_display():
    noise = "Font family " + " ".join(str(i) for i in range(200))
    pages = [pg(n, noise, f"Body {n}.") for n in (1, 2, 3)]

    _, removals = clean_pages(pages)

    assert len(removals[0].text) < 200, "report lines should stay readable"


# --- patterns ---------------------------------------------------------------


def test_a_pattern_removes_the_whole_block_it_matches():
    pages = [pg(n, f"Chapter {n} - Some Title", f"Body {n}.") for n in (1, 2, 3)]

    cleaned, _ = clean_pages(pages, patterns=[r"^Chapter \d+ - "])

    assert bodies(cleaned) == ["Body 1.", "Body 2.", "Body 3."]


def test_a_pattern_matches_inside_a_multi_line_block():
    pages = [pg(n, f"Heading\nChapter {n} - Title", f"Body {n}.") for n in (1, 2, 3)]

    cleaned, _ = clean_pages(pages, patterns=[r"^Chapter \d+ - "])

    assert bodies(cleaned) == ["Body 1.", "Body 2.", "Body 3."]


def test_patterns_apply_even_when_there_are_too_few_pages_to_dedupe():
    pages = [pg(1, "Advertisement", "Body 1.")]

    cleaned, _ = clean_pages(pages, patterns=["Advertisement"])

    assert bodies(cleaned) == ["Body 1."]


def test_pattern_removals_are_reported():
    pages = [pg(n, "Advertisement", f"Body {n}.") for n in (1, 2, 3)]

    _, removals = clean_pages(pages, dedupe=False, patterns=["Advert"])

    assert len(removals) == 1
    assert removals[0].pages == 3
    assert "Advert" in removals[0].reason


def test_an_invalid_pattern_is_reported_clearly():
    with pytest.raises(ValueError, match="pattern"):
        clean_pages([pg(1, "Body.")], patterns=["[unclosed"])


# --- structure --------------------------------------------------------------


def test_page_order_and_count_are_preserved():
    pages = [pg(n, "Nav", f"Body {n}.") for n in (1, 2, 3, 4)]

    cleaned, _ = clean_pages(pages)

    assert [p.number for p in cleaned] == [1, 2, 3, 4]
    assert [p.title for p in cleaned] == [f"Chapter {n}" for n in (1, 2, 3, 4)]


def test_a_page_left_empty_is_kept_so_the_loss_is_visible():
    pages = [pg(n, "Nav") for n in (1, 2, 3)]

    cleaned, _ = clean_pages(pages)

    assert len(cleaned) == 3
    assert all(p.body == "" for p in cleaned)


def test_an_empty_input_is_handled():
    cleaned, removals = clean_pages([])

    assert cleaned == []
    assert removals == []
