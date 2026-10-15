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

it('shows a banner when another device or tab moved on, and adopts only its own save', () => {
  expect(onConflict(stored(theirs), 'pc', 'tab1')).toMatchObject({ kind: 'banner', revision: 5, theirs: { chapter: 1240 } })
  // another tab on this same device: still a banner - it may be far ahead
  expect(onConflict(stored({ ...theirs, device: 'pc', tab: 'tab2' }), 'pc', 'tab1').kind).toBe('banner')
  // this very tab's own save that crossed with another send: just catch up
  expect(onConflict(stored({ ...theirs, device: 'pc', tab: 'tab1' }), 'pc', 'tab1')).toEqual({ kind: 'adopt', revision: 5 })
})

it("prefers this device's own later place when its last save never reached the PC", () => {
  const ownSaved = { ...theirs, device: 'pc', chapter: 1240, paragraph: 5 }
  const got = decideOnOpen(stored(ownSaved), 'pc', { chapter: 1240, paragraph: 40, offset: 0.2 })
  expect(got).toMatchObject({ kind: 'go', place: { chapter: 1240, paragraph: 40, offset: 0.2 } })
})

it('says when it had to move to another chapter, so saving can wait for the reader', () => {
  const moved = decideOnOpen(stored(theirs, { chapter: 1241, paragraph: 0, offset: 0, recovered: 'moved' }), 'pc', null)
  expect(moved).toMatchObject({ kind: 'go', recovered: 'moved' })
})

it('remembers where this device was even when the save failed', () => {
  const here = { chapter: 9, paragraph: 2, offset: 0.1 }
  expect(lastOwnAfterFailure(null, here)).toEqual(here)
  expect(lastOwnAfterFailure({ chapter: 1, paragraph: 0, offset: 0 }, here)).toEqual(here)
})
