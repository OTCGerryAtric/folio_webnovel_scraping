// A typed wrapper over every endpoint. Errors arrive as ApiError carrying
// the server's own message, which is the CLI's wording.

import type { Stored } from './reader/sync'
import type {
  BookDetail, BookSummary, Chapter, ChapterList, Job, JobRequest, PatternResult, Preview, Review, SettingsData, SettingValue,
} from './types'

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message)
  }
}

const enc = encodeURIComponent

async function call<T>(method: string, path: string, body?: unknown): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, {
      method,
      headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    })
  } catch {
    throw new ApiError(0, 'Folio is not reachable. Is it still running?')
  }
  if (response.status === 204) return undefined as T
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new ApiError(response.status, data.error ?? `${response.status} ${response.statusText}`)
  return data as T
}

export const api = {
  books: () => call<BookSummary[]>('GET', '/api/books'),
  book: (name: string) => call<BookDetail>('GET', `/api/books/${enc(name)}`),
  site: (name: string, fresh = false) =>
    call<{ latest: number | null; summary: BookSummary }>('GET', `/api/books/${enc(name)}/site${fresh ? '?fresh=1' : ''}`),
  preview: (url: string) => call<Preview>('POST', '/api/books/preview', { url }),
  add: (body: { url?: string; name?: string; url_template?: string; title?: string; download?: boolean }) =>
    call<BookSummary>('POST', '/api/books', body),
  startJob: (name: string, body: JobRequest) => call<Job>('POST', `/api/books/${enc(name)}/jobs`, body),
  updateAll: () => call<Job[]>('POST', '/api/update-all'),
  jobs: () => call<Job[]>('GET', '/api/jobs'),
  cancel: (id: string) => call<Job>('POST', `/api/jobs/${enc(id)}/cancel`),
  review: (name: string, min: number) => call<Review>('GET', `/api/books/${enc(name)}/review?min=${min}`),
  testPattern: (name: string, pattern: string) =>
    call<PatternResult>('POST', `/api/books/${enc(name)}/review/test`, { pattern }),
  suggest: (name: string, sentence: string) =>
    call<{ pattern: string }>('POST', `/api/books/${enc(name)}/review/phrase`, { sentence }),
  ignore: (name: string, sentence: string) =>
    call<{ ignored: string }>('POST', `/api/books/${enc(name)}/review/ignore`, { sentence }),
  settings: (name: string) => call<SettingsData>('GET', `/api/books/${enc(name)}/settings`),
  saveSettings: (name: string, body: { values?: Record<string, SettingValue>; raw?: string }) =>
    call<SettingsData>('PUT', `/api/books/${enc(name)}/settings`, body),
  deleteFile: (name: string, file: string) => call<void>('DELETE', `/api/books/${enc(name)}/files/${enc(file)}`),
  chapters: (name: string) => call<ChapterList>('GET', `/api/books/${enc(name)}/chapters`),
  chapter: (name: string, n: number) => call<Chapter>('GET', `/api/books/${enc(name)}/chapters/${n}`),
  position: (name: string) => call<Stored>('GET', `/api/books/${enc(name)}/position`),
}

export interface PositionSave {
  base_revision: number
  chapter: number
  paragraph: number
  offset: number
  device: string
  device_name: string
  tab: string
}

/** Save a reading place. A 409 is an answer here, not an error: it carries the newer place. */
export async function savePosition(
  name: string,
  body: PositionSave,
  keepalive = false,
): Promise<{ ok: boolean; stored: Stored }> {
  let response: Response
  try {
    response = await fetch(`/api/books/${enc(name)}/position`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      keepalive,
    })
  } catch {
    throw new ApiError(0, 'Folio is not reachable. Is it still running?')
  }
  const data = await response.json().catch(() => ({}))
  // Only a 409 carrying the newer place is a conflict; anything else is a failed save.
  if (response.status === 409 && typeof data.revision === 'number') return { ok: false, stored: data as Stored }
  if (!response.ok) throw new ApiError(response.status, data.error ?? `${response.status} ${response.statusText}`)
  return { ok: true, stored: data as Stored }
}

export const fileUrl = (name: string, file: string) => `/api/books/${enc(name)}/files/${enc(file)}`
export const coverUrl = (name: string) => `/api/books/${enc(name)}/cover`
