// A hash router: #/ for the library, #/book/<name>/<tab> for a book.
// Hash routes keep the server's static file serving trivial.

export type Tab = 'overview' | 'watermarks' | 'files' | 'settings'
export const TABS: Tab[] = ['overview', 'watermarks', 'files', 'settings']

export type Route = { page: 'library' } | { page: 'book'; name: string; tab: Tab }

function parse(hash: string): Route {
  const parts = hash.replace(/^#\/?/, '').split('/').filter(Boolean)
  if (parts[0] === 'book' && parts[1]) {
    const tab = (TABS as string[]).includes(parts[2]) ? (parts[2] as Tab) : 'overview'
    return { page: 'book', name: decodeURIComponent(parts[1]), tab }
  }
  return { page: 'library' }
}

class Router {
  route = $state<Route>(parse(location.hash))

  constructor() {
    addEventListener('hashchange', () => {
      this.route = parse(location.hash)
      scrollTo({ top: 0 })
    })
  }

  go(path: string) {
    location.hash = path
  }
}

export const router = new Router()

export const bookPath = (name: string, tab: Tab = 'overview') =>
  `#/book/${encodeURIComponent(name)}${tab === 'overview' ? '' : `/${tab}`}`
