import { describe, expect, it } from 'vitest'
import { PositionSync, type SyncDeps } from './positionSync.svelte'
import type { Stored } from './sync'

const mine = { id: 'pc', name: 'Windows · Edge' }
const place = (chapter: number, paragraph = 0) => ({ chapter, paragraph, offset: 0 })
const saved = (chapter: number, device: string, revision: number, tab = '', paragraph = 0, offset = 0): Stored => ({
  revision,
  position: { chapter, paragraph, offset, tab, device, device_name: device === 'pc' ? mine.name : 'iPhone · Safari', saved_at: '2026-10-15T20:00:00Z', anchor: 'x' },
  resolved: { chapter, paragraph, offset, recovered: 'exact' },
})

function fake(server: { stored: Stored; reachable?: boolean; delay?: number }, tab = 'tab1') {
  const memory = new Map<string, string>()
  const sent: { base: number; chapter: number; keepalive: boolean }[] = []
  const deps: SyncDeps = {
    device: () => mine,
    tab: () => tab,
    get: async () => server.stored,
    save: async (_book, body, keepalive) => {
      if (server.reachable === false) throw new Error('unreachable')
      if (server.delay) await new Promise(r => setTimeout(r, server.delay))
      sent.push({ base: body.base_revision, chapter: body.chapter, keepalive })
      if (body.base_revision !== server.stored.revision) return { ok: false, stored: server.stored }
      server.stored = saved(body.chapter, body.device, server.stored.revision + 1, body.tab, body.paragraph, body.offset)
      return { ok: true, stored: server.stored }
    },
    storage: { get: k => memory.get(k) ?? null, set: (k, v) => void memory.set(k, v) },
    now: () => Date.parse('2026-10-15T21:00:00Z'),
  }
  return { deps, sent, memory }
}

describe('PositionSync', () => {
  it('saves on the revision it last saw and moves on with each answer', async () => {
    const server = { stored: saved(1, 'pc', 4) }
    const { deps, sent } = fake(server)
    const sync = new PositionSync('B', deps)
    await sync.open()

    sync.report(place(2))
    await sync.flush()
    sync.report(place(3))
    await sync.flush()

    expect(sent.map(s => [s.base, s.chapter])).toEqual([[4, 2], [5, 3]])
    expect(sent.every(s => s.keepalive)).toBe(true)
  })

  it('shows the banner when another device moved on, and holds further saves', async () => {
    const server = { stored: saved(1, 'pc', 4) }
    const { deps, sent } = fake(server)
    const sync = new PositionSync('B', deps)
    await sync.open()
    server.stored = saved(9, 'phone', 5) // the phone saved meanwhile

    sync.report(place(2))
    await sync.flush()
    sync.report(place(3))
    await sync.flush()

    expect(sync.banner?.resolvedChapter).toBe(9)
    expect(sent).toHaveLength(1) // the refused one; nothing after while the banner is up
    expect(server.stored.position!.chapter).toBe(9)
  })

  it('keep reading here overwrites on purpose, on the newer revision', async () => {
    const server = { stored: saved(1, 'pc', 4) }
    const { deps } = fake(server)
    const sync = new PositionSync('B', deps)
    await sync.open()
    server.stored = saved(9, 'phone', 5)
    sync.report(place(2))
    await sync.flush()

    await sync.keepHere()

    expect(sync.banner).toBeNull()
    expect(server.stored.revision).toBe(6)
    expect(server.stored.position!.chapter).toBe(2)
  })

  it('go there takes the other place and catches up', async () => {
    const server = { stored: saved(1, 'pc', 4) }
    const { deps } = fake(server)
    const sync = new PositionSync('B', deps)
    await sync.open()
    server.stored = saved(9, 'phone', 5)
    sync.report(place(2))
    await sync.flush()

    expect(sync.goThere()).toEqual(place(9))
    sync.report(place(9, 3))
    await sync.flush()
    expect(server.stored.revision).toBe(6)
  })

  it('a stale tab on the same device cannot overwrite a newer place from another tab', async () => {
    const server = { stored: saved(1, 'pc', 4) }
    const a = new PositionSync('B', fake(server, 'tabA').deps)
    const b = new PositionSync('B', fake(server, 'tabB').deps)
    await a.open()
    await b.open()
    b.report(place(50))
    await b.flush() // tab B reads on to chapter 50

    await a.onVisible() // tab A comes back after days
    a.report(place(5))
    await a.flush()

    expect(a.banner?.resolvedChapter).toBe(50)
    expect(server.stored.position!.chapter).toBe(50)
  })

  it('a refusal that is not a conflict leaves saving working', async () => {
    const server = { stored: saved(1, 'pc', 4) }
    const { deps } = fake(server)
    const realSave = deps.save
    let broken = true
    deps.save = async (...args) => {
      if (!broken) return realSave(...args)
      broken = false
      return { ok: false, stored: { error: 'locked' } as unknown as Stored }
    }
    const sync = new PositionSync('B', deps)
    await sync.open()

    sync.report(place(2))
    await sync.flush()
    sync.report(place(3))
    await sync.flush()

    expect(sync.banner).toBeNull()
    expect(server.stored.position!.chapter).toBe(3)
  })

  it('overlapping saves go one at a time, and the latest place wins', async () => {
    const server = { stored: saved(1, 'pc', 4), delay: 20 }
    const { deps, sent } = fake(server)
    const sync = new PositionSync('B', deps)
    await sync.open()

    sync.report(place(2))
    const first = sync.flush()
    sync.report(place(3))
    const second = sync.flush() // the tab hides while the first is still in flight
    const third = sync.flush() // and pagehide fires too
    await Promise.all([first, second, third])

    expect(server.stored.position!.chapter).toBe(3)
    // only the latest place is sent, once: no older place lands after it, no repeat on pagehide
    expect(sent.map(s => s.chapter)).toEqual([3])
  })

  it('a small move inside one enormous paragraph is still saved', async () => {
    const server = { stored: saved(1, 'pc', 4) }
    const { deps } = fake(server)
    const sync = new PositionSync('B', deps)
    await sync.open()

    sync.report({ chapter: 1, paragraph: 0, offset: 0.5 })
    await sync.flush()
    sync.report({ chapter: 1, paragraph: 0, offset: 0.505 }) // a couple of lines in a 20,000px paragraph
    await sync.flush()

    expect(server.stored.position!.offset).toBe(0.505)
  })

  it('keeps note of where this device is while the banner is up', async () => {
    const server = { stored: saved(1, 'pc', 4) }
    const { deps } = fake(server)
    const sync = new PositionSync('B', deps)
    await sync.open()
    server.stored = saved(9, 'phone', 5)
    sync.report(place(2))
    await sync.flush()

    sync.report(place(7)) // reading on under the banner
    await sync.flush()

    expect(sync.lastOwn()).toMatchObject({ chapter: 7 })
  })

  it('keep reading here saves the place it is given, even with nothing pending', async () => {
    const server = { stored: saved(1, 'pc', 4) }
    const { deps } = fake(server)
    const sync = new PositionSync('B', deps)
    await sync.open()
    server.stored = saved(9, 'phone', 5)
    await sync.onVisible()

    await sync.keepHere(place(4, 2))

    expect(server.stored.position).toMatchObject({ chapter: 4, paragraph: 2 })
  })

  it('holds saving until the reader acts, after landing somewhere it had to choose', async () => {
    const server = { stored: saved(1, 'pc', 4) }
    const { deps, sent } = fake(server)
    const sync = new PositionSync('B', deps)
    await sync.open()

    sync.hold()
    sync.report(place(300))
    await sync.flush()
    expect(sent).toHaveLength(0)
    expect(sync.lastOwn()).toBeNull()

    sync.release()
    sync.report(place(301))
    await sync.flush()
    expect(server.stored.position!.chapter).toBe(301)
  })

  it("knows how far its clock is from the server's", async () => {
    const server = { stored: { ...saved(1, 'pc', 4), now: '2026-10-15T19:00:00Z' } as Stored }
    const sync = new PositionSync('B', fake(server).deps) // its clock says 21:00
    await sync.open()
    expect(sync.skew).toBe(2 * 3600 * 1000)
  })

  it('keeps where this device was when the PC cannot be reached, so next time it asks', async () => {
    const server = { stored: saved(1, 'pc', 4), reachable: true }
    const { deps } = fake(server)
    const sync = new PositionSync('B', deps)
    await sync.open()
    server.reachable = false

    sync.report(place(8, 2))
    await sync.flush()

    server.reachable = true
    server.stored = saved(12, 'phone', 5)
    const decision = await new PositionSync('B', deps).open()
    expect(decision).toMatchObject({ kind: 'ask', ours: { chapter: 8, paragraph: 2 } })
  })

  it('notices on returning to the tab that another device moved on', async () => {
    const server = { stored: saved(1, 'pc', 4) }
    const { deps } = fake(server)
    const sync = new PositionSync('B', deps)
    await sync.open()
    server.stored = saved(30, 'phone', 5)

    await sync.onVisible()

    expect(sync.banner?.resolvedChapter).toBe(30)
  })
})
