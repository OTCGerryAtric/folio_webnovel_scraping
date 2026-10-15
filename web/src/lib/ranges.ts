// Small formatting helpers for numbers, sizes and times.

import type { ChapterState, MapRun } from './types'

/** `[1, 2, 3, 7]` reads as `1-3, 7`, as the CLI writes it. */
export function describeRanges(nums: number[]): string {
  const sorted = [...nums].sort((a, b) => a - b)
  if (!sorted.length) return 'none'
  const spans: string[] = []
  let first = sorted[0]
  let last = sorted[0]
  const close = () => spans.push(first === last ? `${first}` : `${first}-${last}`)
  for (const n of sorted.slice(1)) {
    if (n === last + 1) {
      last = n
      continue
    }
    close()
    first = last = n
  }
  close()
  return spans.join(', ')
}

export function formatBytes(n: number): string {
  if (n < 1024) return `${n} B`
  const units = ['KB', 'MB', 'GB']
  let value = n / 1024
  let unit = 0
  while (value >= 1024 && unit < units.length - 1) {
    value /= 1024
    unit++
  }
  return `${value.toFixed(1)} ${units[unit]}`
}

export function eta(done: number, total: number | null | undefined, perSecond: number): string {
  if (!total || !perSecond || done >= total) return ''
  const seconds = Math.round((total - done) / perSecond)
  return seconds < 60 ? `about ${seconds}s left` : `about ${Math.round(seconds / 60)} min left`
}

export function timeAgo(when: string | number): string {
  const t = typeof when === 'number' ? when * 1000 : Date.parse(when)
  const s = Math.max(0, (Date.now() - t) / 1000)
  if (s < 60) return 'just now'
  if (s < 3600) return `${Math.floor(s / 60)} min ago`
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`
  const days = Math.floor(s / 86400)
  return days === 1 ? 'yesterday' : `${days} days ago`
}

export function plural(n: number, word: string): string {
  return `${n.toLocaleString('en-GB')} ${word}${n === 1 ? '' : 's'}`
}

/** Every chapter number in the map's runs of one state. */
export function expandRuns(map: MapRun[], state: ChapterState): number[] {
  const out: number[] = []
  for (const [s, first, last] of map) {
    if (s !== state) continue
    for (let n = first; n <= last; n++) out.push(n)
  }
  return out
}
