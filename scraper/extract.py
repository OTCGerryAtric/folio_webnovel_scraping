"""Turn a page of HTML into Markdown, keeping the formatting that matters.

Pure functions only: no network, no filesystem. Give it a string of HTML
and it gives you back a `Page`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from bs4 import BeautifulSoup, Comment

# Placeholder for <br>. It survives whitespace collapsing, which a bare
# newline would not, and is swapped for a real newline at the end.
_BREAK = "\x00"

_HEADINGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_CONTAINERS = {"div", "section", "article", "main", "body", "span"}
_EMPHASIS = {"em", "i", "cite", "dfn"}
_STRONG = {"strong", "b"}
_DROP = {"script", "style", "noscript"}

# Chrome that is never part of the prose.
_NOISE_TAGS = ("script", "style", "noscript", "nav", "header", "footer", "aside")
_HIDDEN_SELECTORS = ('[style*="display:none"]', '[style*="display: none"]', "[hidden]")

_ESCAPE_RE = re.compile(r"([\\`*_\[\]#])")
_SPACE_RE = re.compile(r"[ \t\r\n]+")
_BREAK_RE = re.compile(r" *\x00 *")


@dataclass(frozen=True)
class Page:
    """One extracted page: its number, what it is called, and what it says."""

    number: int | None
    title: str | None
    body: str

    @property
    def is_empty(self) -> bool:
        return not self.body.strip()


def extract_page(
    html: str,
    content_selector: str | None = None,
    title_selector: str | None = None,
    remove_selectors: list[str] | None = None,
) -> Page:
    """Extract the main text of `html` as Markdown.

    With no `content_selector`, the densest block of prose on the page is
    used. A selector that matches nothing yields an empty body, which the
    caller reads as a miss.
    """
    soup = BeautifulSoup(html, "lxml")

    title = _find_title(soup, title_selector)
    _strip_noise(soup, remove_selectors or [])

    if content_selector:
        root = _select_one(soup, content_selector)
        if root is None:
            return Page(number=None, title=title, body="")
    else:
        root = _densest_block(soup)

    return Page(number=None, title=title, body="\n\n".join(_blocks(root)))


# --- locating the content ---------------------------------------------------


def _select_one(soup: BeautifulSoup, selector: str):
    try:
        return soup.select_one(selector)
    except Exception as exc:  # soupsieve raises its own syntax errors
        raise ValueError(f"Invalid content selector {selector!r}: {exc}") from exc


def _strip_noise(soup: BeautifulSoup, remove_selectors: list[str]) -> None:
    for element in soup.find_all(_NOISE_TAGS):
        element.decompose()
    for comment in soup.find_all(string=lambda s: isinstance(s, Comment)):
        comment.extract()
    for selector in list(remove_selectors) + list(_HIDDEN_SELECTORS):
        try:
            matches = soup.select(selector)
        except Exception as exc:
            raise ValueError(f"Invalid remove selector {selector!r}: {exc}") from exc
        for element in matches:
            element.decompose()


def _densest_block(soup: BeautifulSoup):
    """Pick the container holding the most prose.

    Paragraph text is scored first, since a sidebar of links can be long
    without being prose. Ties go to the deeper element, so we land on the
    chapter div rather than the <body> that wraps it.
    """
    root = soup.body or soup
    candidates = [root, *root.find_all(["div", "article", "section", "main"])]

    def depth(element) -> int:
        return len(list(element.parents))

    best, best_score = root, (-1, -1)
    for candidate in candidates:
        paragraph_text = sum(
            len(p.get_text(" ", strip=True)) for p in candidate.find_all("p")
        )
        score = (paragraph_text, depth(candidate))
        if score > best_score:
            best, best_score = candidate, score

    if best_score[0] > 0:
        return best

    # No paragraphs anywhere - fall back to raw text length.
    best, best_score = root, (-1, -1)
    for candidate in candidates:
        score = (len(candidate.get_text(" ", strip=True)), depth(candidate))
        if score > best_score:
            best, best_score = candidate, score
    return best


def _find_title(soup: BeautifulSoup, title_selector: str | None) -> str | None:
    if title_selector:
        match = _select_one(soup, title_selector)
        if match:
            text = match.get_text(" ", strip=True)
            if text:
                return text
    if soup.title and soup.title.string:
        text = soup.title.string.strip()
        if text:
            return text
    return None


# --- rendering --------------------------------------------------------------


def _blocks(node) -> list[str]:
    """Render a container's children into a list of Markdown blocks."""
    blocks: list[str] = []
    pending: list[str] = []

    def flush() -> None:
        if pending:
            text = _tidy("".join(pending))
            if text:
                blocks.append(text)
            pending.clear()

    for child in node.children:
        name = getattr(child, "name", None)

        if name is None:
            if not isinstance(child, Comment):
                pending.append(_escape(str(child)))
            continue

        if name in _DROP:
            continue

        if name in _HEADINGS:
            flush()
            text = _tidy(_inline(child))
            if text:
                blocks.append("#" * int(name[1]) + " " + text)
        elif name == "p":
            flush()
            text = _tidy(_inline(child))
            if text:
                blocks.append(text)
        elif name == "hr":
            flush()
            blocks.append("---")
        elif name == "blockquote":
            flush()
            inner = "\n\n".join(_blocks(child))
            if inner:
                blocks.append(
                    "\n".join(f"> {line}" if line else ">" for line in inner.split("\n"))
                )
        elif name in ("ul", "ol"):
            flush()
            items = []
            for index, item in enumerate(child.find_all("li", recursive=False), 1):
                text = _tidy(_inline(item))
                if text:
                    items.append(f"{index}. {text}" if name == "ol" else f"- {text}")
            if items:
                blocks.append("\n".join(items))
        elif name in _CONTAINERS:
            flush()
            blocks.extend(_blocks(child))
        else:
            pending.append(_inline(child))

    flush()
    return blocks


def _inline(node) -> str:
    """Render inline content, keeping emphasis and hard breaks."""
    parts: list[str] = []
    for child in node.children:
        name = getattr(child, "name", None)
        if name is None:
            if not isinstance(child, Comment):
                parts.append(_escape(str(child)))
        elif name in _DROP:
            continue
        elif name == "br":
            parts.append(_BREAK)
        elif name in _EMPHASIS:
            inner = _inline(child).strip()
            if inner:
                parts.append(f"*{inner}*")
        elif name in _STRONG:
            inner = _inline(child).strip()
            if inner:
                parts.append(f"**{inner}**")
        else:
            parts.append(_inline(child))
    return "".join(parts)


def _escape(text: str) -> str:
    return _ESCAPE_RE.sub(r"\\\1", text)


def _tidy(text: str) -> str:
    """Collapse source whitespace but keep hard breaks."""
    text = _SPACE_RE.sub(" ", text)
    text = _BREAK_RE.sub("\n", text)
    return text.strip()
