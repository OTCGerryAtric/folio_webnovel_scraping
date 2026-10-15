// Marking a match inside a passage of text.

export interface Part {
  text: string
  hit: boolean
}

export function splitAt(text: string, start: number, end: number): Part[] {
  return [
    { text: text.slice(0, start), hit: false },
    { text: text.slice(start, end), hit: true },
    { text: text.slice(end), hit: false },
  ].filter(p => p.text)
}

function escape(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/** Where `sentence` sits in `context`, however its case and spacing differ. */
export function findSpan(context: string, sentence: string): [number, number] | null {
  const words = sentence.trim().split(/\s+/).filter(Boolean)
  if (!words.length) return null
  const match = new RegExp(words.map(escape).join('\\s+'), 'i').exec(context)
  return match ? [match.index, match.index + match[0].length] : null
}
