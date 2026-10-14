"""Tests for the repeated-sentence report."""
from scraper.extract import Page
from scraper.review import repeated_sentences

NOTE = "Give it a power stone, please!"


def page(number, body):
    return Page(number=number, title=None, body=body)


def test_sentences_in_enough_chapters_are_listed_with_their_first_chapter():
    pages = [page(n, f"Story {n} goes on and on. {NOTE}") for n in range(3, 8)]

    repeats = repeated_sentences(pages, min_chapters=4)

    assert [(r.text, r.chapters, r.first) for r in repeats] == [(NOTE, 5, 3)]


def test_chapters_are_counted_not_occurrences():
    pages = [page(1, f"{NOTE}\n\n{NOTE}\n\n{NOTE}"), page(2, NOTE)]

    assert repeated_sentences(pages, min_chapters=3) == []
    assert repeated_sentences(pages, min_chapters=2)[0].chapters == 2


def test_differences_in_punctuation_and_case_still_match():
    pages = [page(1, "Give it a power stone, please!"), page(2, "give it a POWER stone please")]

    assert repeated_sentences(pages, min_chapters=2)[0].chapters == 2


def test_short_sentences_are_not_evidence():
    pages = [page(n, "He nodded.") for n in range(1, 10)]

    assert repeated_sentences(pages, min_chapters=2) == []


def test_the_most_repeated_come_first_and_the_list_is_capped():
    pages = [page(n, "Alpha sentence repeated often. " + ("Beta sentence here too." if n < 3 else ""))
             for n in range(1, 6)]

    repeats = repeated_sentences(pages, min_chapters=2, limit=1)

    assert [r.text for r in repeats] == ["Alpha sentence repeated often."]


def test_report_text_is_ascii_safe():
    pages = [page(n, "“It’s not enough at all…”") for n in range(1, 3)]

    text = repeated_sentences(pages, min_chapters=2)[0].text

    assert text == "\"It's not enough at all...\""
    assert text.isascii()
