import { expect, it } from 'vitest'
import { coverLines, coverPalette } from './cover'

it('gives each title its own stable palette', () => {
  expect(coverPalette('Shadow Slave')).toEqual(coverPalette('Shadow Slave'))
  expect(coverPalette('Shadow Slave')).not.toEqual(coverPalette('Weakest Beast Tamer'))
})

it('wraps a title onto a few short lines', () => {
  expect(coverLines('Weakest Beast Tamer Gets All SSS Dragons')).toEqual([
    'Weakest Beast', 'Tamer Gets All', 'SSS Dragons',
  ])
  expect(coverLines('Shadow Slave')).toEqual(['Shadow Slave'])
})

it('keeps at most five lines, ending with an ellipsis', () => {
  const lines = coverLines('one two three four five six seven eight nine ten eleven twelve thirteen fourteen')
  expect(lines).toHaveLength(5)
  expect(lines[4].endsWith('…')).toBe(true)
})
