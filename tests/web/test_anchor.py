"""Tests for finding a saved place again after a re-clean."""
from scraper.web.anchor import find_paragraph, make_anchor, resolve_position

PARAS = [f"Paragraph number {i} talks about something rather particular to itself." for i in range(40)]


def saved(chapter=5, paragraph=17, offset=0.4, paras=PARAS, version="v1"):
    return {"chapter": chapter, "paragraph": paragraph, "offset": offset,
            "anchor": make_anchor(paras[paragraph]), "paragraphs": len(paras), "version": version}


def loader(chapters):
    return lambda n: chapters.get(n)


def test_anchor_is_the_normalised_opening():
    assert make_anchor("“Wait,” Sunny said — *quietly*. " + "word " * 20).split()[:3] == ["wait", "sunny", "said"]
    assert len(make_anchor("word " * 30).split()) == 12


def test_unchanged_chapter_is_exact():
    got = resolve_position(saved(), [5], loader({5: ("v1", PARAS)}))
    assert (got["paragraph"], got["offset"], got["recovered"]) == (17, 0.4, "exact")


def test_paragraphs_inserted_above_are_followed_by_the_anchor():
    changed = ["New intro A.", "New intro B.", "New intro C."] + PARAS
    got = resolve_position(saved(), [5], loader({5: ("v2", changed)}))
    assert (got["paragraph"], got["offset"], got["recovered"]) == (20, 0.4, "anchor")


def test_a_lightly_edited_anchor_paragraph_is_still_found():
    changed = list(PARAS)
    changed[17] = changed[17].replace("rather", "very")
    got = resolve_position(saved(), [5], loader({5: ("v2", changed)}))
    assert (got["paragraph"], got["recovered"]) == (17, "anchor")


def test_a_vanished_passage_falls_back_to_the_same_proportion():
    changed = [f"Entirely different text {i} here now." for i in range(20)]
    got = resolve_position(saved(), [5], loader({5: ("v2", changed)}))
    assert (got["paragraph"], got["offset"], got["recovered"]) == (8, 0.0, "proportional")  # 17/40 of 20


def test_a_removed_chapter_moves_to_the_next_then_the_previous():
    got = resolve_position(saved(chapter=5), [3, 8], loader({3: ("x", PARAS), 8: ("y", PARAS)}))
    assert (got["chapter"], got["paragraph"], got["recovered"]) == (8, 0, "moved")
    got = resolve_position(saved(chapter=5), [3], loader({3: ("x", PARAS)}))
    assert (got["chapter"], got["recovered"]) == (3, "moved")


def test_no_chapters_means_no_position():
    assert resolve_position(saved(), [], loader({})) is None


def test_a_chapter_shrunk_below_the_saved_paragraph_is_clamped():
    got = resolve_position(saved(paragraph=17), [5], loader({5: ("v1", PARAS[:5])}))
    assert got["paragraph"] == 4


def test_search_stays_near_the_old_place():
    assert find_paragraph(make_anchor(PARAS[17]), PARAS, near=17) == 17
    far = ["x y z"] * 30 + PARAS[17:18]
    assert find_paragraph(make_anchor(PARAS[17]), far, near=0) is None  # 30 away: beyond the window
    assert find_paragraph("", PARAS, near=0) is None
