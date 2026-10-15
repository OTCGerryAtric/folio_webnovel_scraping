import { expect, it } from 'vitest'
import { parseRoute, readPath } from './routes'

it('reads the reader routes', () => {
  expect(parseRoute('#/read/Shadow%20Slave')).toEqual({ page: 'read', name: 'Shadow Slave', chapter: null })
  expect(parseRoute('#/read/Shadow%20Slave/1240')).toEqual({ page: 'read', name: 'Shadow Slave', chapter: 1240 })
  expect(parseRoute('#/read/B/abc')).toEqual({ page: 'read', name: 'B', chapter: null })
})

it('keeps the existing routes', () => {
  expect(parseRoute('#/')).toEqual({ page: 'library' })
  expect(parseRoute('#/book/B/files')).toEqual({ page: 'book', name: 'B', tab: 'files' })
  expect(parseRoute('#/book/B/nonsense')).toEqual({ page: 'book', name: 'B', tab: 'overview' })
})

it('builds reader links', () => {
  expect(readPath('Shadow Slave')).toBe('#/read/Shadow%20Slave')
  expect(readPath('Shadow Slave', 12)).toBe('#/read/Shadow%20Slave/12')
})
