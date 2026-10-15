import { describe, expect, it } from 'vitest'
import { PositionSync, type SyncDeps } from './positionSync.svelte'
import type { Stored } from './sync'

const mine = { id: 'pc', name: 'Windows · Edge' }
const place = (chapter: number, paragraph = 0) => ({ chapter, paragraph, offset: 0 })
const saved = (chapter: number, device: string, revision: number): Stored => ({
  revision,
  position: { chapter, paragraph: 0, offset: 0, device, device_name: device === 'pc' ? mine.name : 'iPhone · Safari', saved_at: '2026-10-15T20:00:00Z', anchor: 'x' },
  resolved: { chapter, paragraph: 0, offset: 0, recovered: 'exact' },
})

function fake(server: { stored: Stored; reachable?: boolean }) {
  const memory = new Map<string, string>()
  const sent: { base: number; chapter: number; keepalive: boolean }[] = []
  const deps: SyncDeps = {
    device: () => mine,
    get: async () => server.stored,
    save: async (_book, body, keepalive) => {
      if (server.reachable === false) throw new Error('unreachable')
      sent.push({ base: body.base_revision, chapter: body.chapter, keepalive })
      if (body.base_revision !== server.stored.revision) return { ok: false, stored: server.stored }
      server.stored = saved(body.chapter, body.device, server.stored.revision + 1)
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

  it("adopts its own other tab's save quietly", async () => {
    const server = { stored: saved(1, 'pc', 4) }
    const { deps } = fake(server)
    const sync = new PositionSync('B', deps)
    await sync.open()
    server.stored = saved(5, 'pc', 7) // another tab on this same device

    sync.report(place(6))
    await sync.flush()

    expect(sync.banner).toBeNull()
    expect(server.stored.position!.chapter).toBe(6)
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
