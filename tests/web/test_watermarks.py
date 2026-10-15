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


# --- telling site and author notes from the story ---------------------------------

from scraper.web.watermarks import classify  # noqa: E402

# Lines that repeat across Weakest Beast Tamer, as the site and author added them...
JUNK = [
    ("Give it a power stone!", "reader"),
    ("Have some idea about my story?", "reader"),
    ("Comment it and let me know.", "reader"),
    ("Thank you so much for reading!", "reader"),
    ("┻━┻ ︵ヽ(`Д´)ﾉ︵ ┻━┻ – It’s free and you help me a lot", "symbols"),
    ('Follow new episodes on the "N0vel1st.c0m".', "website"),
    ("Read more at FreeWebNovel.Com today.", "website"),
    ("Visit www.example.org for the latest chapters.", "website"),
]
# ...and lines that repeat because the author writes that way.
STORY = [
    "The silence that followed was absolute.",
    "Ren shook his head.",
    '"What’s happening?"',
    "Selphira smiled.",
    "But it was too late.",
    '"What do you mean?"',
    "she said finally.",
    '"Help me!"',
    '"No comment," he said.',
    "He commented on the weather and left.",
    "The army moved to support the vanguard.",
    # Shadow Slave's in-world system messages, with the brackets escaped as they are stored
    "\\[You have received a Memory...\\]",
    "\\[Your Memory has been destroyed.\\]",
    "*Sunny gritted his teeth.*",
]


@pytest.mark.parametrize("text, signal", JUNK)
def test_site_and_author_notes_look_like_junk(text, signal):
    kind, signals = classify(text)
    assert kind == "junk" and signal in signals


@pytest.mark.parametrize("text", STORY)
def test_the_authors_own_lines_look_like_story(text):
    assert classify(text) == ("story", [])


def test_rows_say_which_kind_and_why():
    pages_ = [Page(number=i, title=None, body=f"Ren shook his head. Story {i} goes on and on here. Give it a power stone!")
              for i in range(1, 6)]

    rows = {r["text"]: r for r in review_rows(pages_, min_chapters=4, ignore=[])}

    assert rows["Give it a power stone!"]["kind"] == "junk" and rows["Give it a power stone!"]["signals"] == ["reader"]
    assert rows["Ren shook his head."]["kind"] == "story" and rows["Ren shook his head."]["signals"] == []


def test_the_tester_warns_when_a_pattern_catches_story():
    lines = [f"Ren shook his head {i} times." for i in range(5)] + ["Line plain filler sentence here."] * 300
    pages_ = [Page(number=1, title=None, body=" ".join(lines))]

    result = try_pattern(pages_, "shook his head")

    assert "look like the story" in result["story_warning"]
    assert "story_warning" not in try_pattern(pages(60), "freewebnovel")
