"""Finding a saved place in a chapter again, after a re-clean may have
changed it. Pure functions; no files, no network.

A place is a paragraph and how far into it, plus the paragraph's opening
words (its anchor), the chapter's version, and how many paragraphs the
chapter had. If the chapter is unchanged the place is used as it is;
otherwise the anchor is looked for near where it was, and failing that
the same proportion of the way through is used.
"""

from __future__ import annotations

from scraper.review import normalise

ANCHOR_WORDS = 12
WINDOW = 25  # paragraphs either side of the old place to search
OVERLAP = 0.75  # share of the anchor's words a lightly edited opening must keep


def make_anchor(paragraph: str) -> str:
    return " ".join(normalise(paragraph).split()[:ANCHOR_WORDS])


def _same_opening(anchor: str, paragraph: str) -> bool:
    opening = make_anchor(paragraph)
    return bool(opening) and (opening.startswith(anchor) or anchor.startswith(opening))


def _similar_opening(anchor: str, paragraph: str) -> bool:
    wanted, have = anchor.split(), set(make_anchor(paragraph).split())
    return bool(wanted) and sum(word in have for word in wanted) / len(wanted) >= OVERLAP


def find_paragraph(anchor: str, paragraphs: list[str], near: int) -> int | None:
    """The paragraph opening with `anchor`, looking outwards from `near`.

    An exact opening anywhere in the window beats a merely similar one
    nearer by: in a book, neighbouring paragraphs often start alike.
    """
    if not anchor:
        return None
    order = [i for d in range(WINDOW + 1) for i in sorted({near - d, near + d}) if 0 <= i < len(paragraphs)]
    for test in (_same_opening, _similar_opening):
        for index in order:
            if test(anchor, paragraphs[index]):
                return index
    return None


def resolve_position(position: dict, numbers: list[int], load) -> dict | None:
    """`position` as it lands in the chapters as they are now.

    `numbers` are the cleaned chapters; `load(n)` gives `(version,
    paragraphs)` or None. The result carries `recovered`: exact, anchor,
    proportional, or moved (to the next chapter, else the previous one).
    """
    if not numbers:
        return None
    out = dict(position)
    chapter = position["chapter"]
    loaded = load(chapter) if chapter in numbers else None
    if loaded is None:
        later = [n for n in numbers if n > chapter]
        out.update(chapter=later[0] if later else max(numbers), paragraph=0, offset=0.0, recovered="moved")
        return out

    version, paragraphs = loaded
    last = max(len(paragraphs) - 1, 0)
    if version == position.get("version"):
        out.update(paragraph=min(position["paragraph"], last), recovered="exact")
        return out

    found = find_paragraph(position.get("anchor", ""), paragraphs, near=position["paragraph"])
    if found is not None:
        out.update(paragraph=found, recovered="anchor")
        return out

    share = position["paragraph"] / max(position.get("paragraphs") or 1, 1)
    out.update(paragraph=min(int(share * len(paragraphs)), last), offset=0.0, recovered="proportional")
    return out
