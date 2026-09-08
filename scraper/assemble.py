"""Join extracted pages into a single document.

The output format follows the file extension: `.md`, `.txt` or `.epub`.
"""

from __future__ import annotations

import html
import re
import uuid
from pathlib import Path

from scraper.extract import Page

# Emphasis markers that were not escaped by the extractor, i.e. ones we
# emitted ourselves rather than ones present in the source text.
_STRONG_RE = re.compile(r"(?<!\\)\*\*(.+?)(?<!\\)\*\*", re.DOTALL)
_EMPHASIS_RE = re.compile(r"(?<!\\)\*(.+?)(?<!\\)\*", re.DOTALL)
_UNESCAPE_RE = re.compile(r"\\([\\`*_\[\]#])")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_ORDERED_ITEM_RE = re.compile(r"^\d+\.\s+(.*)$")


def write_document(
    pages: list[Page], out_path: Path | str, title: str | None = None
) -> Path:
    """Write `pages` to `out_path` as one document."""
    if not pages:
        raise ValueError("no pages to write")

    path = Path(out_path)
    writer = _WRITERS.get(path.suffix.lower())
    if writer is None:
        raise ValueError(
            f"Unsupported output format {path.suffix!r}. "
            f"Use one of: {', '.join(sorted(_WRITERS))}"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    writer(pages, path, title)
    return path


def _heading_for(page: Page) -> str:
    return page.title or f"Page {page.number}"


# --- markdown ---------------------------------------------------------------


def _write_markdown(pages: list[Page], path: Path, title: str | None) -> None:
    level = "##" if title else "#"
    sections = [f"{level} {_heading_for(p)}\n\n{p.body}".rstrip() for p in pages]
    if title:
        sections.insert(0, f"# {title}")
    path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")


# --- plain text -------------------------------------------------------------


def _write_text(pages: list[Page], path: Path, title: str | None) -> None:
    sections = []
    if title:
        sections.append(_underline(title, "="))
    for page in pages:
        heading = _underline(_heading_for(page), "-" if title else "=")
        sections.append(f"{heading}\n\n{_to_plain(page.body)}".rstrip())
    path.write_text("\n\n".join(sections) + "\n", encoding="utf-8")


def _underline(text: str, character: str) -> str:
    return f"{text}\n{character * len(text)}"


def _to_plain(markdown: str) -> str:
    """Drop Markdown syntax, leaving readable prose."""
    lines = []
    for line in markdown.split("\n"):
        heading = _HEADING_RE.match(line)
        if heading:
            depth = len(heading.group(1))
            lines.append(_underline(_strip_inline(heading.group(2)), "=" if depth == 1 else "-"))
        else:
            lines.append(_strip_inline(line))
    return "\n".join(lines)


def _strip_inline(text: str) -> str:
    text = _STRONG_RE.sub(r"\1", text)
    text = _EMPHASIS_RE.sub(r"\1", text)
    return _unescape(text)


def _unescape(text: str) -> str:
    return _UNESCAPE_RE.sub(r"\1", text)


# --- epub -------------------------------------------------------------------


def _write_epub(pages: list[Page], path: Path, title: str | None) -> None:
    from ebooklib import epub

    book = epub.EpubBook()
    book.set_identifier(str(uuid.uuid4()))
    book.set_title(title or path.stem)
    book.set_language("en")

    chapters = []
    for index, page in enumerate(pages, 1):
        heading = _heading_for(page)
        number = page.number if page.number is not None else index
        chapter = epub.EpubHtml(
            title=heading, file_name=f"page_{number}.xhtml", lang="en"
        )
        chapter.content = (
            f"<h1>{html.escape(heading)}</h1>\n{_to_html(page.body)}"
        )
        book.add_item(chapter)
        chapters.append(chapter)

    book.toc = tuple(chapters)
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", *chapters]

    epub.write_epub(str(path), book)


def _to_html(markdown: str) -> str:
    """Render the Markdown subset the extractor emits back into HTML."""
    parts = []
    for block in markdown.split("\n\n"):
        block = block.strip("\n")
        if not block.strip():
            continue

        heading = _HEADING_RE.match(block)
        if heading:
            depth = len(heading.group(1))
            parts.append(f"<h{depth}>{_inline_html(heading.group(2))}</h{depth}>")
        elif block.strip() == "---":
            parts.append("<hr/>")
        elif all(line.startswith(">") for line in block.split("\n")):
            inner = "\n".join(line.lstrip("> ").rstrip() for line in block.split("\n"))
            parts.append(f"<blockquote><p>{_inline_html(inner)}</p></blockquote>")
        elif all(line.startswith("- ") for line in block.split("\n")):
            items = "".join(
                f"<li>{_inline_html(line[2:])}</li>" for line in block.split("\n")
            )
            parts.append(f"<ul>{items}</ul>")
        elif all(_ORDERED_ITEM_RE.match(line) for line in block.split("\n")):
            items = "".join(
                f"<li>{_inline_html(_ORDERED_ITEM_RE.match(line).group(1))}</li>"
                for line in block.split("\n")
            )
            parts.append(f"<ol>{items}</ol>")
        else:
            parts.append(f"<p>{_inline_html(block).replace(chr(10), '<br/>')}</p>")

    return "\n".join(parts)


def _inline_html(text: str) -> str:
    """Escape for HTML first, then turn our own markers into tags."""
    text = html.escape(text, quote=False)
    text = _STRONG_RE.sub(r"<strong>\1</strong>", text)
    text = _EMPHASIS_RE.sub(r"<em>\1</em>", text)
    return _unescape(text)


# Registered last, once every writer above exists.
_WRITERS = {
    ".md": _write_markdown,
    ".markdown": _write_markdown,
    ".txt": _write_text,
    ".text": _write_text,
    ".epub": _write_epub,
}

SUPPORTED_FORMATS = frozenset(_WRITERS)
