# Backlog

Known issues and follow-ups that were reviewed and deliberately deferred.
Newest first. Each says what a person would notice, and where to look.

## Reader (2026-10-15, final review of branch `reader`)

- **False "moved on" banner after opening a chapter offline.** Opening a
  specific chapter while the PC cannot be reached leaves the reader's
  revision at 0, so the next save is refused and the banner says another
  device moved on, though you chose the chapter. Low impact: choosing
  "Keep reading here" fixes it. (`web/src/routes/Read.svelte`, `start`)
- **Missing-chapter fallback can pick another missing chapter.** When the
  saved chapter is gone, `resolve_position` picks the next (else previous)
  chapter number without checking it can be loaded; the reader then
  retries and shows "isn't available". Saving is held meanwhile, so the
  real place is not lost. (`scraper/web/anchor.py`, `resolve_position`)
- **`#/read/<book>/<n>` for a chapter not held, with no saved place**, opens
  chapter n (retries, then an error) instead of the first chapter.
  (`web/src/routes/Reader.svelte`, the final `open(chapter ?? list.first!)`)
- **Phase 2 seams are not yet the only places to change.** The reader also
  fetches the book's title with `api.book`, and constructs `networkSource`
  and `PositionSync` itself. For offline reading: carry the title in the
  chapter list and inject the source and sync implementations.
- **Non-ASCII digits in the chapter route** (`/chapters/²`) give 400 rather
  than 404. (`scraper/web/app.py`, `chapter`)
- **Waiting for the text face** uses `document.fonts.ready`;
  `document.fonts.load('1em "Literata Variable"')` would be deterministic.
  Restore accuracy was verified on a real book.
- **Cosmetic:** a backslash before `<` in scraped text shows literally; the
  chapter list shows no gap row before the first available chapter;
  re-clean retries give up after about 3 seconds.

## Folio web app (2026-10-15, final review of branch `web-app`)

- A stopped job is labelled "stopped" even when it finished all its work.
- Cancelling a queued "Update all" job only takes effect when its turn comes.
- Two concurrent watermark reviews can race in the review cache (KeyError).
- Non-finite numbers (`inf`) in the settings form give 500, not 422.
- Saving a watermark pattern while the book is busy shows an error though
  the pattern was saved, and allows a duplicate.
- The build preview can differ from the real build at the edges (cleaned
  chapters below a raised `start`; an emptied "files of N" box).
- A "book is busy" message is a plain toast, not linked to the job.
- Request-validation errors are not in the `{"error": ...}` shape.
- Settings writes are not fsynced before replace.
- A clean interrupted during its final write phase can leave `02 Cleaned`
  partly written (also true of Ctrl-C in the CLI).
