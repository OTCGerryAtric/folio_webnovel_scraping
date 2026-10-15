import { describe, expect, it } from 'vitest'
import { planBuild } from './blocks'

const range = (a: number, b: number) => Array.from({ length: b - a + 1 }, (_, i) => a + i)

// The same cases build_blocks and build answer in tests/test_stages.py.
describe('planBuild', () => {
  it('builds one file when every is 0', () => {
    expect(planBuild(range(1228, 1274), { every: 0, bookName: 'S', format: 'epub' }))
      .toEqual([{ first: 1228, last: 1274, name: 'S 1228-1274.epub', chapters: 47 }])
  })

  it('lines blocks up on round numbers and names them by what they hold', () => {
    expect(planBuild(range(1, 1274), { every: 500, bookName: 'S', format: 'epub' }).map(b => b.name))
      .toEqual(['S 1-500.epub', 'S 501-1000.epub', 'S 1001-1274.epub'])
  })

  it('skips empty blocks and respects from and to', () => {
    const cleaned = [...range(1, 10), ...range(1200, 1210)]
    expect(planBuild(cleaned, { every: 500, start: 5, end: 1205, bookName: 'S', format: 'md' }).map(b => b.name))
      .toEqual(['S 5-10.md', 'S 1200-1205.md'])
  })

  it('returns nothing when nothing is cleaned', () => {
    expect(planBuild([], { every: 500, bookName: 'S', format: 'epub' })).toEqual([])
  })
})
