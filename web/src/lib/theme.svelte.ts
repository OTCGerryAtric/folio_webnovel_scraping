// Light or dark: the system's choice until the person picks one, which is
// remembered in this browser.

export type Theme = 'light' | 'dark'
const KEY = 'folio-theme'

function stored(): Theme | null {
  try {
    const value = localStorage.getItem(KEY)
    return value === 'light' || value === 'dark' ? value : null
  } catch {
    return null
  }
}

const media = matchMedia('(prefers-color-scheme: dark)')

class ThemeStore {
  chosen = $state<Theme | null>(stored())
  system = $state<Theme>(media.matches ? 'dark' : 'light')

  constructor() {
    media.addEventListener('change', e => (this.system = e.matches ? 'dark' : 'light'))
    $effect.root(() => {
      $effect(() => {
        document.documentElement.dataset.theme = this.current
      })
    })
  }

  get current(): Theme {
    return this.chosen ?? this.system
  }

  toggle() {
    this.chosen = this.current === 'dark' ? 'light' : 'dark'
    try {
      localStorage.setItem(KEY, this.chosen)
    } catch {
      // private mode: the choice lasts this visit
    }
  }
}

export const theme = new ThemeStore()
