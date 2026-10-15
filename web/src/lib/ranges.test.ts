import { expect, it } from 'vitest'
import { describeRanges, eta, expandRuns, formatBytes, hostOf, plural } from './ranges'

it('describes ranges like the CLI', () => {
  expect(describeRanges([1, 2, 3, 7])).toBe('1-3, 7')
  expect(describeRanges([])).toBe('none')
})

it('formats sizes', () => {
  expect(formatBytes(512)).toBe('512 B')
  expect(formatBytes(2_400_000)).toBe('2.3 MB')
})

it('estimates time left', () => {
  expect(eta(10, 70, 2)).toBe('about 30s left')
  expect(eta(10, 1210, 2)).toBe('about 10 min left')
  expect(eta(10, null, 2)).toBe('')
})

it('expands chapter-map runs of one state', () => {
  expect(expandRuns([['cleaned', 1, 3], ['raw', 4, 4], ['cleaned', 6, 7]], 'cleaned')).toEqual([1, 2, 3, 6, 7])
})

it('pluralises', () => {
  expect(plural(1, 'chapter')).toBe('1 chapter')
  expect(plural(1274, 'chapter')).toBe('1,274 chapters')
})

it('names the site a source is on, and survives one that is not a full address', () => {
  expect(hostOf('https://www.freewebnovel.com/novel/x')).toBe('freewebnovel.com')
  expect(hostOf('freewebnovel.com/novel/x')).toBeNull()
  expect(hostOf(null)).toBeNull()
})
