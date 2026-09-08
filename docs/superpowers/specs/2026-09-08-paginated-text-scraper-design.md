# Paginated Text Scraper — Design

**Date:** 2026-09-08
**Status:** Approved

## Purpose

Fetch a sequence of web pages whose URLs differ only by an incrementing
number, extract the main text from each while preserving its formatting,
and join the results into a single document.

The tool is source-agnostic. It carries no knowledge of any particular
site; every site-specific detail is supplied by the user at the command
line or in an optional config file. The user is responsible for having
the right to copy whatever they point it at.

## Scope

In scope:

- URL templates with a `{n}` placeholder
- Bounded ranges and open-ended runs that stop on repeated failure
- Text extraction via an explicit CSS selector, or automatic detection
- Formatting preserved as Markdown: paragraphs, headings, emphasis,
  blockquotes, line breaks, lists
- Output as Markdown, plain text, PDF, or EPUB
- Removal of site furniture: blocks repeating across most pages, plus
  user-supplied patterns for furniture that varies per page
- Polite fetching: rate limiting, retry with backoff, on-disk cache

Out of scope:

- JavaScript-rendered pages (no headless browser)
- Authentication, cookies, or any bypass of access controls
- Concurrency — requests are sequential by design, to stay polite

## Modules

Each module has one responsibility and is testable in isolation.

### `scraper/fetch.py`

Sequential HTTP with a descriptive user-agent. Sleeps `delay` seconds
between requests. Retries 429 and 5xx with exponential backoff, honouring
`Retry-After` when present. Caches every successful response body to
`.cache/<slug>/<n>.html`; a cached page is returned without a network
call unless `refresh` is set. Knows nothing about HTML structure.

Returns `FetchResult(number, url, html, from_cache)` or `None` on a 404.

### `scraper/extract.py`

Pure function of HTML text. No network, no filesystem.

Selects the content root: the node matching `content_selector` if given,
otherwise the block with the greatest text density found by walking
candidate containers. Strips `remove_selectors` plus `script`, `style`,
`nav`, `header`, `footer`, `aside`, and elements hidden inline.

Walks the resulting tree and emits Markdown:

| HTML | Markdown |
|------|----------|
| `p` | paragraph separated by a blank line |
| `h1`–`h6` | `#`–`######` |
| `em`, `i` | `*text*` |
| `strong`, `b` | `**text**` |
| `br` | hard line break |
| `blockquote` | `> ` prefix |
| `ul`/`ol` + `li` | `- ` / `1. ` |
| `hr` | `---` |

Markdown metacharacters in text nodes are escaped. Whitespace is
collapsed within a paragraph but never across paragraphs. Emphasis
nesting is preserved.

Returns `Page(number, title, body_markdown)`; an empty body signals a
miss to the caller.

### `scraper/assemble.py`

Takes an ordered list of `Page` and writes one file. Format is chosen by
the output extension: `.md`, `.txt`, `.pdf`, `.epub`.

- Markdown — a `#` title per page, blank line separated
- Plain text — emphasis markers stripped, headings underlined
- EPUB — one chapter per page, with a generated table of contents
- PDF — A4, 11pt serif, each page starting a fresh sheet under its own
  heading, page numbers in the footer, and an outline bookmark per page.
  A title page when a document title is given.

PDF rendering uses reportlab, chosen over weasyprint because it installs
from pip alone: weasyprint needs the GTK/Pango runtime, which is a
meaningful obstacle on Windows for a marginal gain in typography.

The built-in Type 1 fonts cover Latin text including accented characters
and typographic punctuation. Non-Latin scripts would need an embedded
font; that is deliberately not carried in the repo until a source needs it.

### `scraper/boilerplate.py`

Removes site furniture after extraction, when the whole run is visible at
once. Pure functions over a list of `Page`.

Two mechanisms, both operating on whole blocks:

- **Repetition.** A block appearing on `threshold` (default 0.6) or more of
  the pages is furniture, not prose. Prose is virtually never
  byte-identical across most of a run, whereas navigation and
  reader-settings widgets are identical every time. Comparison is on
  whitespace-collapsed text, so trivial layout differences still match.
  Requires at least 3 pages: with two, a coincidence is not evidence.
- **Patterns.** Furniture that varies per page — a heading carrying the
  page number — cannot be caught by repetition, so the user supplies
  regular expressions. Matched with `re.MULTILINE` so `^` anchors to a
  line start inside a block.

Returns the cleaned pages alongside a list of `Removal(text, pages,
reason)`. The caller reports these: text disappearing silently is how a
tool loses the user's trust. Summary text is deliberately ASCII, since it
goes to a console that may be in a legacy code page.

A page left empty is kept rather than dropped, so an over-aggressive
threshold is visible rather than silent. The CLI warns when this happens.

### `scraper/config.py`

Loads an optional TOML file via stdlib `tomllib` and merges it with CLI
arguments. CLI arguments win. Validates that a URL template is present
and contains `{n}`.

### `scraper/run.py`

The run loop: walk the numbers, fetch, extract, attach the number, collect.
Separated from argument parsing so it can be driven by a stub fetcher in
the tests.

An open-ended run stops once `max_misses` pages in a row are missing or
empty. A bounded run reports gaps and carries on to its end. A keyboard
interrupt returns whatever was collected rather than discarding it.

### `scrape.py`

Argument parsing and the entry point. Every setting is available as a flag,
so the tool is fully usable with no config file:

    --url TEMPLATE     URL containing {n}
    --start N          first number (default 1)
    --end N            last number; omit to run until repeated failure
    --step N           increment (default 1)
    --out PATH         output file; extension picks the format
    --selector CSS     content selector
    --title-selector CSS
    --remove CSS       repeatable
    --delay SECONDS    default 1.5
    --max-misses N     consecutive failures before stopping (default 3)
    --refresh          ignore the cache
    --no-dedupe        keep blocks repeating across pages
    --dedupe-threshold FRACTION   default 0.6
    --strip-regex REGEX           repeatable
    --site PATH        optional TOML config
    --verbose

Progress is reported to stderr per page. A run that ends with zero pages
exits non-zero.

## Error handling

- 404 or empty extraction counts as a miss; `max_misses` consecutive
  misses ends an open-ended run. Within a bounded range, misses are
  logged and skipped.
- Connection errors and timeouts retry up to 3 times, then count as a
  miss.
- An invalid selector, an unwritable output path, or a template without
  `{n}` fails immediately with a clear message.
- Ctrl-C stops the run and still writes what was collected.

## Testing

pytest, no network access anywhere in the suite.

- `extract.py` — hand-written HTML fixtures: nested emphasis, headings,
  lists, blockquotes, wrapper-div noise, entity escaping, density-based
  auto-detection
- `fetch.py` — mocked transport for cache hits, cache writes, retry and
  backoff, `Retry-After`, 404 handling
- `assemble.py` — synthetic pages through each writer; PDFs are
  read back with pypdf so the assertions are about what landed on the page
- `boilerplate.py` — threshold edges either side of the default,
  whitespace-insensitive matching, too-few-pages, reporting, patterns
- `config.py` — merge precedence and validation failures
- `scrape.py` — the run loop against a stubbed fetcher: bounded range,
  open-ended stop, miss tolerance
