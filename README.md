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

## Books

Each book lives in its own folder under `books/`:

```
books\
  Weakest Beast Tamer\
    book.toml       settings: title, author, URL pattern, phrases to remove
    01 Raw\         0001.html ...  pages exactly as downloaded
    02 Cleaned\     0001.md ...    one cleaned chapter per file
    03 Output\      Weakest Beast Tamer 1228-1274.epub ...
```

The whole `books` folder stays out of git.

Add a book from its main page on the site. The title, author, chapter URL
pattern and latest chapter are read from the page:

```powershell
python scrape.py add https://freewebnovel.com/novel/shadow-slave --name "Shadow Slave"
```

A site that doesn't publish those details can be added by hand:
`add --url "https://example.com/book/chapter-{n}" --title "Some Book"`.

Then, naming the book by its folder - any unambiguous start of the name
will do:

| Command | Does |
|---------|------|
| `status shadow` | What is downloaded, cleaned and built, and how many chapters are new on the site |
| `download shadow` | Fetches chapters not yet in `01 Raw`. Stop with Ctrl-C and run again to carry on |
| `clean shadow` | Rebuilds `02 Cleaned` from `01 Raw` and reports everything it removed |
| `review shadow` | Lists sentences that recur across many chapters, to spot junk |
| `build shadow` | Joins every cleaned chapter into an epub (`--format pdf/md/txt`, `--from`/`--to`) |
| `update shadow` | The everyday one: download what's new, clean, and build just the new chapters |
| `books` | Lists the books |

`clean` is local and quick, so re-run it whenever you change `book.toml`.
It replaces everything in `02 Cleaned`, so a hand edit there won't last -
put lasting fixes in `book.toml` as rules.

### Removing watermarks

Sites splice their name into the text in ever-changing wording, often onto
the end of a real paragraph. `remove_phrases` in `book.toml` lists regular
expressions; any *sentence* matching one is removed and the rest of its
paragraph kept. `add` starts the list with a pattern for the site's name,
and you add more:

```toml
remove_phrases = ['f[\W_]*r[\W_]*e ...', 'n0vel1st', 'Give it a power stone']
```

Matching ignores case. Use single quotes so backslashes reach the pattern
intact. Run `review` to find more, add them, and `clean` again.

### Chapter titles

Titles lose the decoration the site adds - the book's name in front, the
site's name after a `|`, and a doubled chapter number - leaving the
author's chapter name whole. To replace titles outright, put a
`titles.json` of `{"number": "title"}` in the book's folder.

## Usage

For a one-off run that doesn't need a book folder, pass everything on the
command line. Fifty numbered pages into one Markdown file:

```powershell
python scrape.py --url "https://example.com/page-{n}" --start 1 --end 50 --out book.md
```

The `{n}` is the part that changes. Leave `--end` off and it keeps going
until three pages in a row come back empty:

```powershell
python scrape.py --url "https://example.com/page-{n}" --out book.md
```

When you don't know where the series ends, stop at the first missing page
with `--max-misses 1` and let the file name itself after what was actually
collected. `{first}` and `{last}` in `--out` become the first and last page
numbers:

```powershell
python scrape.py --url "https://example.com/page-{n}" --start 1228 --max-misses 1 --out "book-{first}-{last}.epub"
```

That writes `book-1228-1264.epub` if page 1265 is the first one missing.

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

### Removing the recap at the top of a page

Serialised sources often open a new instalment by restating how the last one
ended, so the same passage lands in your document twice. Repetition can't
catch it — it appears on two pages, not most of them — and it's rarely
copied verbatim: it gets reworded and re-paragraphed on the way in.

So each page is compared, a sentence at a time, against the tail of the page
before it. Leading blocks whose every sentence turns up there are dropped,
and the walk stops at the first block that doesn't, which keeps it to the
opening of a page. Headings are stepped over rather than stopping it, so a
chapter title can't hide the recap behind it.

What went is reported:

```
Trimmed 284 repeated block(s) from the start of 139 page(s):
  page 2: ren kept his head high as he descended from the altar his parents had sold ev...
  page 3: the path home had never felt so long
```

- `--overlap-window 30` — look further back for the restated passage
  (default 15 blocks)
- `--no-trim-overlap` — keep the recap

A page that is *nothing but* a recap is left alone: that's more likely a
duplicate fetch than a page to delete, and you should see it.

**Strip the furniture first.** This runs after the two mechanisms above, and
it only ever trims from the *start* of a page. A leftover furniture line —
`Chapter 12 - The Tunnels`, a navigation strip — sits between the recap and
the top of the page and stops the walk before it begins, so nothing is
trimmed at all. If the report says nothing was trimmed but you can see
repetition, check what your pages actually start with and add a
`--strip-regex` for it. Headings are the exception: those are stepped over.

### Options

| Flag | Meaning |
|------|---------|
| `--url` | URL containing `{n}` |
| `--out` | Output file; `.md`, `.txt`, `.pdf` or `.epub`. `{first}`/`{last}` become the page range collected |
| `--start`, `--end`, `--step` | Which numbers to walk (default: from 1, by 1, no end) |
| `--selector` | CSS selector for the main text |
| `--title-selector` | CSS selector for each page's title |
| `--remove` | CSS selector to strip; repeatable |
| `--no-dedupe` | Keep blocks that repeat across pages |
| `--dedupe-threshold` | Fraction of pages a block must appear on (default 0.6) |
| `--strip-regex` | Drop any block matching this pattern; repeatable |
| `--no-trim-overlap` | Keep the recap a page opens with |
| `--overlap-window` | Blocks at the end of a page a recap may restate (default 15) |
| `--title` | Title for the finished document |
| `--titles` | JSON file of page number to title, used instead of the scraped titles |
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

284 tests, none of which touch the network. The design notes are in
`docs/superpowers/specs/`.
