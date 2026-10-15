import { expect, it } from 'vitest'
import { SIGNAL_LABEL, splitRows } from './watermarks'

const row = (text: string, kind: 'junk' | 'story', signals: string[] = []) =>
  ({ text, key: text, chapters: 5, first: 1, contexts: [], kind, signals }) as any

it('puts likely site and author notes first, and the story apart', () => {
  const { junk, story } = splitRows([row('Ren shook his head.', 'story'), row('Give it a power stone!', 'junk', ['reader'])])
  expect(junk.map(r => r.text)).toEqual(['Give it a power stone!'])
  expect(story.map(r => r.text)).toEqual(['Ren shook his head.'])
})

it('says each reason in plain words', () => {
  expect(SIGNAL_LABEL.website).toBe('Names a website')
  expect(SIGNAL_LABEL.reader).toBe('Talks to the reader')
  expect(SIGNAL_LABEL.symbols).toBe('Mostly symbols')
})
