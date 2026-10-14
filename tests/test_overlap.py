"""Tests for trimming the recap a new page opens with.

Serialised sources often restate the end of the previous instalment before
getting on with the new one. The restatement is rarely byte-identical: it
gets reworded and re-paragraphed, so this works on sentences, not blocks.
"""
import pytest

from scraper.extract import Page
from scraper.overlap import trim_overlap


def pg(number, *blocks):
    return Page(number=number, title=f"Chapter {number}", body="\n\n".join(blocks))


def bodies(pages):
    return [p.body for p in pages]


def joined(*blocks):
    return "\n\n".join(blocks)


# Long enough to clear the minimum-length guard, and distinct enough that
# nothing matches by accident.
A = "The path home had never felt so long that evening."
B = "His parents had sold everything they owned for this one moment."
C = "The contract bond established itself with a flash so weak it barely lit his wrist."
D = "Cobblestone streets gave way to dirt roads as he walked out of the city."


# --- the basic trim ---------------------------------------------------------


def test_an_identical_repeat_at_the_start_of_a_page_is_removed():
    pages = [pg(1, C, A), pg(2, A, D)]

    trimmed, _ = trim_overlap(pages)

    assert bodies(trimmed) == [f"{C}\n\n{A}", D]


def test_a_reworded_and_resplit_repeat_is_removed():
    # The real shape, taken from a scraped run: the recap merges two of the
    # previous page's paragraphs into one and drops a word along the way.
    previous = pg(
        1,
        "Ren kept his head high as he descended from the altar. His parents had "
        "sold everything for this moment. They had worked double shifts.",
        "He wouldn't give these brats the pleasure of seeing him cry.",
    )
    current = pg(
        2,
        "Ren kept his head high as he descended from the altar.",
        "His parents had sold everything for this moment. Had worked double "
        "shifts. He wouldn't give these brats the pleasure of seeing him cry.",
        C,
    )

    trimmed, _ = trim_overlap([previous, current])

    assert trimmed[1].body == C


def test_the_trim_stops_at_the_first_block_that_is_not_a_repeat():
    # B repeats too, but D interrupts the run, so B has to stay.
    pages = [pg(1, A, B), pg(2, A, D, B)]

    trimmed, _ = trim_overlap(pages)

    assert trimmed[1].body == f"{D}\n\n{B}"


def test_prose_that_does_not_repeat_is_left_alone():
    pages = [pg(1, A, B), pg(2, C, D)]

    trimmed, _ = trim_overlap(pages)

    assert bodies(trimmed) == bodies(pages)


def test_the_first_page_is_never_trimmed():
    # Contrived, but a page cannot recap something that came before it.
    pages = [pg(1, A, B), pg(2, C)]

    trimmed, _ = trim_overlap(pages)

    assert trimmed[0].body == f"{A}\n\n{B}"


def test_titles_and_numbers_survive_the_trim():
    pages = [pg(1, C, A), pg(2, A, D)]

    trimmed, _ = trim_overlap(pages)

    assert [p.number for p in trimmed] == [1, 2]
    assert [p.title for p in trimmed] == ["Chapter 1", "Chapter 2"]


def test_an_empty_run_is_handled():
    assert trim_overlap([]) == ([], [])


# --- guards against taking too much -----------------------------------------


def test_a_page_is_never_left_empty():
    # Every block repeats. Trimming them all would delete the page, so the
    # page is left alone for the reader to judge.
    pages = [pg(1, A, B), pg(2, A, B)]

    trimmed, _ = trim_overlap(pages)

    assert trimmed[1].body == f"{A}\n\n{B}"


def test_a_block_is_only_trimmed_when_all_of_it_repeats():
    mixed = f"{A} {C}"
    pages = [pg(1, B, A), pg(2, mixed, D)]

    trimmed, _ = trim_overlap(pages)

    assert trimmed[1].body == f"{mixed}\n\n{D}"


def test_a_short_line_is_too_weak_to_trigger_a_trim():
    pages = [pg(1, C, "He nodded."), pg(2, "He nodded.", D)]

    trimmed, _ = trim_overlap(pages)

    assert trimmed[1].body == f"He nodded.\n\n{D}"


def test_a_short_line_riding_along_with_real_prose_still_goes():
    pages = [pg(1, C, f"{A} He nodded."), pg(2, f"{A} He nodded.", D)]

    trimmed, _ = trim_overlap(pages)

    assert trimmed[1].body == D


def test_a_repeat_from_deep_in_the_previous_page_is_not_matched():
    # Only the tail of the previous page counts as a recap source. Further
    # back, a match is more likely to be a coincidence than a restatement.
    filler = [f"Filler paragraph number {i} of the previous chapter." for i in range(20)]
    pages = [pg(1, A, *filler), pg(2, A, D)]

    trimmed, _ = trim_overlap(pages)

    assert trimmed[1].body == f"{A}\n\n{D}"


def test_the_window_can_be_widened():
    filler = [f"Filler paragraph number {i} of the previous chapter." for i in range(20)]
    pages = [pg(1, A, *filler), pg(2, A, D)]

    trimmed, _ = trim_overlap(pages, window=25)

    assert trimmed[1].body == D


def test_a_loose_paraphrase_is_not_close_enough():
    pages = [
        pg(1, C, "The walk back to the house felt endless that particular evening."),
        pg(2, A, D),
    ]

    trimmed, _ = trim_overlap(pages)

    assert trimmed[1].body == f"{A}\n\n{D}"


# --- headings ---------------------------------------------------------------


def test_a_heading_does_not_hide_the_recap_behind_it():
    # A chapter title inside the content selector is structure, not prose,
    # so the walk steps over it rather than stopping there.
    pages = [pg(1, C, A), pg(2, "## Chapter Two", A, D)]

    trimmed, _ = trim_overlap(pages)

    assert trimmed[1].body == joined("## Chapter Two", D)


def test_a_heading_is_kept_when_everything_after_it_repeats():
    pages = [pg(1, C, A, B), pg(2, "## Chapter Two", A, B)]

    trimmed, _ = trim_overlap(pages)

    assert trimmed[1].body == joined("## Chapter Two", A, B)


def test_a_heading_is_not_counted_as_a_trimmed_block():
    pages = [pg(1, C, A), pg(2, "## Chapter Two", A, D)]

    _, trims = trim_overlap(pages)

    assert trims[0].blocks == 1
    assert "chapter two" not in trims[0].text


def test_escaped_prose_starting_with_a_hash_is_not_a_heading():
    # The extractor escapes a literal '#' in prose, so it must not be
    # mistaken for structure and stepped over.
    literal = r"\#1 on the list was the path home, which had never felt so long."
    pages = [pg(1, C, A), pg(2, literal, A, D)]

    trimmed, _ = trim_overlap(pages)

    assert trimmed[1].body == joined(literal, A, D)


# --- reporting --------------------------------------------------------------


def test_what_was_trimmed_is_reported():
    pages = [pg(1, C, A), pg(2, A, D)]

    _, trims = trim_overlap(pages)

    assert len(trims) == 1
    assert trims[0].number == 2
    assert trims[0].blocks == 1
    assert "path home" in trims[0].text


def test_nothing_is_reported_when_nothing_is_trimmed():
    _, trims = trim_overlap([pg(1, A), pg(2, D)])

    assert trims == []


def test_the_report_summarises_a_long_trimmed_run():
    long_block = " ".join(f"Sentence number {i} of a very long recap block." for i in range(20))
    pages = [pg(1, C, long_block), pg(2, long_block, D)]

    _, trims = trim_overlap(pages)

    assert len(trims[0].text) <= 80
    assert trims[0].text.endswith("...")


def test_the_report_is_plain_ascii():
    # It goes to the console, and a legacy Windows code page raises on
    # anything it cannot encode.
    curly = "“The path home had never felt so long,” he said…"
    pages = [pg(1, C, curly), pg(2, curly, D)]

    _, trims = trim_overlap(pages)

    trims[0].text.encode("ascii")
