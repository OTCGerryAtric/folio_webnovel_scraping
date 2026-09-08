"""Tests for HTML -> Markdown extraction.

Every fixture here is hand-written. The suite never touches the network.
"""
import pytest

from scraper.extract import extract_page


def html(body: str, title: str = "Test Page") -> str:
    return f"<html><head><title>{title}</title></head><body>{body}</body></html>"


# --- paragraphs and whitespace ---------------------------------------------


def test_paragraphs_are_separated_by_a_blank_line():
    page = extract_page(
        html("<div id='c'><p>First para.</p><p>Second para.</p></div>"),
        content_selector="#c",
    )
    assert page.body == "First para.\n\nSecond para."


def test_whitespace_inside_a_paragraph_is_collapsed():
    page = extract_page(
        html("<div id='c'><p>Ragged\n   source    text</p></div>"),
        content_selector="#c",
    )
    assert page.body == "Ragged source text"


def test_empty_paragraphs_are_dropped():
    page = extract_page(
        html("<div id='c'><p>One</p><p>  </p><p>Two</p></div>"),
        content_selector="#c",
    )
    assert page.body == "One\n\nTwo"


# --- formatting -------------------------------------------------------------


def test_headings_become_hashes_at_matching_depth():
    page = extract_page(
        html("<div id='c'><h1>Big</h1><h3>Small</h3></div>"),
        content_selector="#c",
    )
    assert page.body == "# Big\n\n### Small"


def test_emphasis_and_strong_are_preserved():
    page = extract_page(
        html("<div id='c'><p>An <em>emphasised</em> and <strong>strong</strong> word.</p></div>"),
        content_selector="#c",
    )
    assert page.body == "An *emphasised* and **strong** word."


def test_i_and_b_are_treated_as_emphasis():
    page = extract_page(
        html("<div id='c'><p><i>it</i> and <b>bo</b></p></div>"),
        content_selector="#c",
    )
    assert page.body == "*it* and **bo**"


def test_nested_emphasis_is_preserved():
    page = extract_page(
        html("<div id='c'><p><strong>bold with <em>italic</em> inside</strong></p></div>"),
        content_selector="#c",
    )
    assert page.body == "**bold with *italic* inside**"


def test_br_becomes_a_hard_line_break():
    page = extract_page(
        html("<div id='c'><p>line one<br/>line two</p></div>"),
        content_selector="#c",
    )
    assert page.body == "line one\nline two"


def test_blockquote_lines_are_prefixed():
    page = extract_page(
        html("<div id='c'><blockquote><p>quoted</p></blockquote></div>"),
        content_selector="#c",
    )
    assert page.body == "> quoted"


def test_unordered_list_items_become_dashes():
    page = extract_page(
        html("<div id='c'><ul><li>alpha</li><li>beta</li></ul></div>"),
        content_selector="#c",
    )
    assert page.body == "- alpha\n- beta"


def test_ordered_list_items_are_numbered():
    page = extract_page(
        html("<div id='c'><ol><li>alpha</li><li>beta</li></ol></div>"),
        content_selector="#c",
    )
    assert page.body == "1. alpha\n2. beta"


def test_horizontal_rule_becomes_three_dashes():
    page = extract_page(
        html("<div id='c'><p>a</p><hr/><p>b</p></div>"),
        content_selector="#c",
    )
    assert page.body == "a\n\n---\n\nb"


def test_html_entities_are_decoded():
    page = extract_page(
        html("<div id='c'><p>Caf&eacute; &amp; bar &mdash; open</p></div>"),
        content_selector="#c",
    )
    assert page.body == "Café & bar — open"


def test_markdown_metacharacters_in_text_are_escaped():
    page = extract_page(
        html("<div id='c'><p>5 * 3 and a_b and # hash</p></div>"),
        content_selector="#c",
    )
    assert page.body == r"5 \* 3 and a\_b and \# hash"


# --- noise removal ----------------------------------------------------------


def test_script_and_style_are_stripped():
    page = extract_page(
        html("<div id='c'><script>var x=1;</script><p>real</p><style>p{}</style></div>"),
        content_selector="#c",
    )
    assert page.body == "real"


def test_navigation_chrome_is_stripped():
    page = extract_page(
        html("<div id='c'><nav>Prev Next</nav><p>real</p><footer>copyright</footer></div>"),
        content_selector="#c",
    )
    assert page.body == "real"


def test_custom_remove_selectors_are_applied():
    page = extract_page(
        html("<div id='c'><p class='ad'>buy things</p><p>real</p></div>"),
        content_selector="#c",
        remove_selectors=[".ad"],
    )
    assert page.body == "real"


# --- content location -------------------------------------------------------


def test_explicit_selector_wins_over_larger_blocks():
    body = (
        "<div id='sidebar'><p>" + ("filler sentence. " * 40) + "</p></div>"
        "<div id='c'><p>the short real text</p></div>"
    )
    page = extract_page(html(body), content_selector="#c")
    assert page.body == "the short real text"


def test_auto_detection_picks_the_densest_text_block():
    body = (
        "<div class='sidebar'><ul><li>link</li><li>link</li></ul></div>"
        "<div class='content'><p>" + ("A real sentence of prose. " * 20) + "</p></div>"
    )
    page = extract_page(html(body))
    assert "A real sentence of prose." in page.body
    assert "link" not in page.body


def test_missing_selector_yields_an_empty_body():
    page = extract_page(html("<div id='c'><p>text</p></div>"), content_selector="#nope")
    assert page.body == ""


def test_invalid_selector_raises_a_clear_error():
    with pytest.raises(ValueError, match="selector"):
        extract_page(html("<p>x</p>"), content_selector="<<<not a selector>>>")


# --- title ------------------------------------------------------------------


def test_title_selector_is_used_when_given():
    page = extract_page(
        html("<h1>Chapter Nine</h1><div id='c'><p>body</p></div>"),
        content_selector="#c",
        title_selector="h1",
    )
    assert page.title == "Chapter Nine"


def test_title_falls_back_to_the_document_title():
    page = extract_page(
        html("<div id='c'><p>body</p></div>", title="Doc Title"),
        content_selector="#c",
    )
    assert page.title == "Doc Title"


def test_title_is_none_when_nothing_matches():
    page = extract_page(
        "<html><body><div id='c'><p>body</p></div></body></html>",
        content_selector="#c",
    )
    assert page.title is None
