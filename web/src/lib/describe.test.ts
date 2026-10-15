import { expect, it } from 'vitest'
import { describeJob } from './describe'

it('sums up an update', () => {
  expect(describeJob({ kind: 'update', status: 'done', error: null, summary: { fetched: 10, cleaned: 1274, files: ['S 1265-1274.epub'] } }))
    .toBe('Downloaded 10 · Cleaned 1,274 · Built S 1265-1274.epub')
})

it('says when nothing was new', () => {
  expect(describeJob({ kind: 'update', status: 'done', error: null, summary: { fetched: 0, files: [] } })).toBe('Nothing new')
})

it('counts several files', () => {
  expect(describeJob({ kind: 'build', status: 'done', error: null, summary: { files: ['a', 'b', 'c'] } })).toBe('Built 3 files')
})

it('shows the error, or that it was stopped', () => {
  expect(describeJob({ kind: 'build', status: 'error', error: 'file in use', summary: {} })).toBe('file in use')
  expect(describeJob({ kind: 'download', status: 'cancelled', error: null, summary: { fetched: 2 } })).toBe('Stopped · Downloaded 2')
})
