// Where the reader gets chapters. Phase 1 asks Folio over the network and
// keeps the last few in memory; Phase 2 can put an IndexedDB store behind
// the same interface for reading offline.

import { api } from '../api'
import type { Chapter, ChapterList } from '../types'

export interface ChapterSource {
  chapters(): Promise<ChapterList>
  chapter(n: number): Promise<Chapter>
  /** Start fetching a chapter likely to be read next. */
  prefetch(n: number): void
}

interface Fetchers {
  chapter: (book: string, n: number) => Promise<Chapter>
  chapters: (book: string) => Promise<ChapterList>
}

const KEEP = 3

export function networkSource(book: string, fetchers: Fetchers = { chapter: api.chapter, chapters: api.chapters }): ChapterSource {
  const kept = new Map<number, Promise<Chapter>>()

  function get(n: number): Promise<Chapter> {
    const held = kept.get(n)
    if (held) {
      kept.delete(n) // most recently used goes last
      kept.set(n, held)
      return held
    }
    const pending = fetchers.chapter(book, n)
    kept.set(n, pending)
    pending.catch(() => kept.get(n) === pending && kept.delete(n))
    while (kept.size > KEEP) kept.delete(kept.keys().next().value!)
    return pending
  }

  return {
    chapters: () => fetchers.chapters(book),
    chapter: get,
    prefetch: n => void get(n).catch(() => {}),
  }
}

const sleep = (ms: number) => new Promise<void>(resolve => setTimeout(resolve, ms))

/**
 * Try again when a chapter is missing for a moment - a re-clean rewrites
 * the cleaned folder - and give up after two retries.
 */
export async function withRetry<T>(
  fn: () => Promise<T>,
  { tries = 3, delay = 1500, wait = sleep }: { tries?: number; delay?: number; wait?: (ms: number) => Promise<void> } = {},
): Promise<T> {
  for (let attempt = 1; ; attempt++) {
    try {
      return await fn()
    } catch (e) {
      if ((e as { status?: number }).status !== 404 || attempt >= tries) throw e
      await wait(delay)
    }
  }
}
