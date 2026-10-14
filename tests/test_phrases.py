"""Tests for removing watermark sentences while keeping the story around them."""
import pytest

from scraper.extract import Page
from scraper.phrases import remove_phrases

SITE = r"f[\W_]*r[\W_]*e[\W_]*e[\W_]*w[\W_]*e[\W_]*b[\W_]*n[\W_]*o[\W_]*v[\W_]*e[\W_]*l"


def page(body, number=1):
    return Page(number=number, title=f"Chapter {number}", body=body)


def test_a_watermark_on_its_own_goes_with_its_block():
    pages, _ = remove_phrases(
        [page("He ran.\n\nExplore more at freewebnovel\n\nShe followed.")], [SITE]
    )

    assert pages[0].body == "He ran.\n\nShe followed."


def test_a_watermark_glued_to_a_story_paragraph_takes_only_its_sentence():
    pages, _ = remove_phrases(
        [page("His fingers tensed. The phoenix rose. Read more at FreeWebNovel.Com")], [SITE]
    )

    assert pages[0].body == "His fingers tensed. The phoenix rose."


def test_spaced_and_capitalised_spellings_match():
    pages, _ = remove_phrases(
        [page("Story. Stay tuned to Free Web Novel! More story.")], [SITE]
    )

    assert pages[0].body == "Story. More story."


def test_hard_line_breaks_in_kept_text_survive():
    pages, _ = remove_phrases(
        [page("Line one.\nLine two. Visit freewebnovel.com")], [SITE]
    )

    assert pages[0].body == "Line one.\nLine two."


def test_pages_without_a_match_are_untouched():
    original = page("Nothing to see.\n\n\nOdd spacing kept.")

    pages, removals = remove_phrases([original], [SITE])

    assert pages[0] is original
    assert removals == []


def test_no_patterns_changes_nothing():
    original = page("Explore more at freewebnovel")

    pages, removals = remove_phrases([original], [])

    assert pages == [original]
    assert removals == []


def test_removals_count_sentences_and_pages():
    pages, removals = remove_phrases(
        [
            page("A. Explore more at freewebnovel", 1),
            page("Stay tuned to Freewebnovel. B. Find adventures on freewebnovel", 2),
            page("Clean.", 3),
        ],
        [SITE],
    )

    assert len(removals) == 1
    assert removals[0].pages == 2
    assert removals[0].text.startswith("3 sentence(s) matching")


def test_an_invalid_pattern_is_reported_clearly():
    with pytest.raises(ValueError, match="remove phrase"):
        remove_phrases([page("x")], ["(unclosed"])


def test_a_watermark_in_emphasis_or_brackets_before_the_story_takes_only_itself():
    pages, _ = remove_phrases(
        [page("*Visit freewebnovel.* He ran home."), page("(Read more at freewebnovel.) She ran.", 2)],
        [SITE],
    )

    assert [p.body for p in pages] == ["He ran home.", "She ran."]
