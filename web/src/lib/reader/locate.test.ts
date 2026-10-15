import { expect, it } from 'vitest'
import { scrollTarget, topParagraph } from './locate'

const rects = [{ top: 0, height: 100 }, { top: 120, height: 300 }, { top: 440, height: 50 }]

it('finds the paragraph at the top of the view and how far into it', () => {
  expect(topParagraph(rects, 0)).toEqual({ paragraph: 0, offset: 0 })
  expect(topParagraph(rects, 270)).toEqual({ paragraph: 1, offset: 0.5 })
  expect(topParagraph(rects, 110)).toEqual({ paragraph: 1, offset: 0 }) // in the gap: the next one
  expect(topParagraph(rects, 9999)).toEqual({ paragraph: 2, offset: 1 })
  expect(topParagraph([], 50)).toEqual({ paragraph: 0, offset: 0 })
})

it('scrolls back to the same spot, even in one enormous paragraph', () => {
  expect(scrollTarget(rects, 1, 0.5)).toBe(270)
  expect(scrollTarget(rects, 99, 0)).toBe(440) // a paragraph past the end: the last
  const huge = [{ top: 0, height: 20000 }]
  expect(scrollTarget(huge, 0, topParagraph(huge, 12345).offset)).toBeCloseTo(12345, 0)
})

it('does not slip back a paragraph when scrolling lands a fraction of a pixel short', () => {
  const tight = [{ top: 0, height: 100 }, { top: 100, height: 100 }]
  // scrollTo rounds to whole pixels; the reading line can end up 0.4px above paragraph 1
  expect(topParagraph(tight, 99.6)).toEqual({ paragraph: 1, offset: 0 })
  expect(topParagraph(tight, 98)).toEqual({ paragraph: 0, offset: 0.98 })
})
