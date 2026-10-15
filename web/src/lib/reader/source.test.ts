import { expect, it } from 'vitest'
import { networkSource, withRetry } from './source'

const chapter = (n: number) => ({ number: n, title: `C${n}`, version: 'v', paragraphs: ['<p>x</p>'], prev: n - 1, next: n + 1 })

it('keeps the last three chapters, so turning back is instant', async () => {
  const asked: number[] = []
  const source = networkSource('B', {
    chapter: async (_b, n) => (asked.push(n), chapter(n)),
    chapters: async () => ({ chapters: [], first: null, last: null }),
  })

  await source.chapter(1)
  await source.chapter(1)
  source.prefetch(2)
  await source.chapter(2)
  await source.chapter(3)
  await source.chapter(4)
  await source.chapter(1)

  expect(asked).toEqual([1, 2, 3, 4, 1]) // 1 again only after falling out of the three kept
})

it('a failed fetch is not kept, so asking again tries again', async () => {
  let calls = 0
  const source = networkSource('B', {
    chapter: async (_b, n) => {
      calls++
      if (calls === 1) throw Object.assign(new Error('nope'), { status: 500 })
      return chapter(n)
    },
    chapters: async () => ({ chapters: [], first: null, last: null }),
  })

  await expect(source.chapter(5)).rejects.toThrow()
  await expect(source.chapter(5)).resolves.toMatchObject({ number: 5 })
})

it('retries a chapter missing for a moment, then gives up', async () => {
  let calls = 0
  const waits: number[] = []
  const wait = async (ms: number) => void waits.push(ms)
  const flaky = async () => {
    calls++
    if (calls < 3) throw Object.assign(new Error('gone'), { status: 404 })
    return 'ok'
  }

  await expect(withRetry(flaky, { wait })).resolves.toBe('ok')
  expect(waits).toEqual([1500, 1500])

  calls = -10
  await expect(withRetry(flaky, { wait })).rejects.toThrow('gone')
})

it('does not retry other errors', async () => {
  let calls = 0
  const broken = async () => {
    calls++
    throw Object.assign(new Error('bad'), { status: 401 })
  }
  await expect(withRetry(broken, { wait: async () => {} })).rejects.toThrow('bad')
  expect(calls).toBe(1)
})
