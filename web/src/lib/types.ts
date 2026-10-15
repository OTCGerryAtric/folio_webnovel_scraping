// The shapes the API sends, as defined in scraper/web/app.py.

export type ChapterState = 'cleaned' | 'raw' | 'missing' | 'new'
export type MapRun = [ChapterState, number, number]
export type JobKind = 'download' | 'clean' | 'build' | 'update'
export type JobStatus = 'queued' | 'running' | 'done' | 'cancelled' | 'error'
export type Format = 'epub' | 'pdf' | 'md' | 'txt'

export interface OutputFile {
  name: string
  format: string
  size: number
  modified: string
  first: number | null
  last: number | null
}

export interface BookSummary {
  name: string
  title: string
  author: string | null
  source: string | null
  ready: boolean
  error: string | null
  downloaded: number
  cleaned: number
  first: number | null
  last: number | null
  missing: number
  latest: number | null
  new: number
  build_every: number
  outputs: OutputFile[]
  has_cover: boolean
  /** Where reading got to, for "Continue reading". */
  reading: { chapter: number } | null
  job: string | null
}

export interface JobSummary {
  fetched?: number
  cleaned?: number
  skipped?: number
  files?: string[]
}

export interface ActivityRecord {
  id: string
  book: string
  kind: JobKind
  params: Record<string, unknown>
  status: JobStatus
  created: number
  started: number | null
  finished: number | null
  summary: JobSummary
  error: string | null
}

export interface BookDetail extends BookSummary {
  map: MapRun[]
  activity: ActivityRecord[]
}

export interface Progress {
  done: number
  total: number | null
  label: string
}

export interface Job extends ActivityRecord {
  progress: Progress | null
  log?: string[]
}

export type JobEvent =
  | { type: 'job'; job: Job }
  | { type: 'log'; job: string; book: string; line: string }
  | { type: 'progress'; job: string; book: string; progress: Progress }

export interface Preview {
  title: string
  author: string | null
  status: string | null
  updated: string | null
  latest: number | null
  url_template: string
  cover: string | null
  site_phrase: boolean
  name: string
  exists: boolean
}

export interface ReviewRow {
  text: string
  key: string
  chapters: number
  first: number | null
  contexts: { chapter: number; text: string }[]
}

export interface Review {
  chapters: number
  rows: ReviewRow[]
  phrases: string[]
}

export interface PatternResult {
  sentences: number
  chapters: number
  total: number
  examples: { chapter: number; text: string; start: number; end: number }[]
  warning?: string
}

export type SettingValue = string | number | boolean | string[] | null

export interface SettingsData {
  values: Record<string, SettingValue>
  defaults: Record<string, SettingValue>
  raw: string
}

export interface JobRequest {
  kind: JobKind
  start?: number
  end?: number
  refresh?: boolean
  format?: Format
  every?: number
}

// --- the reader ---------------------------------------------------------------

export interface ChapterSummary {
  number: number
  title: string | null
  words: number
}

export interface ChapterList {
  chapters: ChapterSummary[]
  first: number | null
  last: number | null
}

export interface Chapter {
  number: number
  title: string | null
  version: string
  /** Escaped HTML, one entry per paragraph of the cleaned text. */
  paragraphs: string[]
  prev: number | null
  next: number | null
}
