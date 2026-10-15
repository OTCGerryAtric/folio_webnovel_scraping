# Folio Reader — Design

**Date:** 2026-10-15
**Status:** Approved and implemented (branch `reader`). Where the build
refined this design, see "As built" at the end.
**Builds on:** `2026-10-15-web-app-design.md` (Folio)

## Purpose

Folio builds books well, but reading them means downloading a file and
opening another app. The reader lets you read any book in Folio itself,
on the PC, phone or tablet, and pick up exactly where you stopped on
whichever device is in your hand.

Phase 1 (this spec) is online: devices read from Folio on the PC, at home
or over a private network such as Tailscale, and your place is kept on
the PC. Phase 2 (offline reading) is not built here, but this design
keeps the parts it will need separate, so Phase 2 adds to the reader
rather than rebuilding it. Its requirements are recorded at the end.

The priority is excellent reading ergonomics and reliable progress. Where
a choice trades simplicity against features, this spec picks simplicity
and lists the trade-off.

### Acceptance criteria

1. Any book with at least one cleaned chapter can be read, whether or not
   anything has been built, and with gaps in its chapters.
2. Reading text looks like a well-set book on a phone at 360px wide and on a
   desktop: a comfortable measure, a serif text face, and adjustable size,
   spacing, width and theme. The page never scrolls sideways.
3. Closing the reader on one device and opening the same book on another
   resumes at the same paragraph, within a screenful, without asking -
   unless the second device had its own, different place (criterion 5).
4. A browser tab left open for days cannot overwrite newer progress made
   on another device: its save is rejected and it offers a choice.
5. When this device's last place differs from the place saved by another
   device, the reader asks which to use, saying where each is and when it
   was saved. It never jumps silently.
6. After a re-clean changes a chapter, the saved place still lands on the
   same passage when that passage survives, and on a sensible nearby point
   when it does not, and says so.
7. Chapter text is shown as escaped text: markup in a scraped page cannot
   run in the reader.
8. Every reader endpoint keeps Folio's protections: the LAN access key,
   the list of allowed host names, and the refusal of changes from other
   sites.
9. The CLI and existing Folio behaviour are unchanged.

## Key decisions

| Decision | Choice | Why |
|---|---|---|
| Layout | Continuous scroll within a chapter; one chapter at a time | Scrolling is the most robust way to show reflowable text on every screen; pagination is a lot of layout work and its "page" is not a stable position. |
| Unit of position | Chapter, paragraph index, offset within the paragraph, text anchor, content version | Survives text-size changes and different screens; can be recovered after a re-clean. A scroll percentage cannot. |
| Where positions live | `books/<name>/reading.json` on the PC | One source of truth, beside the book, with no hosting. |
| Conflicts | Optimistic versioning: a save names the revision it was based on; a stale one is refused | Prevents silent overwrites without locks or a server-side merge. |
| Two devices disagree | The person chooses, with both places described | Re-reading a chapter on purpose is legitimate; neither "latest wins" nor "furthest wins" is always right. |
| Rendering | The server turns each cleaned paragraph into escaped HTML with the existing epub renderer | One renderer for epub and reader, already escaping; the browser does no markdown parsing. |
| Reader settings | Per device, in the browser | Text size is a property of the screen, not the book. |
| Live sync between open devices | Not pushed; checked on save, on returning to the tab, and on opening | Covers stale tabs reliably without new event types. |

## The reading position

```json
{
  "chapter": 1240,
  "paragraph": 17,
  "offset": 0.4,
  "anchor": "the black knight remained motionless for several minutes silently",
  "paragraphs": 38,
  "version": "3f9c2a1b7e04",
  "device": "d-8f2k1q",
  "device_name": "iPhone · Safari",
  "saved_at": "2026-10-15T21:04:11Z"
}
```

- `chapter`: the chapter number.
- `paragraph`: the 0-based index of the paragraph at the top of the
  reading area. Paragraphs are the chapter body's non-empty blocks,
  separated by blank lines, exactly as the cleaned file stores them. The
  `# title` line is not a paragraph.
- `offset`: how far down that paragraph the top of the reading area is,
  from 0 to 1. This puts long paragraphs back within a line or two.
- `anchor`: the paragraph's first 12 words, normalised the way `review`
  compares sentences (lower case, punctuation as spaces). It is used to find
  the passage again after a re-clean.
- `paragraphs`: how many paragraphs the chapter had when saved, for
  proportional recovery.
- `version`: the first 12 hex digits of the SHA-1 of the chapter file's
  text. Any re-clean that changes the chapter changes it.
- `device`, `device_name`: which device saved it (below).
- `saved_at`: stamped by the server when it accepts the save, never taken
  from the device, so a device with a wrong clock cannot mislead the
  choice prompt.

### Recovery after a re-clean

When a saved position is opened, the server resolves it against the
chapter as it is now. This is one pure function, `resolve_position`:

1. **The chapter is unchanged** (`version` matches): use it as saved.
2. **The chapter changed** but its anchor is found: first look at the saved
   paragraph index, then outwards up to 25 paragraphs either way. A match
   is a paragraph whose normalised opening starts with the anchor; failing
   that, one whose first 12 words share at least 75% of the anchor's
   words. Use that paragraph and keep the offset. `recovered: "anchor"`.
3. **The anchor is not found:** take the same proportion of the way
   through the chapter (`paragraph / paragraphs × new count`), with offset
   0. `recovered: "proportional"`.
4. **The chapter no longer exists** (removed by the rules, or its raw page
   deleted): open the next available cleaned chapter after it, or failing
   that the one before, at its start. `recovered: "moved"`.

The reader shows a quiet note whenever `recovered` is not `"exact"`: "This
chapter has changed since you left it - you're at the closest point." or
"Chapter 1240 isn't available - opened chapter 1241."

## Synchronisation

### Storage

`books/<name>/reading.json`:

```json
{ "revision": 42, "position": { ... } }
```

- It is written atomically (temporary file, then replace), under a lock
  per book, so concurrent saves from several devices are serialised.
- `revision` starts at 0 and increases by one on every accepted save.
- A missing file means revision 0 and no position.
- An unreadable file is treated as missing and replaced by the next save,
  with a warning in the server log: a corrupt place must not lock the book.

### The protocol

- `GET /api/books/{book}/position` returns `{revision, position}`.
- `PUT /api/books/{book}/position` with `{base_revision, position}`:
  - **`base_revision` equals the stored revision:** the save is accepted;
    `revision` + 1 is returned with the position.
  - **Otherwise:** 409 Conflict, with the stored `{revision, position}`.
    Nothing is written.

### Devices

Each browser generates a random device id the first time it opens the
reader, keeps it in its own storage, and derives a readable name from the
user agent ("iPhone · Safari", "Windows · Edge"). The person can rename it
in reader settings. Device ids identify, they do not authenticate: access
control stays with the LAN key (see Security).

The browser also remembers, per book, the last position *this device*
saved (`lastOwn`). It is used only to decide whether to ask.

### Behaviour

**On opening a book** (from Continue reading, or the book page):

1. GET the position.
2. If there is no stored position, start at the first available chapter.
3. If the stored position was saved by this device, or this device has no
   `lastOwn` for the book, go to the stored position. No question.
4. Otherwise another device has saved since this one last did. If this
   device's `lastOwn` is within 3 paragraphs of the stored position, go
   there without asking. If not, ask:
   > **Where would you like to continue?**
   > - Chapter 1,240, near "The Black Knight remained…" — *iPhone · Safari, 2 hours ago*
   > - Chapter 1,198, near "Sunny raised an eyebrow…" — *this device, yesterday*

Opening a specific chapter (from the chapter list or the chapter map) is
itself an explicit choice. It opens that chapter at its start, and the
next save moves the stored position there.

**While reading:**

- The position is saved 2 seconds after scrolling stops, and immediately
  when the tab is hidden or closed (a `keepalive` request), when the chapter
  changes, and before the reader closes.
- The tab tracks the revision it last saw.
- A 409 means another device has saved since. The tab does not retry.
  It shows a banner:
  > Your iPhone has moved on to chapter 1,262. **Go there** · **Keep reading here**

  "Keep reading here" saves this position against the new revision (an
  explicit overwrite); "Go there" moves this tab.
- When a tab becomes visible again, it fetches the position. If the stored
  revision is newer and was saved by another device, it shows the same
  banner, so a stale tab finds out before its next save.

## Architecture

The three Phase 2 seams are separate modules on both sides.

### Server

```
scraper/web/chapters.py   chapter retrieval: list, one chapter as paragraphs + version
scraper/web/anchor.py     resolve_position and anchor matching (pure)
scraper/web/positions.py  reading.json: read, compare-and-set write, per-book lock
scraper/web/app.py        routes only
```

- `chapters.py` reads only `02 Cleaned`, through the existing
  `Book.cleaned_numbers()` and `cleaned_path()`. It renders each paragraph
  with a block-level function extracted from `assemble._to_html`, so the
  reader and the epub always render alike.

| Method & path | Returns |
|---|---|
| `GET /api/books/{book}/chapters` | `{chapters: [{number, title, words}], first, last}` - only cleaned chapters; gaps are simply absent |
| `GET /api/books/{book}/chapters/{n}` | `{number, title, version, paragraphs: [html], prev, next}` - `prev`/`next` are the neighbouring *available* chapters, skipping gaps; 404 if not cleaned |
| `GET /api/books/{book}/position` | `{revision, position}`, with `position.resolved` (resolved against the current chapter, with `recovered`) |
| `PUT /api/books/{book}/position` | 200 `{revision, position}` or 409 `{revision, position}` |

- `{n}` is parsed as an integer by the route; anything else is 404.
- `/position` validates the body: the chapter must be a cleaned chapter
  (otherwise 422); the paragraph is clamped to the chapter; the offset is
  clamped to 0-1; text fields are length-limited.

### Browser

```
web/src/lib/reader/source.ts    ChapterSource: getChapters(), getChapter(n), prefetch(n)
web/src/lib/reader/locate.ts    which paragraph and offset are at the top; scroll to a position (pure maths + DOM helper)
web/src/lib/reader/sync.ts      PositionSync: revision tracking, debounced save, conflict state (pure reducer + thin I/O)
web/src/lib/reader/device.ts    device id and name
web/src/lib/reader/settings.ts  text size, spacing, width, theme, font (per device)
web/src/routes/Reader.svelte    the page
web/src/components/reader/*     Toolbar, ChapterDrawer, SettingsPanel, ContinuePrompt, ConflictBanner
```

- `ChapterSource` and `PositionSync` are interfaces. Phase 1 implements
  them over the network, with an in-memory cache of the current, previous
  and next chapters. Phase 2 replaces their implementations, with IndexedDB
  and a queue of unsent saves, without touching the page or components.

## The reading page

- **Route:** `#/read/<book>` resumes. `#/read/<book>/<n>` opens chapter `n`.
- **Layout:** a full-height page with a slim toolbar: back, the book's
  title, the chapter's title, chapter list, and Aa settings. The toolbar
  hides while scrolling down and returns on scrolling up or tapping the
  text. Then the chapter heading and the text in one centred column.
- **Typography:**
  - A bundled text face (Literata, variable, via @fontsource), or the
    system sans if the person prefers.
  - Size from 15 to 26px, default 19px on phones and 20px on desktops.
  - Line height 1.45 to 1.9 (default 1.65).
  - Measure narrow, medium or wide (about 34, 40 or 46em), default medium.
  - Justified text with hyphenation is offered but off by default.
- **Themes:** paper, sepia and night, separate from the app's light and
  dark themes, and following it until chosen.
- **End of a chapter:** a clear "Next: Chapter 1,241 - Title" card. If
  the next chapter number is missing, it says "Chapter 1,241 isn't
  downloaded - next available is 1,243".
- **Moving around:**
  - ← and → change chapter; space and shift-space scroll a screen.
  - `t` opens the chapter list.
  - Previous and next buttons sit at the chapter's start and end.
- **Chapter list:** a drawer with search by number or title. It shows
  where you are, and gaps as faint "not downloaded" rows, so a book with
  holes makes sense.
- **Progress:** a thin bar under the toolbar shows progress through the
  chapter; the drawer shows "Chapter 1,240 of 3,214 available".
- **Entry points:**
  - **Continue reading** on each library card and on the book page, with
    the chapter number when a position exists.
  - "Read from here" in the chapter map's tooltip, as a click on a cleaned
    chapter.
- **Prefetch:** the next chapter is fetched in the background once the
  reader is 70% through the current one, so turning the chapter is instant.

## Security

- Every reader endpoint is under `/api`, so the existing LAN access-key
  middleware, allowed-host check, and refusal of cross-origin changes apply
  unchanged. Tests prove it for the new routes specifically.
- **Authorised addresses:** Folio still answers only to `127.0.0.1`,
  `localhost` and, with `--lan`, the PC's LAN address. `serve` gains
  `--allow-host NAME` (repeatable) to authorise more names, such as a
  Tailscale address (`100.x.y.z`) or MagicDNS name. A Tailscale device
  connects from its own address, not loopback, so it still needs the access
  key, exactly like a phone on the home Wi-Fi. Being on a private network
  grants nothing by itself.
- **Escaping:** chapter HTML comes only from the renderer, which escapes
  scraped text before adding its own `<em>` and `<strong>` tags. A test
  feeds markup and script through and checks it arrives inert.
- **Device names** are shown as text, never as HTML.

## Phase 2 requirements (recorded, not built)

Offline reading needs all of these. Phase 1 must not preclude any of them.

1. **A secure context.** Browsers only allow service workers on HTTPS, or
   on localhost. Folio on `http://192.168.…` cannot work offline.
   - **Preferred:** Tailscale's HTTPS certificates (`tailscale cert`, or
     `tailscale serve`), which give a trusted certificate with no
     configuration on the phone.
   - **Alternatives:** a certificate from a local CA trusted on each device
     (such as mkcert), or a reverse proxy with a real domain.
   - Folio's `serve` would accept a certificate and key.
   - **Tailscale is preferred, not required.**
2. **A service worker** to serve the app shell when offline.
3. **Local chapter storage** in IndexedDB: chapters downloaded ahead
   (for example the next 50), with a size limit and eviction of chapters
   already read.
4. **Eventual synchronisation:** offline saves are queued locally with the
   revision they were based on, and sent on reconnection through the same
   PUT. A 409 on reconnection produces the same explicit choice, never a
   silent overwrite.
5. **Content changes while offline:** a stored chapter whose version no
   longer matches is replaced on reconnection, and its position goes
   through `resolve_position`.

## Testing

- **Server (pytest):**
  - `chapters`: listing with gaps; a book with cleaned chapters but no
    built files; titles; word counts; `prev` and `next` skipping gaps; 404
    for a missing chapter or a non-integer; escaping of markup and script;
    the version changing when the file changes.
  - `anchor`: an unchanged chapter (exact); a paragraph inserted above the
    anchor (found by its anchor); a lightly edited anchor paragraph (found
    by overlap); an anchor paragraph removed (proportional); the chapter
    removed (next chapter, else previous); a book with one chapter.
  - `positions`:
    - The first save from revision 0.
    - A matching revision accepted and incremented.
    - A stale revision refused with the stored copy, and the file unchanged.
    - Two threads saving from the same base: exactly one wins.
    - A corrupt file treated as empty.
    - An atomic write that leaves no temporary file behind.
  - **API:**
    - Validation (chapter not cleaned is 422; clamping).
    - A 409 body.
    - LAN key required from another host for GET and PUT position.
    - A cross-origin PUT refused.
    - An unknown host refused.
    - `--allow-host` admitting a named host.
- **Browser logic (Vitest):**
  - `locate`: choosing the top paragraph and offset from paragraph
    rectangles; the inverse scroll target.
  - `sync`: the reducer's decisions:
    - save accepted;
    - 409 to the conflict banner;
    - "keep here" re-saves on the new revision;
    - "go there" moves;
    - no prompt for this device's own save;
    - prompt when another device differs by more than 3 paragraphs;
    - debounce and flush on hide.
  - `settings`: clamping and defaults.
  - `device`: a stable id and readable names.
- **In the browser (scripted, as for Folio):**
  - Phone (390px) and desktop layouts in all three themes; no sideways
    scroll.
  - Resume across two separate browser profiles acting as two devices.
  - A stale tab: profile A open, profile B moves on, A scrolls, and A
    shows the banner, not an overwrite.
  - Re-clean recovery on a copy of a chapter.
  - A book with gaps.

## As built: reading-position and conflict decisions

Implementation, testing and an independent review refined the design
above. These are the rules as they now stand. Deferred findings are in
`docs/backlog.md`.

### What a saved place holds

The server stamps everything that identifies the passage, whatever the
browser sent:
- `anchor`: normalised opening words, used for matching;
- `excerpt`: the opening words as written, up to 90 characters, shown in
  the continue prompt;
- `paragraphs` and `version`;
- `saved_at`: the server's time.

The browser sends:
- `chapter`, `paragraph` and `offset`; the server clamps them;
- `device` and `device_name`;
- `tab`: a random id per page load.

### Finding the place after a re-clean

- **Matching is word by word, not by character.** "He." does not count as
  the start of "Her voice…".
- **Two passes over the ±25-paragraph window:** an exact opening anywhere
  in the window first, then one sharing at least 75% of its words.
  Neighbouring paragraphs in a novel often open alike, so a near fuzzy
  match must not beat the true one a few paragraphs away.

### Which place opens

On opening a book, in this order:
1. **Nothing saved:** start at the first chapter.
2. **This device saved last:**
   - If this device's own later place (`lastOwn`) differs, and the chapter
     has not been re-cleaned since, use `lastOwn`. Its last save may never
     have reached the PC.
   - Otherwise use the saved place.
3. **Another device saved last, and this device has no `lastOwn`, or one
   within 3 paragraphs:** go to the saved place.
4. **Otherwise ask**, showing both places. The time shown for the other
   device is shifted by the measured skew between this device's clock
   and the server's.

`lastOwn` is written to the browser **before** every save is attempted:
- even while a banner is up;
- even if the PC cannot be reached.

So this device's own place is never lost.

### Saving and conflicts

- **One at a time:** saves are queued, and each sends the newest place
  when its turn comes. Repeated flushes (tab hidden, then page closed)
  send at most once.
- **What counts as a repeat:** a place within 1e-4 of the last one sent.
  So a few lines inside an enormous paragraph still save.
- **Refused as stale (409 with a revision):**
  - If it was this same tab's own save (two sends that crossed), catch up
    and save once more.
  - Anything else - another device, or another tab on this device - shows
    the banner: "Go there" or "Keep reading here". "Keep reading here"
    saves the place on screen, against the newer revision.
  - Saving waits while the banner is up.
- **Not a conflict:** a 409 without a revision, a 503, or no connection is
  a failed save. Saving carries on with the next one.
- **Locked file:** the server waits out a briefly locked `reading.json`
  (Windows, scanners, indexers) before answering 503. It never pretends
  nothing was saved.
- **Unreadable file:** a malformed saved place reads as none.
- **Missing chapter:** when the saved chapter is missing (for example mid
  re-clean) and the reader lands on another, nothing is saved until the
  person scrolls, taps or presses a key. The real place is never
  overwritten by a fallback.
- **Returning to a tab:** the tab checks for a newer revision and shows
  the banner if another device or tab has moved on.

### Reading line and scrolling

- **Measuring the place:** the paragraph at the reading line counts with
  1px of slack. Scrolling lands on whole pixels; without the slack,
  each save could slip back a paragraph.
- **Restoring the place:** the reader waits for the text face before
  scrolling to a saved place, so a late font cannot reflow the page
  underneath it.

## Unresolved trade-offs (for the reviewer)

1. **Scroll versus pages.** Phase 1 scrolls. Pagination feels more like a
   book and suits e-ink readers, but it is costly to do well and its
   positions are fragile. It could be added later as a display mode over
   the same paragraph-based position.
2. **The "ask" threshold.** Three paragraphs avoids asking about trivial
   differences. Asking on any difference is simpler, but nags.
3. **No live push.** A second open device learns of movement on its next
   save or when it regains focus, not instantly. A Server-Sent Events
   message would make it instant at modest cost. It is left out for
   simplicity.
4. **History.** Only the latest position is kept. A short history ("you
   were also at…") would make the choice prompt richer, but is not needed
   for correctness.
5. **The reading font** adds about 150KB to the bundle (Latin subsets
   only). The system serif is an alternative with no download, but varies
   in quality across devices.
6. **Device identity is self-declared.** Fine for one person's devices
   behind the access key; not a basis for per-user permissions.
