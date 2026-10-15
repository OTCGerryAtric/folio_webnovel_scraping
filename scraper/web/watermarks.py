"""The watermark studio's working parts: repeated sentences with context,
trying a pattern against the whole book, and suggesting one.

Pure functions over cleaned pages. No network, no filesystem.
"""

from __future__ import annotations

import re

from scraper.review import normalise, repeated_sentences, split_sentences

# A pattern that would remove more than this share of the book's sentences
# is surely catching story, not a watermark, and is refused. Above
# WARN_SHARE it is allowed with a warning: a watermark in every chapter of
# short chapters can come close to 2% on its own.
MAX_SHARE = 0.10
WARN_SHARE = 0.02

_SNIPPET = 220

# How often a line repeats does not tell site junk from the author's habits:
# "The silence that followed was absolute." recurs as often as a site's
# sign-off. What the junk says does. These are the signs, each a reason
# shown to the person.
_WEBSITE = re.compile(
    r"https?://|www\.|[a-z0-9][\s.]*[.·]\s*(com|c0m|net|n3t|org|0rg|info|io|co)\b",
    re.IGNORECASE,
)
_READER = re.compile(
    r"power\s*stones?|golden\s*tickets?|\bcomments?\b|thanks?\s+(you\s+)?(so\s+much\s+)?for\s+reading"
    r"|\bmy\s+(story|novel|book|readers?)\b|\bpatreon\b|\bko-?fi\b|\bdiscord\b|\bbookmark"
    r"|support\s+(me|us|my|the\s+author|the\s+translator)\b|help\s+me\s+a\s+lot|\bit'?s\s+free\b"
    r"|follow\s+(new|us|me|the\s+novel)\b|new\s+episodes?|latest\s+chapters?|\bvote\s+for\b"
    r"|leave\s+a\s+review|\btranslat(or|ed\s+by|ion\s+by)\b|\btl\s+note\b|\bdonat",
    re.IGNORECASE,
)
_QUOTE_OPEN = ('"', "“", "'", "‘")
# Ordinary punctuation, plus the marks the cleaned text itself uses - escapes,
# brackets around in-world system messages, emphasis - none of which are junk.
_PLAIN = re.compile(r"[\w\s.,;:!?'\"“”‘’()\[\]\\*_#/\-–—…]", re.UNICODE)


def classify(sentence: str) -> tuple[str, list[str]]:
    """("junk" or "story", the signs found): what a repeated line looks like.

    Junk needs a sign - a website, words to the reader, a run of symbols -
    so anything without one is treated as the author's writing. Dialogue
    counts as story unless it names a website.
    """
    text = sentence.strip()
    signals = []
    if _WEBSITE.search(text):
        signals.append("website")
    if _READER.search(text.replace("’", "'")):
        signals.append("reader")
    odd = sum(1 for ch in text if not _PLAIN.match(ch))
    if odd >= 3 and odd / max(len(text), 1) > 0.1:
        signals.append("symbols")
    if text.startswith(_QUOTE_OPEN) and "website" not in signals:
        return "story", []
    return ("junk", signals) if signals else ("story", [])


def review_rows(pages, min_chapters: int, ignore) -> list[dict]:
    """Repeated sentences, each with up to two places it appears, and what it looks like."""
    repeats = repeated_sentences(pages, min_chapters=min_chapters, ignore=ignore)
    contexts: dict[str, list[dict]] = {r.key: [] for r in repeats}
    wanted = len(contexts) * 2
    found_count = 0
    for page in pages:
        if found_count >= wanted:
            break  # every row has its two examples; no need to read on
        for block in page.body.split("\n\n"):
            for sentence in split_sentences(block):
                found = contexts.get(normalise(sentence))
                if found is None or len(found) >= 2:
                    continue
                if all(c["chapter"] != page.number for c in found):
                    found.append({"chapter": page.number, "text": _snippet(block, sentence)})
                    found_count += 1
    rows = []
    for r in repeats:
        kind, signals = classify(r.text)
        rows.append({
            "text": r.text, "key": r.key, "chapters": r.chapters, "first": r.first,
            "contexts": contexts[r.key], "kind": kind, "signals": signals,
        })
    return rows


def test_pattern(pages, pattern: str, examples: int = 20) -> dict:
    """What a remove phrase would take out of the book, before it is saved."""
    if not pattern or not pattern.strip():
        raise ValueError("Enter a pattern to try.")
    try:
        compiled = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        raise ValueError(f"That is not a valid pattern: {exc}") from None
    if compiled.search(""):
        raise ValueError("That pattern matches empty text, so it would remove every sentence.")

    total = matched = story = 0
    chapters, samples = set(), []
    for page in pages:
        for block in page.body.split("\n\n"):
            for sentence in split_sentences(block):
                sentence = sentence.strip()
                if not sentence:
                    continue
                total += 1
                match = compiled.search(sentence)
                if match is None:
                    continue
                matched += 1
                story += classify(sentence)[0] == "story"
                chapters.add(page.number)
                if len(samples) < examples:
                    samples.append({
                        "chapter": page.number, "text": sentence,
                        "start": match.start(), "end": match.end(),
                    })
    if total and matched / total > MAX_SHARE:
        raise ValueError(
            f"That pattern would remove {matched:,} of {total:,} sentences "
            f"({matched / total:.0%}). Make it more specific."
        )
    result = {"sentences": matched, "chapters": len(chapters), "total": total, "examples": samples}
    if total and matched / total > WARN_SHARE:
        result["warning"] = (
            f"That is {matched / total:.0%} of all sentences - more than a watermark "
            f"usually is. Check the examples are all junk before saving."
        )
    if matched >= 3 and story / matched >= 0.5:
        result["story_warning"] = (
            f"{story:,} of these {matched:,} sentences look like the story - dialogue or "
            f"narration, not a site or author note. Check the examples before saving."
        )
    return result


def suggest_pattern(sentence: str) -> str:
    """The sentence's words in order, with any punctuation or spacing between them."""
    words = re.findall(r"[^\W_]+", sentence)
    if not words:
        raise ValueError("That sentence has no words to match.")
    return r"[\W_]+".join(re.escape(word) for word in words)


def _snippet(block: str, sentence: str) -> str:
    block = " ".join(block.split())
    if len(block) <= _SNIPPET:
        return block
    at = max(block.find(" ".join(sentence.split())[:40]), 0)
    start = max(at - _SNIPPET // 3, 0)
    text = block[start:start + _SNIPPET]
    return ("…" if start else "") + text + ("…" if start + _SNIPPET < len(block) else "")
