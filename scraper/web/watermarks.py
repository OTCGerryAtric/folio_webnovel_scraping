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


def review_rows(pages, min_chapters: int, ignore) -> list[dict]:
    """Repeated sentences, each with up to two places it appears."""
    repeats = repeated_sentences(pages, min_chapters=min_chapters, ignore=ignore)
    contexts: dict[str, list[dict]] = {r.key: [] for r in repeats}
    for page in pages:
        for block in page.body.split("\n\n"):
            for sentence in split_sentences(block):
                found = contexts.get(normalise(sentence))
                if found is None or len(found) >= 2:
                    continue
                if all(c["chapter"] != page.number for c in found):
                    found.append({"chapter": page.number, "text": _snippet(block, sentence)})
    return [
        {"text": r.text, "key": r.key, "chapters": r.chapters, "first": r.first, "contexts": contexts[r.key]}
        for r in repeats
    ]


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

    total = matched = 0
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
