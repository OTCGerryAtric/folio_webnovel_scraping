import { expect, it } from 'vitest'
import { decideOnOpen, differs, lastOwnAfterFailure, onConflict, type Stored } from './sync'

const theirs = {
  chapter: 1240, paragraph: 17, offset: 0.4, device: 'phone', device_name: 'iPhone · Safari',
  saved_at: '2026-10-15T19:00:00Z', anchor: 'the black knight',
}
const stored = (position: any, resolved?: any): Stored => ({
  revision: 5,
  position,
  resolved: resolved ?? (position && { chapter: position.chapter, paragraph: position.paragraph, offset: position.offset, recovered: 'exact' }),
})

it('starts at the beginning when nothing is saved', () => {
  expect(decideOnOpen(stored(null), 'pc', null)).toEqual({ kind: 'start' })
})

it('goes straight there when this device saved it, or has no place of its own', () => {
  expect(decideOnOpen(stored({ ...theirs, device: 'pc' }), 'pc', { chapter: 1, paragraph: 0, offset: 0 }).kind).toBe('go')
  expect(decideOnOpen(stored(theirs), 'pc', null)).toMatchObject({ kind: 'go', place: { chapter: 1240, paragraph: 17 } })
})

it('asks when another device saved somewhere else, but not over a few paragraphs', () => {
  const asked = decideOnOpen(stored(theirs), 'pc', { chapter: 1198, paragraph: 3, offset: 0 })
  expect(asked).toMatchObject({ kind: 'ask', ours: { chapter: 1198 }, theirs: { chapter: 1240, device_name: 'iPhone · Safari' } })
  expect(decideOnOpen(stored(theirs), 'pc', { chapter: 1240, paragraph: 15, offset: 0 }).kind).toBe('go')
})

it('goes to the recovered place, with a note, after a re-clean', () => {
  const got = decideOnOpen(stored(theirs, { chapter: 1240, paragraph: 20, offset: 0.4, recovered: 'anchor' }), 'pc', null)
  expect(got).toMatchObject({ kind: 'go', place: { paragraph: 20 } })
  expect((got as any).note).toMatch(/changed/)
  const moved = decideOnOpen(stored(theirs, { chapter: 1241, paragraph: 0, offset: 0, recovered: 'moved' }), 'pc', null)
  expect((moved as any).note).toMatch(/1,240 isn't available - opened chapter 1,241/)
})

it('compares places', () => {
  expect(differs({ chapter: 1, paragraph: 0, offset: 0 }, { chapter: 2, paragraph: 0, offset: 0 })).toBe(true)
  expect(differs({ chapter: 1, paragraph: 0, offset: 0 }, { chapter: 1, paragraph: 3, offset: 0 })).toBe(false)
  expect(differs({ chapter: 1, paragraph: 0, offset: 0 }, { chapter: 1, paragraph: 4, offset: 0 })).toBe(true)
})

it('shows a banner when another device moved on, and quietly adopts its own other tab', () => {
  expect(onConflict(stored(theirs), 'pc')).toMatchObject({ kind: 'banner', revision: 5, theirs: { chapter: 1240 } })
  expect(onConflict(stored({ ...theirs, device: 'pc' }), 'pc')).toEqual({ kind: 'adopt', revision: 5 })
})

it('remembers where this device was even when the save failed', () => {
  const here = { chapter: 9, paragraph: 2, offset: 0.1 }
  expect(lastOwnAfterFailure(null, here)).toEqual(here)
  expect(lastOwnAfterFailure({ chapter: 1, paragraph: 0, offset: 0 }, here)).toEqual(here)
})
