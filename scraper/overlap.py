"""Trim the recap a page opens with.

Serialised sources often restate the end of the previous instalment before
getting on with the new one. `boilerplate` cannot see it: the restatement is
prose, it appears on two pages rather than most of them, and it is rarely
byte-identical - it gets reworded and re-paragraphed on the way in.

So this works a sentence at a time. For each page, take the sentences from
the tail of the page before, then walk the new page's leading blocks and
drop each one whose every sentence turns up in that tail. Stop at the first
block that does not, which keeps the damage to a leading run.

Pure functions over a list of `Page`. No network, no filesystem.

Run it *after* `boilerplate.clean_pages`. Site furniture at the top of a
page - a "Chapter 12" line, a navigation strip - sits between the recap and
the start of the page, and would stop the walk before it began. Worse, a
"next chapter" teaser left in the page before makes furniture look like a
repeat, which is a false positive rather than a miss.
"""

from __future__ import annotations

import dataclasses
import difflib
import re
from dataclasses import dataclass

from scraper.extract import Page

# Blocks at the end of the previous page that count as a recap source.
# Further back than this a match says more about the language than about
# the source repeating itself.
DEFAULT_WINDOW = 15

# How close two sentences must be to count as the same one. Low enough to
# survive a reworded recap, high enough to reject a mere paraphrase.
DEFAULT_CUTOFF = 0.85

# Shorter than this and a sentence is not evidence of anything: "He nodded."
# recurs in any book without being a recap.
_MIN_SENTENCE = 12

_SUMMARY_LENGTH = 80

_SENTENCE_RE = re.compile(r'(?<=[.!?"”’…])\s+')
_NOT_PLAIN_RE = re.compile(r"[^a-z0-9 ]+")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class Trim:
    """One page's recap, and how much of it went. Reported so nothing vanishes silently."""

    number: int | None
    blocks: int
    text: str


def trim_overlap(
    pages: list[Page],
    window: int = DEFAULT_WINDOW,
    cutoff: float = DEFAULT_CUTOFF,
) -> tuple[list[Page], list[Trim]]:
    """Drop the leading blocks of each page that restate the page before it."""
    if not pages:
        return [], []

    trimmed = [pages[0]]
    trims: list[Trim] = []

    # Pair each page with the page as it arrived, not as it was trimmed: a
    # recap restates the end of the page before, which trimming never touches.
    for previous, page in zip(pages, pages[1:]):
        kept, removed = _split_recap(
            _blocks(page), _recap_sentences(previous, window), cutoff
        )
        if removed:
            trims.append(
                Trim(
                    number=page.number,
                    blocks=len(removed),
                    text=_summarise(" ".join(removed)),
                )
            )
            page = dataclasses.replace(page, body="\n\n".join(kept))
        trimmed.append(page)

    return trimmed, trims


def _recap_sentences(page: Page, window: int) -> list[str]:
    return [s for block in _blocks(page)[-window:] for s in _sentences(block)]


def _split_recap(
    blocks: list[str], recap: list[str], cutoff: float
) -> tuple[list[str], list[str]]:
    """Split leading blocks into the ones that stay and the ones that restate `recap`.

    Headings are structure rather than prose, so the walk steps over them and
    keeps them. Without that, a chapter title sitting inside the content
    selector - which is where most sources put it - hides the recap behind it
    and nothing is ever trimmed.
    """
    removed: list[str] = []
    end = 0
    for end, block in enumerate(blocks):
        if _is_heading(block):
            continue
        sentences = _sentences(block)
        # A block of nothing but short lines is not evidence either way, so
        # it ends the run rather than extending it.
        if not sentences or not all(_repeats(s, recap, cutoff) for s in sentences):
            break
        removed.append(block)
    else:
        end = len(blocks)

    # A page that is nothing but a recap is more likely a duplicate fetch
    # than a page to delete. Leave it whole and let the reader judge.
    if all(_is_heading(block) for block in blocks[end:]):
        return blocks, []

    return [b for b in blocks[:end] if _is_heading(b)] + blocks[end:], removed


def _is_heading(block: str) -> bool:
    # The extractor escapes a literal '#' in prose as '\#', so an unescaped
    # one at the start of a block is always a heading it emitted.
    return block.startswith("#")


def _repeats(sentence: str, recap: list[str], cutoff: float) -> bool:
    return bool(difflib.get_close_matches(sentence, recap, n=1, cutoff=cutoff))


def _sentences(block: str) -> list[str]:
    return [
        text
        for text in (_normalise(part) for part in _SENTENCE_RE.split(block))
        if len(text) >= _MIN_SENTENCE
    ]


def _normalise(text: str) -> str:
    """Reduce to the words alone, so punctuation and emphasis cannot matter.

    The extractor escapes Markdown and adds its own emphasis markers, and a
    recap is often re-typeset with different quotes, so comparing anything
    but the letters produces spurious differences.
    """
    return _WHITESPACE_RE.sub(" ", _NOT_PLAIN_RE.sub(" ", text.lower())).strip()


def _blocks(page: Page) -> list[str]:
    return [b for b in page.body.split("\n\n") if b.strip()]


def _summarise(text: str) -> str:
    """A fingerprint of what went, short enough for one console line.

    Built from the normalised form, which is plain ASCII by construction:
    this goes to the console, and a Windows terminal in a legacy code page
    raises on characters it cannot encode - which curly quotes, in prose
    lifted from a web page, very much are.
    """
    text = _normalise(text)
    if len(text) <= _SUMMARY_LENGTH:
        return text
    return text[: _SUMMARY_LENGTH - 3].rstrip() + "..."
