// The settings form: which book.toml keys it shows, how, and what changed.
// remove_phrases and review_ignore are managed in the Watermarks tab.

import type { SettingValue } from './types'

export type FieldKind = 'text' | 'url' | 'int' | 'float' | 'bool' | 'list' | 'patterns'

export interface Field {
  key: string
  label: string
  kind: FieldKind
  help: string
  min?: number
  max?: number
  step?: number
  mono?: boolean
}

export interface Group {
  title: string
  hint: string
  fields: Field[]
  /** Changing these alters the cleaned text, so a re-clean is worth offering. */
  affectsCleaning?: boolean
}

export const GROUPS: Group[] = [
  {
    title: 'Book',
    hint: 'What the finished files are called and credited to.',
    fields: [
      { key: 'title', label: 'Title', kind: 'text', help: 'Goes on the title page of every file.' },
      { key: 'author', label: 'Author', kind: 'text', help: '' },
      { key: 'source', label: 'Book page', kind: 'url', help: 'Where Folio checks for new chapters.' },
    ],
  },
  {
    title: 'Chapters',
    hint: 'Where each chapter lives on the site.',
    fields: [
      { key: 'url_template', label: 'Chapter address', kind: 'url', mono: true, help: '{n} is replaced by the chapter number.' },
      { key: 'start', label: 'First chapter', kind: 'int', min: 1, help: '' },
      { key: 'step', label: 'Step', kind: 'int', min: 1, help: 'Gap between chapter numbers.' },
    ],
  },
  {
    title: 'Extraction',
    hint: 'Which part of each page is the story.',
    affectsCleaning: true,
    fields: [
      { key: 'content_selector', label: 'Text selector', kind: 'text', mono: true, help: 'CSS selector for the chapter text. Empty: found automatically.' },
      { key: 'title_selector', label: 'Title selector', kind: 'text', mono: true, help: 'CSS selector for the chapter title.' },
      { key: 'remove_selectors', label: 'Strip these first', kind: 'list', mono: true, help: 'CSS selectors removed before the text is read.' },
    ],
  },
  {
    title: 'Cleaning',
    hint: 'What is taken out of the text.',
    affectsCleaning: true,
    fields: [
      { key: 'dedupe', label: 'Remove repeated blocks', kind: 'bool', help: 'Blocks on most pages are site furniture.' },
      { key: 'dedupe_threshold', label: 'Repeated on at least', kind: 'float', min: 0.05, max: 1, step: 0.05, help: 'Share of pages, 0 to 1.' },
      { key: 'strip_patterns', label: 'Remove blocks matching', kind: 'patterns', help: 'Regular expressions; a matching paragraph goes.' },
      { key: 'trim_overlap', label: 'Trim opening recaps', kind: 'bool', help: 'When a chapter repeats the end of the last one.' },
      { key: 'overlap_window', label: 'Recap window', kind: 'int', min: 1, help: 'Blocks at the end of a chapter a recap may restate.' },
    ],
  },
  {
    title: 'Building',
    hint: 'How the finished files are split.',
    fields: [
      { key: 'build_every', label: 'Chapters per file', kind: 'int', min: 0, step: 50, help: '0 builds one file; 500 gives 1-500, 501-1000, …' },
    ],
  },
  {
    title: 'Politeness',
    hint: 'How gently the site is asked.',
    fields: [
      { key: 'delay', label: 'Seconds between pages', kind: 'float', min: 0, step: 0.5, help: '' },
      { key: 'max_misses', label: 'Stop after missing', kind: 'int', min: 1, help: 'Pages in a row, when the end is not known.' },
      { key: 'max_retries', label: 'Attempts per page', kind: 'int', min: 1, help: '' },
      { key: 'timeout', label: 'Timeout (seconds)', kind: 'float', min: 1, help: '' },
    ],
  },
]

const same = (a: SettingValue | undefined, b: SettingValue | undefined) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null)

/** The keys whose values differ. A field emptied is sent as "", which removes it from book.toml. */
export function changes(saved: Record<string, SettingValue>, edited: Record<string, SettingValue>): Record<string, SettingValue> {
  const out: Record<string, SettingValue> = {}
  for (const key of Object.keys(edited)) {
    if (same(saved[key], edited[key])) continue
    out[key] = edited[key] === null ? '' : edited[key]
  }
  return out
}

export function parseField(kind: FieldKind, raw: string): SettingValue {
  const text = raw.trim()
  if (!text) return null
  if (kind === 'int') return Number.parseInt(text, 10)
  if (kind === 'float') return Number.parseFloat(text)
  return text
}
