// The current route, reactive. The routes themselves are in routes.ts.

import { parseRoute, type Route } from './routes'

export { bookPath, readPath, TABS, type Route, type Tab } from './routes'

class Router {
  route = $state<Route>(parseRoute(location.hash))

  constructor() {
    addEventListener('hashchange', () => {
      this.route = parseRoute(location.hash)
      // The reader puts its own place back; everywhere else starts at the top.
      if (this.route.page !== 'read') scrollTo({ top: 0 })
    })
  }

  go(path: string) {
    location.hash = path
  }
}

export const router = new Router()
