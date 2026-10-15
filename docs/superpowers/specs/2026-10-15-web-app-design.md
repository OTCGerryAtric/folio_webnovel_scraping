# Folio: a Web App for the Books — Design

**Date:** 2026-10-15
**Status:** Draft, for review
**Builds on:** `2026-10-14-books-and-stages-design.md`

## Purpose

The book pipeline works (add, download, clean, review, build, update),
but it is driven by remembering commands and flags, reading long blocks of
terminal output, and editing `book.toml` by hand. The watermark loop is
the worst: run `review`, copy a sentence, write a regex, `clean`, look
again.

Folio puts a polished front end on the same engine. It runs locally,
opens in a browser, and works equally from the PC, a tablet or a phone,
so the books can be updated and downloaded on whichever device is reading
them. The reader chooses the format; Folio does not assume a device.

Success looks like:

- Everything the CLI does can be done from the browser, with no flags to
  remember and no TOML to hand-edit.
- Updating a book is one click, with live per-chapter progress, and can be
  cancelled.
- Finding and removing a watermark takes seconds: see it, test a pattern
  against the whole book, save, and the book re-cleans itself.
- A built book downloads straight to the device in use, in any format.
- It looks like something worth opening: a bookshelf, not a form.
- The CLI keeps working unchanged, and the two cannot drift apart because
  they share all their logic.

Out of scope for this version, planned as v1.1: an OPDS catalogue for
reading apps, and an in-browser reader.

## Architecture

```
python scrape.py serve  ─►  FastAPI app  (scraper/web/)
                              ├─ JSON API         /api/...
                              ├─ event stream     /api/events      (SSE)
                              └─ static front end  scraper/web/static/
                                       │
                                       ▼
                         existing scraper package: stages, book, review ...
```

- **One engine.** `scraper/web/` sits beside `commands.py` and calls the
  same functions the CLI does. It contains no scraping, cleaning or
  building logic of its own.
- **Backend:** FastAPI + uvicorn. New dependencies: `fastapi`,
  `uvicorn`, `tomlkit` (comment-preserving TOML writes). Dev: `httpx`
  (for FastAPI's TestClient).
- **Front end:** Svelte 5 + TypeScript + Vite + Tailwind CSS v4, in
  `web/` at the project root. `npm run build` writes to
  `scraper/web/static/`, and that built output is committed, so Node is
  needed only to change the UI, never to run it. Fonts (Fraunces for
  display, Inter for UI) are bundled via `@fontsource` so the app works
  offline. Icons from `lucide-svelte`.

## Engine changes

Small, backward-compatible hooks so the UI can show progress and cancel.
The CLI passes none of them and behaves exactly as now.

1. `download(..., progress=None, should_stop=None)`
   - `progress(number, end, outcome)` after each chapter tried, where
     `outcome` is `"downloaded" | "not found" | "no text"`.
   - `should_stop()` is checked before each chapter; when true the loop
     ends exactly as Ctrl-C does now, keeping what was fetched.
2. `clean(..., progress=None)`: `progress(done, total)` while extracting
   raw pages, the slow part.
3. `BookInfo` gains `cover: str | None`, read from `og:image`.
4. `write_document(..., cover=None)`: when given a path to an image, the
   epub carries it as its cover (`EbookLib`'s `set_cover`), so reading
   apps show it on their shelves. Other formats ignore it.
   `build`/`build_blocks` pass the book's cover when it has one.
5. A new setting `review_ignore` (list of strings) in `DEFAULTS`:
   sentences the user has marked as the author's own habit. Both the CLI
   `review` and the web review leave them out. It is stored as normalised
   text (the key `review` already computes), so punctuation and case
   differences do not matter.
6. `Book.cover_path`: `books/<name>/cover.<ext>`, the first of
   jpg/png/webp/gif that exists.

## Backend

### Package layout

```
scraper/web/
  __init__.py
  app.py        create_app(root, get_page, fetcher_factory): routes, static files
  jobs.py       JobManager: background jobs, events, cancellation
  library.py    book summaries, site-latest cache, covers
  settings.py   reading and writing book.toml through tomlkit
  watermarks.py review rows with context, pattern testing, phrase building
  serve.py      `scrape.py serve`: uvicorn, browser launch, LAN mode, token
  static/       built front end (generated)
```

`create_app` takes the same injectable `root`, `get_page` and
`fetcher_factory` as `run_command`, so the tests drive it with a temp
`books/` folder and fake network, exactly as `test_commands.py` does.

### API

Books are addressed by folder name, URL-encoded. Every `{book}` is
resolved through `list_books(root)` by exact name, so a request can never
reach outside `books/`.

| Method & path | Does |
|---|---|
| `GET /api/books` | Summary of every book: name, title, author, counts, ranges, outputs, cover URL, `build_every`, cached site latest if known, running job id |
| `POST /api/books/preview` `{url}` | Fetches a book page and returns what `add` would create: title, author, status, latest, url template, cover, site phrase, suggested folder name. Writes nothing |
| `POST /api/books` `{url, name}` or `{url_template, title, name}` | Creates the book (as `add`), saves its cover |
| `GET /api/books/{book}` | Full detail: summary plus chapter map (see below) and recent activity |
| `GET /api/books/{book}/site` | Checks the site's latest chapter (cached 15 minutes per book; `?fresh=1` bypasses) |
| `POST /api/books/{book}/jobs` `{kind, ...}` | Starts `download`, `clean`, `build` or `update`; returns the job. 409 if the book already has a job running |
| `POST /api/update-all` | Queues `update` for every book with a source, one after another |
| `GET /api/jobs` | Running and recent jobs |
| `POST /api/jobs/{id}/cancel` | Asks a job to stop |
| `GET /api/events` | SSE stream of every job event (one connection per browser tab) |
| `GET /api/books/{book}/review?min=4` | Repeated sentences, each with count, first chapter, two context snippets, and whether an existing phrase already matches it |
| `POST /api/books/{book}/review/test` `{pattern}` | Compiles the pattern and counts the sentences it would remove across the cleaned book, returning up to 20 highlighted examples. Rejects patterns that do not compile or that match more than 2% of sentences, with a clear message |
| `POST /api/books/{book}/review/phrase` `{sentence}` | Suggests a pattern for a sentence: escaped, with flexible whitespace and punctuation |
| `POST /api/books/{book}/review/ignore` `{sentence}` | Adds to `review_ignore` |
| `GET /api/books/{book}/settings` | All known keys with value, default and whether set; the raw `book.toml` text |
| `PUT /api/books/{book}/settings` `{values}` or `{raw}` | Validates through `build_settings`, then writes with tomlkit, keeping comments and order. Invalid input changes nothing and returns the error |
| `GET /api/books/{book}/files/{name}` | Downloads a built file from `03 Output` (name must be one of `book.outputs()`) |
| `DELETE /api/books/{book}/files/{name}` | Deletes a built file |
| `GET /api/books/{book}/cover` | The cover image; 404 if none (the front end draws one) |

Saving a watermark pattern is `PUT settings` with the new
`remove_phrases` followed by a `clean` job; the front end does both from
one button.

### Chapter map

`GET /api/books/{book}` includes the state of every chapter from the
book's `start` to `max(held, site latest)`, run-length encoded so a
2,000-chapter book stays small:

```json
"map": [["cleaned", 1, 1228], ["raw", 1229, 1264], ["missing", 1265, 1274]]
```

States: `cleaned` (raw and cleaned), `raw` (downloaded, not yet cleaned),
`missing` (a gap below the newest held), `new` (above the newest held, up
to the site's latest). It also includes each built file with its chapter
range parsed from its name, so blocks can be shown against the map.

### Jobs

- A job runs in a worker thread. `JobManager` keeps one running job per
  book; `update-all` jobs run strictly one at a time, since they share the
  same site.
- A job's `report` callback (the strings the stages already produce)
  becomes `log` events. The new `progress` hooks become `progress`
  events `{done, total, label}`. The end is a `done` event with a summary
  (`{fetched, cleaned, removed, files}` as relevant) or an `error` event
  with the message the CLI would print.
- Events carry the job id and book name. Each job keeps its last 500 log
  lines in memory, so a tab that connects mid-job can catch up via
  `GET /api/jobs`.
- Finished jobs are appended to `books/<name>/.activity.jsonl` (kind,
  started, finished, outcome, summary), keeping the last 100. The book
  page shows these as the activity history, which survives restarts.
- Cancelling sets the job's stop flag. Download checks it between
  chapters; clean and build are quick and run to completion.
- A file that cannot be written (an epub open in a reader) ends the job
  with the same error message the CLI gives.

### Settings writes

`tomlkit` loads `book.toml`, changes only the keys whose values changed,
removes a key when the user clears its field (so its default applies),
and writes the file back, so comments like the ones explaining `remove_phrases` are
kept. Before writing, the merged values go through `build_settings` (and
each regex through `re.compile`); a failure returns 422 with the message,
and the file is untouched. Raw mode validates the whole text the same way.

### Covers

On `add`, the cover from `og:image` is downloaded to
`books/<name>/cover.<ext>`. For a book without one, `GET /api/books`
schedules one background attempt from its `source` page per server run.
No cover is fine: the front end draws a typographic one.

### Serving

- `python scrape.py serve` binds `127.0.0.1:8765` (first free port from
  there), opens the default browser, and logs the URL.
- `python scrape.py serve --lan` binds `0.0.0.0` and generates a random
  access key. It prints a URL containing the key, plus a QR code in the
  terminal (via `qrcode`, an optional dependency; without it, just the
  URL). The first visit with `?key=` sets a cookie. Every `/api` request
  from a non-loopback address without the cookie gets 401. Loopback is
  always allowed.
- `BookScraper.cmd` in the project root starts `serve` with the venv's
  Python, for pinning to the taskbar.
- `serve` is added to `COMMANDS`, so `scrape.py serve` routes there.

## Front end

### Look

A dark-first "library at night" theme with a warm-paper light theme,
following the system setting with a manual toggle. Ink-navy surfaces, an
amber accent, and Fraunces for titles give it a literary feel; Inter for
interface text. Motion is restrained: covers lift on hover, progress
animates smoothly, panels slide. It is fully responsive. On a phone the
shelf becomes two columns and the book page tabs become a bottom bar.

**Typographic covers:** a book without an image gets a generated cover
(SVG): a gradient whose hues come from a hash of the title, the title set
in Fraunces, the author underneath, a thin rule. Every book therefore
looks deliberate on the shelf.

### Screens

**Library (home)**
- A grid of covers. Each card shows title, author, a slim three-part bar
  (cleaned / downloaded / missing against the latest known), and an
  amber "12 new" badge once the background site check comes back.
- The header has an **Update all** button and a theme toggle.
- The last card is **Add a book**.
- An empty library shows a friendly welcome and a URL box.

**Add a book (dialog)**
- Paste a URL. Folio previews the book: cover, title, author, status,
  chapters on the site, and the detected chapter URL pattern. The folder
  name is pre-filled and editable.
- **Add** creates it, with an optional checked "Download chapters now".
- A "site without book details?" link switches to manual mode
  (URL template and title).

**Book page**

A hero with a large cover, title, author, source link, and key numbers
(chapters held, latest on site, last updated). Primary action:
**Update** (download new, clean, build new). A menu holds Download, Clean
and Build individually. Tabs below:

1. **Overview: chapter map.** Every chapter as a small cell in a dense
   grid, coloured by state (cleaned, raw, missing, new), with built
   blocks outlined as bands. Hovering or tapping a run shows its range.
   This turns "what have I got?" into a glance. Below it, recent
   activity.
2. **Watermarks.** The repeated sentences, ranked by how many chapters
   they appear in, each with a context snippet and three actions:
   - **Remove**: opens the pattern editor pre-filled with the suggested
     pattern.
   - **Keep**: marks it as the author's own (`review_ignore`); it
     disappears from the list.
   - **Already removed**: a dimmed label when a current phrase matches
     it.

   The pattern editor tests as you type (debounced), showing "would
   remove 143 sentences in 141 chapters" and highlighted examples, and
   refuses over-broad patterns. **Save & re-clean** writes the phrase and
   runs clean, after which the list refreshes. The current
   `remove_phrases` are listed below with delete buttons.
3. **Files.**
   - **Build panel:** a format segmented control (EPUB, PDF, Markdown,
     Text); a range choice (whole book, in blocks of N, or a custom
     from–to); and a live preview of the file names that will be
     produced, using the same block arithmetic as `build_blocks`. Then
     **Build**.
   - **Built files:** name, range, size and date, with **Download** (to
     whichever device is in use) and delete.
4. **Settings.** A form over `book.toml` in groups: Book (title, author,
   source), Chapters (URL template, start, step), Extraction (content,
   title and remove selectors), Cleaning (dedupe and threshold, strip
   patterns, trim overlap and window), Building (`build_every`), and
   Politeness (delay, retries, timeout). Each field shows its default as
   placeholder text. An **Advanced** toggle swaps the form for the raw
   TOML with validation on save. After a save that affects cleaning,
   Folio offers to re-clean.

**Activity dock**

A compact, always-present dock in the bottom corner. It shows running
jobs with a progress bar, current chapter and an ETA; expands to the live
log; and offers cancel. A finished job collapses to a toast with its
summary ("Downloaded 10 · Cleaned 1,274 · Built Shadow Slave
1001-1274.epub") and a Download button when it built something.

### Front-end structure

```
web/
  src/
    lib/api.ts        typed fetch wrapper for every endpoint
    lib/events.ts     one shared EventSource, Svelte store of jobs
    lib/blocks.ts     block arithmetic for the build preview (mirrors build_blocks)
    lib/cover.ts      title-hash palette for generated covers
    lib/ranges.ts     formatting ranges and counts
    components/       Cover, ChapterMap, ProgressBar, Dock, Dialog, Tabs, ...
    routes/           Library, Book (with tab components), via a tiny hash router
  vite.config.ts      build into ../scraper/web/static
```

A hash router (`#/`, `#/book/Shadow%20Slave/watermarks`) keeps the
backend's static serving trivial.

## Error handling

- Every API error returns `{"error": "<message>"}` with the message the
  CLI would print (the same `ValueError` text), shown in the UI as an
  inline banner or toast. Nothing fails silently.
- If the site can't be reached, the "new" badge is simply absent and the
  book page says "site not reachable"; it is never an error state.
- If the server stops, the front end shows a "reconnecting" pill while the
  SSE connection is down and recovers by itself.
- A job's 409 (book busy) is shown as "already running", with a link to
  the job in the dock.

## Testing

- **Engine hooks:** unit tests for `progress`/`should_stop` in `download`,
  `progress` in `clean`, `cover` in `BookInfo`, the epub cover, and
  `review_ignore`, in the existing test files.
- **Backend:** `tests/web/` using FastAPI's `TestClient` against a temp
  `books/` folder with fake `get_page`/fetchers. This covers each
  endpoint's success and error paths; job lifecycle (start, progress
  events, done, cancel, 409); settings round-trip preserving comments; the
  watermark test's over-broad rejection; path safety for book and file
  names; and LAN key enforcement.
- **Front end:** Vitest for `blocks.ts` (must agree with `build_blocks`
  on the same cases), `ranges.ts` and `cover.ts`. `svelte-check` for
  types.
- **Manual:** run `serve` against the real books and check, at desktop
  and phone widths: add, update with cancel, a watermark edit, a block
  build, and downloading a file.

## Delivery

1. Engine hooks, with tests.
2. Backend: jobs, library, settings, watermarks, files, serve, with tests.
3. Front end: scaffold and theme, library, add dialog, book page tabs,
   dock.
4. Build into `static/`, add `BookScraper.cmd`, and README section.

v1.1 (separate spec): OPDS catalogue at `/opds` so reading apps can
browse and download over Wi-Fi, and an in-browser reader over the
cleaned chapters with remembered position.
