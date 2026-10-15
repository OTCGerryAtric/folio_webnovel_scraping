// Keeping one reading place across devices: the network side of sync.ts.
// Saves name the revision they were based on; a refusal means another
// device moved on, and the reader asks rather than overwriting. Phase 2
// can replace this with an offline queue behind the same methods.

import { api, savePosition, type PositionSave } from '../api'
import { getDevice, type Device } from './device'
import { decideOnOpen, onConflict, type OpenDecision, type Place, type Stored, type Theirs } from './sync'

export interface SyncDeps {
  device: () => Device
  get: (book: string) => Promise<Stored>
  save: (book: string, body: PositionSave, keepalive: boolean) => Promise<{ ok: boolean; stored: Stored }>
  storage: { get: (key: string) => string | null; set: (key: string, value: string) => void }
  now: () => number
}

/** This device's own last place in a book, and when. */
export interface OwnPlace extends Place {
  at: number
}

const DEBOUNCE = 2000

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

const browserDeps: SyncDeps = {
  device: getDevice,
  get: api.position,
  save: savePosition,
  storage: browserStorage,
  now: Date.now,
}

const same = (a: Place | null, b: Place | null) =>
  !!a && !!b && a.chapter === b.chapter && a.paragraph === b.paragraph && Math.abs(a.offset - b.offset) < 0.02

export class PositionSync {
  /** Set when another device has moved on; saves wait until the reader chooses. */
  banner = $state<Theirs | null>(null)

  private revision = 0
  private bannerRevision = 0
  private pending: Place | null = null
  private sent: Place | null = null
  private timer: ReturnType<typeof setTimeout> | undefined
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
    this.revision = stored.revision
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

  /** Back to this tab: has another device moved on meanwhile? */
  async onVisible() {
    try {
      const stored = await this.deps.get(this.book)
      if (stored.revision > this.revision) this.handleNewer(stored)
    } catch {
      // unreachable: the next save will find out
    }
  }

  /** Overwrite the other device's place with this one, on purpose. */
  async keepHere() {
    this.revision = this.bannerRevision
    this.banner = null
    this.sent = null
    await this.send(true)
  }

  /** Take the other device's place. The caller opens it. */
  goThere(): Place | null {
    const theirs = this.banner
    if (!theirs) return null
    this.revision = this.bannerRevision
    this.banner = null
    this.pending = null
    return { chapter: theirs.resolvedChapter, paragraph: theirs.resolvedParagraph, offset: theirs.resolvedOffset }
  }

  private async send(keepalive: boolean, adopted = false): Promise<void> {
    const place = this.pending
    if (!place || this.banner || same(place, this.sent)) return
    // Remember it here first, so a failed save still counts as this device's place.
    this.deps.storage.set(this.key, JSON.stringify({ ...place, at: this.deps.now() }))
    const device = this.deps.device()
    try {
      const answer = await this.deps.save(
        this.book,
        { base_revision: this.revision, ...place, device: device.id, device_name: device.name },
        keepalive,
      )
      if (answer.ok) {
        this.revision = answer.stored.revision
        this.sent = place
        if (this.pending === place) this.pending = null
        return
      }
      const decision = onConflict(answer.stored, device.id)
      if (decision.kind === 'adopt' && !adopted) {
        this.revision = decision.revision // this device's own other tab: catch up and save again
        return this.send(keepalive, true)
      }
      this.handleNewer(answer.stored)
    } catch {
      // unreachable: lastOwn already holds this place for next time
    }
  }

  private handleNewer(stored: Stored) {
    const decision = onConflict(stored, this.deps.device().id)
    if (decision.kind === 'adopt') {
      this.revision = decision.revision
      return
    }
    this.bannerRevision = decision.revision
    this.banner = decision.theirs
  }
}
