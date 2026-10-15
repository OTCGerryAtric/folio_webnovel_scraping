// Sorting the watermark studio's repeated sentences by what they look like,
// not just how often they repeat: authors repeat themselves too.

import type { ReviewRow } from './types'

export const SIGNAL_LABEL: Record<string, string> = {
  website: 'Names a website',
  reader: 'Talks to the reader',
  symbols: 'Mostly symbols',
}

export function splitRows(rows: ReviewRow[]): { junk: ReviewRow[]; story: ReviewRow[] } {
  return { junk: rows.filter(r => r.kind === 'junk'), story: rows.filter(r => r.kind !== 'junk') }
}
