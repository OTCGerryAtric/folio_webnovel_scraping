import { expect, it } from 'vitest'
import { chapterRows } from './rows'

const ch = (number: number, title: string | null = `Chapter ${number}`) => ({ number, title, words: 100 })

it('lists chapters with a faint row for each gap', () => {
  expect(chapterRows([ch(1), ch(2), ch(5), ch(6), ch(8)], '')).toEqual([
    { kind: 'chapter', number: 1, title: 'Chapter 1' },
    { kind: 'chapter', number: 2, title: 'Chapter 2' },
    { kind: 'gap', from: 3, to: 4 },
    { kind: 'chapter', number: 5, title: 'Chapter 5' },
    { kind: 'chapter', number: 6, title: 'Chapter 6' },
    { kind: 'gap', from: 7, to: 7 },
    { kind: 'chapter', number: 8, title: 'Chapter 8' },
  ])
})

it('searches by number or by title, without gap rows', () => {
  const list = [ch(1, 'Nightmare Begins'), ch(12, 'Sunny'), ch(120, 'The Black Knight'), ch(1240, null)]
  expect(chapterRows(list, '12').map(r => (r as any).number)).toEqual([12, 120, 1240])
  expect(chapterRows(list, 'knight').map(r => (r as any).number)).toEqual([120])
  expect(chapterRows(list, '1,240').map(r => (r as any).number)).toEqual([1240])
})
