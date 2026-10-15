// Keeping one reading place across devices: the network side of sync.ts.
// Saves name the revision they were based on; a refusal means another
// device or tab moved on, and the reader asks rather than overwriting.
// Saves go one at a time, always sending the latest place. Phase 2 can
// replace this with an offline queue behind the same methods.

import { api, savePosition, type PositionSave } from '../api'
import { getDevice, type Device } from './device'
import { decideOnOpen, onConflict, type OpenDecision, type Place, type Stored, type Theirs } from './sync'

export interface SyncDeps {
  device: () => Device
  /** This tab, for telling its own saves from another tab's. */
  tab: () => string
  get: (book: string) => Promise<Stored>
  save: (book: string, body: PositionSave, keepalive: boolean) => Promise<{ ok: boolean; stored: Stored }>
  storage: { get: (key: string) => string | null; set: (key: string, value: string) => void }
  now: () => number
}

/** This device's own last place in a book, and when (by this device's clock). */
export interface OwnPlace extends Place {
  at: number
}

const DEBOUNCE = 2000
// Only for skipping a repeat of the place just sent: small enough that a
// line or two inside an enormous paragraph still counts as a move.
const SAME_OFFSET = 1e-4

const browserStorage: SyncDeps['storage'] = {
  get: key => {
    try {
      return localStorage.getItem(key)
    } catch {
      return null
    }
  },
  set: (key, value) => {
    try {
      localStorage.setItem(key, value)
    } catch {
      // private mode: remembered for this visit only
    }
  },
}

const thisTab = `t-${Math.random().toString(36).slice(2, 10)}`

const browserDeps: SyncDeps = {
  device: getDevice,
  tab: () => thisTab,
  get: api.position,
  save: savePosition,
  storage: browserStorage,
  now: Date.now,
}

const same = (a: Place | null, b: Place | null) =>
  !!a && !!b && a.chapter === b.chapter && a.paragraph === b.paragraph && Math.abs(a.offset - b.offset) < SAME_OFFSET

export class PositionSync {
  /** Set when another device or tab has moved on; saves wait until the reader chooses. */
  banner = $state<Theirs | null>(null)
  /** How far this device's clock is ahead of the server's, in ms. */
  skew = 0

  private revision = 0
  private bannerRevision = 0
  private pending: Place | null = null
  private sent: Place | null = null
  private held = false
  private timer: ReturnType<typeof setTimeout> | undefined
  private queue: Promise<void> = Promise.resolve()
  private readonly key: string

  constructor(
    private readonly book: string,
    private readonly deps: SyncDeps = browserDeps,
  ) {
    this.key = `folio-last:${book}`
  }

  lastOwn(): OwnPlace | null {
    try {
      const value = JSON.parse(this.deps.storage.get(this.key) ?? 'null')
      return value && typeof value.chapter === 'number' ? value : null
    } catch {
      return null
    }
  }

  async open(): Promise<OpenDecision> {
    const stored = await this.deps.get(this.book)
    this.adopt(stored)
    return decideOnOpen(stored, this.deps.device().id, this.lastOwn())
  }

  /** Where the reader is now; saved once scrolling has stopped for a moment. */
  report(place: Place) {
    this.pending = place
    clearTimeout(this.timer)
    this.timer = setTimeout(() => void this.send(false), DEBOUNCE)
  }

  /** Save now: the tab is being hidden or closed, or the chapter changed. */
  flush(): Promise<void> {
    clearTimeout(this.timer)
    return this.send(true)
  }

  /** Don't save until the reader acts: it landed somewhere it did not choose. */
  hold() {
    this.held = true
  }

  release() {
    this.held = false
  }

  /** Back to this tab: has another device or tab moved on meanwhile? */
  async onVisible() {
    try {
      const stored = await this.deps.get(this.book)
      if (typeof stored.revision === 'number' && stored.revision > this.revision) this.handleNewer(stored)
    } catch {
      // unreachable: the next save will find out
    }
  }

  /** Overwrite the other place with this one, on purpose. */
  keepHere(place?: Place | null): Promise<void> {
    this.revision = this.bannerRevision
    this.banner = null
    this.sent = null
    if (place) this.pending = place
    return this.flush()
  }

  /** Take the other place. The caller opens it. */
  goThere(): Place | null {
    const theirs = this.banner
    if (!theirs) return null
    this.revision = this.bannerRevision
    this.banner = null
    this.pending = null
    return { chapter: theirs.resolvedChapter, paragraph: theirs.resolvedParagraph, offset: theirs.resolvedOffset }
  }

  /** Saves go one at a time; each sends the latest place when its turn comes. */
  private send(keepalive: boolean): Promise<void> {
    this.queue = this.queue.then(() => this.sendNow(keepalive))
    return this.queue
  }

  private async sendNow(keepalive: boolean, adopted = false): Promise<void> {
    const place = this.pending
    if (!place || this.held) return
    // Remember it first - even under a banner, even if the PC can't be reached -
    // so this device's own place is never lost.
    this.deps.storage.set(this.key, JSON.stringify({ ...place, at: this.deps.now() }))
    if (this.banner || same(place, this.sent)) return
    const device = this.deps.device()
    try {
      const answer = await this.deps.save(
        this.book,
        { base_revision: this.revision, ...place, device: device.id, device_name: device.name, tab: this.deps.tab() },
        keepalive,
      )
      if (answer.ok) {
        this.adopt(answer.stored)
        this.sent = place
        if (this.pending === place) this.pending = null
        return
      }
      if (typeof answer.stored?.revision !== 'number') return // not a conflict: try again with the next save
      const decision = onConflict(answer.stored, device.id, this.deps.tab())
      if (decision.kind === 'adopt' && !adopted) {
        this.revision = decision.revision // this tab's own save crossed with this one: catch up, save again
        return this.sendNow(keepalive, true)
      }
      this.handleNewer(answer.stored)
    } catch {
      // unreachable: lastOwn already holds this place for next time
    }
  }

  private adopt(stored: Stored) {
    if (typeof stored.revision === 'number') this.revision = stored.revision
    if (stored.now) this.skew = this.deps.now() - Date.parse(stored.now)
  }

  private handleNewer(stored: Stored) {
    const decision = onConflict(stored, this.deps.device().id, this.deps.tab())
    if (decision.kind === 'adopt') {
      this.revision = decision.revision
      return
    }
    this.bannerRevision = decision.revision
    this.banner = decision.theirs
  }
}
