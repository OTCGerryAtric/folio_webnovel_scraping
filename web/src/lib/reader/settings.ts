// How text is set in the reader. Per device: text size belongs to the screen.

export type Measure = 'narrow' | 'medium' | 'wide'
export type ReaderTheme = 'paper' | 'sepia' | 'night'
export type Face = 'serif' | 'sans'

export interface ReaderSettings {
  size: number
  leading: number
  measure: Measure
  /** null follows the app's light or dark theme. */
  theme: ReaderTheme | null
  font: Face
  justify: boolean
}

export const SIZE = { min: 15, max: 26 }
export const LEADING = { min: 1.45, max: 1.9 }
export const MEASURES: Measure[] = ['narrow', 'medium', 'wide']
export const THEMES: ReaderTheme[] = ['paper', 'sepia', 'night']
export const MEASURE_EM: Record<Measure, number> = { narrow: 34, medium: 40, wide: 46 }

const KEY = 'folio-reader'

export function defaults(isPhone: boolean): ReaderSettings {
  return { size: isPhone ? 19 : 20, leading: 1.65, measure: 'medium', theme: null, font: 'serif', justify: false }
}

const between = (n: unknown, lo: number, hi: number, fallback: number) =>
  typeof n === 'number' && Number.isFinite(n) ? Math.min(hi, Math.max(lo, n)) : fallback

export function clampSettings(s: ReaderSettings, base: ReaderSettings = defaults(false)): ReaderSettings {
  return {
    size: Math.round(between(s.size, SIZE.min, SIZE.max, base.size)),
    leading: Math.round(between(s.leading, LEADING.min, LEADING.max, base.leading) * 100) / 100,
    measure: MEASURES.includes(s.measure) ? s.measure : 'medium',
    theme: s.theme && THEMES.includes(s.theme) ? s.theme : null,
    font: s.font === 'sans' ? 'sans' : 'serif',
    justify: s.justify === true,
  }
}

export function loadSettings(isPhone: boolean): ReaderSettings {
  const base = defaults(isPhone)
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) ?? 'null')
    if (saved && typeof saved === 'object') return clampSettings({ ...base, ...saved }, base)
  } catch {
    // unavailable: defaults
  }
  return base
}

export function saveSettings(s: ReaderSettings) {
  try {
    localStorage.setItem(KEY, JSON.stringify(s))
  } catch {
    // private mode: lasts this visit
  }
}
