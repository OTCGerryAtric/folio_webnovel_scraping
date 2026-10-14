# Books and Stages — Design

**Date:** 2026-10-14
**Status:** Draft, for review
**Builds on:** `2026-09-08-paginated-text-scraper-design.md`

## Purpose

The tool currently serves one book whose files are spread across the
project root: a long command kept in `RUNNING.md`, a `titles.json`, batch
outputs, and a cache folder named after a hash of the URL. Moving to a new
book, or carrying on with the current one, means editing that command by
hand.

This change makes the book the unit of work. Each book lives in its own
folder, is added from its page on the source site, and is processed in
three separate stages - download, clean, build - so the text can be
inspected and corrected between fetching it and publishing it.

Success looks like:

- Adding a book is one command given the book's page URL.
- Carrying on with a book is one short command; nobody works out `--start`.
- Books never share or disturb each other's files.
- Site junk (watermark sentences, title decoration) is removed and reported.
- The existing book moves across without re-fetching the 544 pages
  already downloaded.

## Layout

```
books/
  Weakest Beast Tamer/
    book.toml      settings for this book
    01 Raw/        0001.html ...  pages as the site sent them
    02 Cleaned/    0001.md ...    cleaned chapters
    03 Output/     built epub / pdf / md
```

The folder name is a readable name of the user's choosing, spaces
allowed; the stage folders are numbered so Explorer lists them in the
order the work flows. The full title from the site lives in `book.toml`
and goes on the finished document. The whole of `books/` is ignored by
git: books are personal material, not part of the tool, and never go to
GitHub. `sites/example.toml` remains the tracked example of a settings
file.

A book is named on the command line by its folder name, in quotes when it
has spaces. Any unambiguous, case-insensitive start of the name also
works, so `weakest` finds `Weakest Beast Tamer`. An ambiguous or unknown
name lists the books that exist.

Page files are zero-padded to four digits so they sort correctly in
Explorer. Wider numbers are written unpadded, which still sorts correctly
by number in the tool itself.

## Commands

`scrape.py` gains subcommands. A book is named by its folder name.

| Command | Does |
|---------|------|
| `add <book-page-url> [--name NAME]` | Creates `books/<name>/` and its `book.toml` from the book page |
| `status <book>` | What is downloaded, cleaned and built; what is new on the site |
| `download <book>` | Fetches raw pages not already in `01 Raw` |
| `clean <book>` | Rebuilds `02 Cleaned` from `01 Raw`, reporting what it removed |
| `review <book>` | Lists sentences repeated across many chapters |
| `build <book>` | Joins `02 Cleaned` into one file in `03 Output` |
| `update <book>` | download + clean + build, for the chapters that are new |
| `books` | Lists the books and where each stands |

The existing flag-driven mode (`--url ... --out ...`) stays as it is, for
one-off runs that don't warrant a book folder.

## `add` - reading the book page

Many novel sites - freewebnovel among them - publish the book's details as
`og:novel:*` meta tags. Confirmed on two books:

| Tag | Used for |
|-----|----------|
| `og:novel:novel_name` | `title` |
| `og:novel:author` | `author` |
| `og:novel:read_url` | `url_template`: the chapter-1 URL with its number replaced by `{n}` |
| `og:novel:lastest_chapter_url` | latest chapter (the misspelling is the site's) |
| `og:novel:status` | ongoing / completed |
| `og:novel:update_time` | when the site last added a chapter |

`add` makes one request, writes `book.toml`, and reports title, author,
status, and chapter count. For sites without these tags, `add` takes
`--url` with a `{n}` template and `--title` instead.

The folder is named by `--name`, or the site's title when it is not
given. An existing folder is used if it has no `book.toml` yet, so a
folder made by hand in Explorer is fine; `add` refuses to overwrite an
existing `book.toml`. Missing stage folders are created.

## `book.toml`

Every existing setting is still valid here. New keys:

| Key | Meaning |
|-----|---------|
| `title`, `author` | From the book page |
| `source` | The book page URL; used by `status` and `download` to find the latest chapter |
| `remove_phrases` | Regexes; a *sentence* matching any of them is removed (see Clean) |

`add` seeds `remove_phrases` with a pattern for the site's own name, built
from the book page's host with optional spaces and punctuation allowed
between its letters, so `freewebnovel` also matches "Free Web Novel" and
"freewebnovel.com".

## `download`

Fetches every chapter from `start` to the latest chapter that is not
already in `01 Raw`. The latest chapter comes from the book page when
`source` is set; otherwise the run stops at `max_misses` consecutive
misses, as now. Reuses `Fetcher` unchanged apart from where it writes:
delay, retries, backoff and Ctrl-C behaviour are as before.

`--start`/`--end` narrow the range; `--refresh` re-fetches pages already
held.

## `clean`

Reads every page in `01 Raw` in order and writes `02 Cleaned/NNNN.md`, each
starting with a `# <title>` line followed by the body. It rebuilds the
whole of `02 Cleaned` each time - this is local and takes seconds - so a change
of rules always applies everywhere.

Steps, in order:

1. **Extract** - as now (`extract_page`).
2. **Remove phrases** - new. Each block is split into sentences; a sentence
   matching any `remove_phrases` pattern is dropped and the rest of the
   block kept. A block left empty is dropped. This is what handles
   watermarks: 40 of the 119 in the current book are attached to the end of
   a story paragraph, so dropping whole blocks (as `strip_patterns` does)
   would delete story text.
3. **Strip furniture** - as now (`clean_pages`: repetition and `strip_patterns`).
4. **Trim recaps** - as now (`trim_overlap`).
5. **Tidy titles** - new; see below.

Every removal is reported, as now. Steps 3 and 4 compare chapters with
each other, which is why clean works over the whole book rather than
chapter by chapter.

**Hand edits in `02 Cleaned` are overwritten by the next clean.** Fixes that
should last go in `book.toml` as rules. (Protecting hand-edited chapters
is possible later if it turns out to be needed.)

### Titles

Scraped titles carry decoration from the page's `<title>`:

```
Weakest Beast Tamer Gets All SSS Dragons - Chapter 1 - 1 - Beast Tamer Ren Patinder | Free Web Novel
```

Tidying removes, in order:

- a leading `<book title> - ` (the title is known from `book.toml`)
- a trailing ` | <anything>` (the site name)
- a doubled chapter number: `Chapter 1 - 1 - X` becomes `Chapter 1 - X`

Result: `Chapter 1 - Beast Tamer Ren Patinder`. The author's own chapter
name is otherwise kept whole, however long.

If the book folder holds a `titles.json`, its titles override these, as
`--titles` does now.

## `review`

Prints sentences that appear in at least 4 chapters, most frequent first,
with the chapter each first appears in. Repetition alone cannot separate
junk from an author's habits ("Ren shook his head." recurs in 18
chapters), so this is a report to read, not an automatic removal. Anything
unwanted goes into `remove_phrases` and `clean` is run again.

## `build`

Joins chapters from `02 Cleaned` into `03 Output/<name> <first>-<last>.<format>`.
Format defaults to epub; `--format` chooses md, txt or pdf. With no range
it builds every cleaned chapter; `--from`/`--to` narrow it. The document
title is the book's title. Writers in `assemble.py` are unchanged.

## `update`

The everyday command: download what is new, clean, and build a batch file
of just the newly downloaded chapters. *[Decision for review: batch of new
chapters by default, with `build` available for the whole book.]*

## `status`

```
Weakest Beast Tamer
  Weakest Beast Tamer Gets All SSS Dragons, by Dagzo (ongoing)
  downloaded  1-500, 1228-1271      missing 501-1227
  cleaned     1-500, 1228-1271
  site        latest 1274, 3 new    (checked just now)
```

One request to the book page; `--offline` skips it.

## Moving the current book across

A one-off step in the implementation, not a feature:

1. `add` the book from its page into the existing `books/Weakest Beast Tamer`
   folder (already created, with its three empty stage folders).
2. Copy the 544 pages from the two `.cache/freewebnovel.com-*` folders into
   `01 Raw`, renamed to the padded form.
3. Add `remove_phrases` for this book: the site name, `n0vel1st`, and the
   author's sign-off notes ("Give it a power stone!" and the lines around
   it, 36 chapters). *[Decision for review: remove the author's notes.]*
4. `download` the 730 missing chapters (501-1227, 1272-1274): about 20-25
   minutes at the polite delay.
5. The existing epubs in the project root move to `03 Output`.
   `titles.json` is not carried over: cleaned site titles match it except
   for its "(5th E)" tag. `RUNNING.md` is replaced by the README.

## Modules

| Module | Change |
|--------|--------|
| `scraper/book.py` | new - a book folder: paths, load/save `book.toml`, finding a book by name, which chapters each stage folder holds |
| `scraper/bookpage.py` | new - parse `og:novel:*` tags from HTML; pure |
| `scraper/phrases.py` | new - sentence-level phrase removal; pure |
| `scraper/titles.py` | new - title tidying; pure |
| `scraper/review.py` | new - repeated-sentence report; pure |
| `scraper/stages.py` | new - download / clean / build / update, driven by a `Book` |
| `scraper/fetch.py` | page file naming becomes a parameter |
| `scraper/config.py` | knows the new keys |
| `scrape.py` | subcommands; existing flag mode unchanged |

`extract`, `boilerplate`, `overlap`, `assemble` and `retitle` are reused
as they are.

## Out of scope

- Finding the latest chapter on sites without `og:novel` tags by probing
  (doubling then bisecting). Download already stops at the first misses.
- Protecting hand-edited chapters from being overwritten by `clean`.
- Running several books at once.

## Testing

pytest, no network, as now.

- `bookpage` - meta-tag parsing against the two real book pages saved as
  fixtures; a page with no tags
- `phrases` - a watermark alone, a watermark attached to a story sentence,
  obfuscated spellings, a block emptied
- `titles` - each decoration on its own and together; a title with none
- `review` - counts per chapter, not per occurrence; the threshold
- `book` - folder creation, chapter discovery, refusing to overwrite
- `stages` - each stage against a temporary book folder and a stub fetcher;
  `update` builds only the new chapters
- CLI - each subcommand's happy path and its main error
