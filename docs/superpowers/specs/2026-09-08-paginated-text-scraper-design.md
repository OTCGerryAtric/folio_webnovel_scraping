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
- Output as Markdown, plain text, or EPUB
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
the output extension: `.md`, `.txt`, `.epub`.

- Markdown — a `#` title per page, blank line separated
- Plain text — emphasis markers stripped, headings underlined
- EPUB — one chapter per page, with a generated table of contents

### `scraper/config.py`

Loads an optional TOML file via stdlib `tomllib` and merges it with CLI
arguments. CLI arguments win. Validates that a URL template is present
and contains `{n}`.

### `scrape.py`

Argument parsing and the run loop. Every setting is available as a flag,
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
- `assemble.py` — synthetic pages through each of the three writers
- `config.py` — merge precedence and validation failures
- `scrape.py` — the run loop against a stubbed fetcher: bounded range,
  open-ended stop, miss tolerance
