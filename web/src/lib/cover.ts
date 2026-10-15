// Generated covers for books without a cover image: colours drawn from the
// title, so every book keeps its own look.

function fnv1a(text: string): number {
  let hash = 0x811c9dc5
  for (const ch of text) {
    hash ^= ch.codePointAt(0)!
    hash = Math.imul(hash, 0x01000193) >>> 0
  }
  return hash
}

export interface CoverPalette {
  from: string
  to: string
  ink: string
  accent: string
}

export function coverPalette(title: string): CoverPalette {
  const hash = fnv1a(title)
  const hue = hash % 360
  const hue2 = (hue + 25 + ((hash >>> 9) % 60)) % 360
  return {
    from: `hsl(${hue} 42% 18%)`,
    to: `hsl(${hue2} 52% 34%)`,
    ink: `hsl(${hue} 35% 93%)`,
    accent: `hsl(${(hue + 180) % 360} 70% 72%)`,
  }
}

const LINE = 14
const MAX_LINES = 5

/** The title wrapped by words into at most five short lines. */
export function coverLines(title: string): string[] {
  const lines: string[] = []
  let line = ''
  for (const word of title.trim().split(/\s+/)) {
    if (line && line.length + 1 + word.length > LINE) {
      lines.push(line)
      line = word
    } else {
      line = line ? `${line} ${word}` : word
    }
  }
  if (line) lines.push(line)
  if (lines.length > MAX_LINES) {
    const kept = lines.slice(0, MAX_LINES)
    kept[MAX_LINES - 1] += '…'
    return kept
  }
  return lines
}
