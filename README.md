# Paginated Text Scraper

Walks a series of web pages whose URLs differ only by a number, pulls the
main text out of each one keeping its formatting, and joins the lot into a
single document.

The tool knows nothing about any particular website. You supply the URL
pattern and, if the page needs it, a CSS selector. **Point it only at
material you have the right to copy** — public-domain texts, openly
licensed work, your own content, or a site whose terms permit it.

## Setup

From the project folder in PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If activation is blocked by execution policy, either run
`Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` for that
session, or skip activation and call `.\.venv\Scripts\python.exe` directly.

## Usage

Fifty numbered pages into one Markdown file:

```powershell
python scrape.py --url "https://example.com/page-{n}" --start 1 --end 50 --out book.md
```

The `{n}` is the part that changes. Leave `--end` off and it keeps going
until three pages in a row come back empty:

```powershell
python scrape.py --url "https://example.com/page-{n}" --out book.md
```

The output format follows the extension — `.md`, `.txt`, `.pdf` or `.epub`:

```powershell
python scrape.py --url "https://example.com/page-{n}" --end 20 --out book.pdf
python scrape.py --url "https://example.com/page-{n}" --end 20 --out book.epub
```

### PDF

`--out book.pdf` produces a readable A4 document: 11pt serif, each source
page starting on a fresh sheet under its own heading, page numbers in the
footer, and a bookmark per page so your reader's outline panel lets you jump
around. Add `--title "My Collection"` for a title page.

One limitation worth knowing: the built-in fonts cover Latin text properly,
including accented characters, curly quotes and em-dashes. Text in Cyrillic,
Greek, Hebrew or any CJK script will come out as blank boxes. If you need
those, the fix is to embed a font that covers them — ask and it's a small
change to `_pdf_styles()` in `scraper/assemble.py`.

### Pointing it at the right part of the page

With no `--selector`, the densest block of prose on the page is used, which
handles most simple layouts. When it guesses wrong, open the page in your
browser, right-click the text, Inspect, and find the element that wraps it:

```powershell
python scrape.py --url "https://example.com/page-{n}" --selector "div.entry-content" --out book.md
```

Useful companions:

- `--title-selector "h1"` names each page from its heading rather than the
  browser title. If the heading sits *inside* your content selector it will
  appear twice — narrow the content selector to exclude it.
- `--remove ".advert" --remove "#comments"` strips anything else you don't
  want. Repeatable. `script`, `style`, `nav`, `header`, `footer` and `aside`
  are always removed.

### Removing site furniture

Most sites wrap their text in navigation links, reader-settings widgets and
"report a problem" notices. Some of it sits inside the content element, so a
selector alone will not shift it.

The giveaway is that this furniture is *identical on every page*, which is
only visible once you have all the pages together. So after extracting, any
block appearing on 60% or more of the pages is dropped. Real prose is
virtually never byte-identical across most of a run; a Prev/Next line is
identical every time.

This is on by default and it tells you what it did:

```
Removed 3 boilerplate block(s):
  on 12/12 pages: Prev Chapter
  on 12/12 pages: Background Light Gray Light Blue Warm Ivory Font family Ari...
  on 11/12 pages: Report broken chapter. Please refresh the page.
```

Read that list. It is the check on whether the tool took something it
shouldn't have. Tune it with:

- `--dedupe-threshold 0.8` — stricter, drops less
- `--no-dedupe` — keep everything

Furniture that *varies* per page can't be caught by repetition, so give it a
pattern instead. Any block matching is dropped whole:

```powershell
python scrape.py --url "..." --out book.md --strip-regex "^Chapter \d+ - "
```

`--strip-regex` is repeatable, and patterns are matched per line within a
block, so `^` anchors to a line start.

Because every page is cached, re-running to tune any of this costs nothing
and makes no new requests.

### Options

| Flag | Meaning |
|------|---------|
| `--url` | URL containing `{n}` |
| `--out` | Output file; `.md`, `.txt`, `.pdf` or `.epub` |
| `--start`, `--end`, `--step` | Which numbers to walk (default: from 1, by 1, no end) |
| `--selector` | CSS selector for the main text |
| `--title-selector` | CSS selector for each page's title |
| `--remove` | CSS selector to strip; repeatable |
| `--no-dedupe` | Keep blocks that repeat across pages |
| `--dedupe-threshold` | Fraction of pages a block must appear on (default 0.6) |
| `--strip-regex` | Drop any block matching this pattern; repeatable |
| `--title` | Title for the finished document |
| `--delay` | Seconds between requests (default 1.5) |
| `--max-misses` | Consecutive empty pages that end an open-ended run (default 3) |
| `--max-retries` | Attempts per page (default 3) |
| `--timeout` | Per-request timeout in seconds (default 30) |
| `--cache-dir` | Where to keep fetched pages |
| `--refresh` | Ignore the cache and fetch again |
| `--site` | Load settings from a TOML file |
| `--verbose` | Report each URL as it is fetched |

`python scrape.py --help` prints the same list.

## The cache

Every page fetched is written to `.cache/` as raw HTML. Rerunning costs
nothing, and a run interrupted at page 300 picks up where it stopped. This
also means you can re-extract with a different selector without hitting the
site again — only `--refresh` forces new requests.

Press Ctrl-C at any point and the pages collected so far are still written.

## Saved sources

For a source you use repeatedly, put its settings in a TOML file (see
`sites/example.toml`) and pass `--site`. Anything on the command line
overrides the file:

```powershell
python scrape.py --site sites/example.toml --end 20 --out book.md
```

## What it does not do

- **JavaScript-rendered pages.** It reads the HTML the server sends. If the
  text only appears after scripts run, you will get an empty result.
- **Logins, cookies, or anything behind an access control.**
- **Parallel requests.** Deliberately: one page at a time, with a delay.

## Development

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest
```

134 tests, none of which touch the network. The design notes are in
`docs/superpowers/specs/`.
