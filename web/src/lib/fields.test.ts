import { expect, it } from 'vitest'
import { changes, GROUPS, parseField } from './fields'

it('reports only what changed, with a cleared field sent as empty', () => {
  const saved = { delay: 2, title: 'Shadow Slave', author: null, strip_patterns: ['a'] }
  const edited = { delay: 2, title: 'Shadow Slave!', author: null, strip_patterns: [] as string[] }

  expect(changes(saved, edited)).toEqual({ title: 'Shadow Slave!', strip_patterns: [] })
  expect(changes(saved, { ...saved, delay: null })).toEqual({ delay: '' })
})

it('parses what is typed into a field by its kind', () => {
  expect(parseField('float', '2.5')).toBe(2.5)
  expect(parseField('int', '500')).toBe(500)
  expect(parseField('int', '')).toBeNull()
  expect(parseField('text', '  div#article ')).toBe('div#article')
  expect(parseField('text', '')).toBeNull()
})

it('covers the settings the form edits, and not the watermark lists', () => {
  const keys = GROUPS.flatMap(g => g.fields.map(f => f.key))
  expect(keys).toContain('build_every')
  expect(keys).toContain('content_selector')
  expect(keys).not.toContain('remove_phrases')
  expect(keys).not.toContain('review_ignore')
})
