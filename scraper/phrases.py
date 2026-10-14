"""Remove watermark sentences, keeping the story around them.

Sites splice their name into the text in ever-changing wording - "Explore
more at freewebnovel", "Stay connected with freewebnovel.com" - and often
onto the end of a real paragraph. Dropping the whole block, as
`boilerplate`'s patterns do, would take story text with it. So this works
a sentence at a time: a sentence matching any pattern goes, the rest of
its block stays, and a block left with nothing in it goes too.

Pure functions over a list of `Page`. No network, no filesystem.
"""

from __future__ import annotations

import dataclasses
import re

from scraper.boilerplate import Removal
from scraper.extract import Page

# Split after sentence-ending punctuation, keeping the whitespace so a hard
# line break between kept sentences survives. Closing emphasis markers and
# brackets end a sentence too: sites often set a watermark in italics or
# parentheses at the front of a story paragraph.
_SPLIT_RE = re.compile(r'(?<=[.!?"”’…*_)\]])(\s+)')


def remove_phrases(pages: list[Page], patterns) -> tuple[list[Page], list[Removal]]:
    """Drop every sentence matching one of `patterns`, case-insensitively."""
    compiled = _compile(patterns)
    if not compiled or not pages:
        return list(pages), []

    sentences = {p.pattern: 0 for p in compiled}
    on_pages = {p.pattern: 0 for p in compiled}
    cleaned = []

    for page in pages:
        hit_here: set[str] = set()
        blocks = []
        for block in page.body.split("\n\n"):
            text, hits = _clean_block(block, compiled)
            for pattern in hits:
                sentences[pattern] += 1
                hit_here.add(pattern)
            if text.strip():
                blocks.append(text)
        for pattern in hit_here:
            on_pages[pattern] += 1
        cleaned.append(dataclasses.replace(page, body="\n\n".join(blocks)) if hit_here else page)

    removals = [
        Removal(
            text=f"{sentences[pattern]} sentence(s) matching {pattern}",
            pages=on_pages[pattern],
            reason="phrase",
        )
        for pattern in sentences
        if sentences[pattern]
    ]
    removals.sort(key=lambda r: r.pages, reverse=True)
    return cleaned, removals


def _clean_block(block: str, compiled: list) -> tuple[str, list[str]]:
    parts = _SPLIT_RE.split(block)
    kept: list[tuple[str, str]] = []
    hits: list[str] = []
    for index in range(0, len(parts), 2):
        sentence = parts[index]
        hit = next((p for p in compiled if p.search(sentence)), None)
        if hit is None:
            kept.append((parts[index - 1] if index else "", sentence))
        else:
            hits.append(hit.pattern)
    if not hits:
        return block, []
    return "".join(sep + sentence for sep, sentence in kept).strip(), hits


def _compile(patterns) -> list:
    compiled = []
    for pattern in patterns or ():
        try:
            compiled.append(re.compile(pattern, re.IGNORECASE))
        except re.error as exc:
            raise ValueError(f"Invalid remove phrase {pattern!r}: {exc}") from exc
    return compiled
