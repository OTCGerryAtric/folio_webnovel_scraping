// The app's hash routes, as pure functions so they can be tested.
//   #/                      the library
//   #/book/<name>/<tab>     a book
//   #/read/<name>[/<n>]     the reader: resume, or open chapter n

export type Tab = 'overview' | 'watermarks' | 'files' | 'settings'
export const TABS: Tab[] = ['overview', 'watermarks', 'files', 'settings']

export type Route =
  | { page: 'library' }
  | { page: 'book'; name: string; tab: Tab }
  | { page: 'read'; name: string; chapter: number | null }

export function parseRoute(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean)
  if (parts[0] === 'book' && parts[1]) {
    const tab = (TABS as string[]).includes(parts[2]) ? (parts[2] as Tab) : 'overview'
    return { page: 'book', name: decodeURIComponent(parts[1]), tab }
  }
  if (parts[0] === 'read' && parts[1]) {
    const chapter = /^\d+$/.test(parts[2] ?? '') ? Number(parts[2]) : null
    return { page: 'read', name: decodeURIComponent(parts[1]), chapter }
  }
  return { page: 'library' }
}

export const bookPath = (name: string, tab: Tab = 'overview') =>
  `#/book/${encodeURIComponent(name)}${tab === 'overview' ? '' : `/${tab}`}`

export const readPath = (name: string, chapter?: number) =>
  `#/read/${encodeURIComponent(name)}${chapter ? `/${chapter}` : ''}`
