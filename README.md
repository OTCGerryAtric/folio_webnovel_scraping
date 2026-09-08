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

The output format follows the extension — `.md`, `.txt` or `.epub`:

```powershell
python scrape.py --url "https://example.com/page-{n}" --end 20 --out book.epub
```

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

### Options

| Flag | Meaning |
|------|---------|
| `--url` | URL containing `{n}` |
| `--out` | Output file; extension picks the format |
| `--start`, `--end`, `--step` | Which numbers to walk (default: from 1, by 1, no end) |
| `--selector` | CSS selector for the main text |
| `--title-selector` | CSS selector for each page's title |
| `--remove` | CSS selector to strip; repeatable |
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

89 tests, none of which touch the network. The design notes are in
`docs/superpowers/specs/`.
