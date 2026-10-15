import { expect, it } from 'vitest'
import { findSpan, splitAt } from './highlight'

it('splits text around a span', () => {
  expect(splitAt('Read more at site.com today', 13, 21)).toEqual([
    { text: 'Read more at ', hit: false },
    { text: 'site.com', hit: true },
    { text: ' today', hit: false },
  ])
})

it('finds a sentence in its context, ignoring case and spacing', () => {
  const context = 'He ran.  READ more at  Site.com today. She followed.'
  const [start, end] = findSpan(context, 'Read more at Site.com today.')!
  expect(context.slice(start, end)).toBe('READ more at  Site.com today.')
})

it('gives nothing when the sentence is not there', () => {
  expect(findSpan('Nothing to see.', 'Read more')).toBeNull()
})
