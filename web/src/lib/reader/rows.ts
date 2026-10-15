// The chapter list's rows: chapters, and a faint row for each run of
// chapters not downloaded, so a book with holes makes sense.

import type { ChapterSummary } from '../types'

export type Row =
  | { kind: 'chapter'; number: number; title: string | null }
  | { kind: 'gap'; from: number; to: number }

export function chapterRows(chapters: ChapterSummary[], query: string): Row[] {
  const wanted = query.trim().toLowerCase().replace(/,/g, '')
  if (wanted) {
    return chapters
      .filter(c => String(c.number).startsWith(wanted) || (c.title ?? '').toLowerCase().includes(wanted))
      .map(c => ({ kind: 'chapter', number: c.number, title: c.title }))
  }
  const rows: Row[] = []
  let previous: number | null = null
  for (const c of chapters) {
    if (previous !== null && c.number > previous + 1) rows.push({ kind: 'gap', from: previous + 1, to: c.number - 1 })
    rows.push({ kind: 'chapter', number: c.number, title: c.title })
    previous = c.number
  }
  return rows
}
