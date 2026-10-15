// The decisions behind keeping one reading place across devices. Pure: the
// network side lives in positionSync.svelte.ts, so Phase 2 can replace it
// (an offline queue) without changing these rules.

export interface Place {
  chapter: number
  paragraph: number
  offset: number
}

export interface SavedPlace extends Place {
  device: string
  device_name: string
  saved_at: string
  anchor: string
  /** The paragraph's opening as written, for showing. */
  excerpt?: string
  /** Which tab saved it: a tab only quietly catches up with its own saves. */
  tab?: string
}

export type Recovered = 'exact' | 'anchor' | 'proportional' | 'moved'

export interface Stored {
  revision: number
  position: SavedPlace | null
  /** The saved place as it lands in the chapters as they are now. */
  resolved: (Place & { recovered: Recovered }) | null
  /** The server's time when it answered, so ages can ignore a wrong device clock. */
  now?: string
}

/** Another device's place, where it lands now. */
export type Theirs = SavedPlace & { resolvedChapter: number; resolvedParagraph: number; resolvedOffset: number }

export type OpenDecision =
  | { kind: 'start' }
  | { kind: 'go'; place: Place; note?: string; recovered?: Recovered }
  | { kind: 'ask'; theirs: Theirs; ours: Place }

export type ConflictDecision = { kind: 'banner'; revision: number; theirs: Theirs } | { kind: 'adopt'; revision: number }

/** Closer than this, two places count as the same and nobody is asked. */
export const SAME_PLACE = 3

const fmt = (n: number) => n.toLocaleString('en-GB')

export function differs(a: Place, b: Place, threshold = SAME_PLACE): boolean {
  return a.chapter !== b.chapter || Math.abs(a.paragraph - b.paragraph) > threshold
}

function landed(stored: Stored): { place: Place; note?: string; recovered?: Recovered } {
  const saved = stored.position!
  const r = stored.resolved ?? { ...saved, recovered: 'exact' as const }
  const place = { chapter: r.chapter, paragraph: r.paragraph, offset: r.offset }
  if (r.recovered === 'moved') {
    return { place, recovered: 'moved', note: `Chapter ${fmt(saved.chapter)} isn't available - opened chapter ${fmt(r.chapter)}.` }
  }
  if (r.recovered === 'anchor' || r.recovered === 'proportional') {
    return { place, note: "This chapter has changed since you left it - you're at the closest point." }
  }
  return { place }
}

function theirsOf(stored: Stored): Theirs {
  const { place } = landed(stored)
  return { ...stored.position!, resolvedChapter: place.chapter, resolvedParagraph: place.paragraph, resolvedOffset: place.offset }
}

/** What to do on opening a book, given the stored place and this device's own last place. */
export function decideOnOpen(stored: Stored, deviceId: string, lastOwn: Place | null): OpenDecision {
  if (!stored.position) return { kind: 'start' }
  const { place, note, recovered } = landed(stored)
  const go = (to: Place, withNote?: string): OpenDecision => ({
    kind: 'go',
    place: to,
    ...(withNote ? { note: withNote } : {}),
    ...(recovered ? { recovered } : {}),
  })
  if (stored.position.device === deviceId) {
    // This device saved last; but a later place of its own may never have
    // reached the PC (it was offline when the tab closed). lastOwn is
    // written before every send, so it is the most recent - unless a
    // re-clean has moved paragraphs since, when the recovered place is safer.
    if (lastOwn && !recovered && (differs(lastOwn, place, 0) || lastOwn.offset !== place.offset)) {
      return { kind: 'go', place: { chapter: lastOwn.chapter, paragraph: lastOwn.paragraph, offset: lastOwn.offset } }
    }
    return go(place, note)
  }
  if (!lastOwn || !differs(lastOwn, place)) return go(place, note)
  return { kind: 'ask', theirs: theirsOf(stored), ours: lastOwn }
}

/** A save was refused because the stored place is newer. */
export function onConflict(current: Stored, deviceId: string, tabId: string): ConflictDecision {
  // Only this very tab's own save (two sends that crossed) is caught up with
  // quietly. Another tab - even on this device - may be far ahead: ask.
  const own = current.position && current.position.device === deviceId && current.position.tab === tabId
  if (!current.position || own) return { kind: 'adopt', revision: current.revision }
  return { kind: 'banner', revision: current.revision, theirs: theirsOf(current) }
}

/** This device's last place, kept even when sending it failed, so nothing is silently lost. */
export function lastOwnAfterFailure(_lastOwn: Place | null, attempted: Place): Place {
  return attempted
}
