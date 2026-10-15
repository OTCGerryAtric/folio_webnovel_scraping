// Where the reader is in a chapter, as a paragraph and a fraction of it -
// not a scroll offset, which changes with text size and screen width.

export interface Rect {
  top: number
  height: number
}

export interface Spot {
  paragraph: number
  offset: number
}

const clamp = (n: number) => Math.min(1, Math.max(0, n))

/** The paragraph at `viewTop` (paragraph rectangles in the same coordinates), and how far into it. */
export function topParagraph(rects: Rect[], viewTop: number): Spot {
  for (let i = 0; i < rects.length; i++) {
    const { top, height } = rects[i]
    if (top + height > viewTop) {
      return { paragraph: i, offset: height > 0 ? clamp((viewTop - top) / height) : 0 }
    }
  }
  return rects.length ? { paragraph: rects.length - 1, offset: 1 } : { paragraph: 0, offset: 0 }
}

/** The scroll position that puts `paragraph`, `offset` of the way in, at the top. */
export function scrollTarget(rects: Rect[], paragraph: number, offset: number): number {
  if (!rects.length) return 0
  const rect = rects[Math.min(Math.max(paragraph, 0), rects.length - 1)]
  return rect.top + clamp(offset) * rect.height
}
