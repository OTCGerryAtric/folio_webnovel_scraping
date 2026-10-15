<script lang="ts">
  // Every chapter as a cell, coloured by state. With build_every set, each
  // block (1-500, 501-1000, ...) gets its own band, lined up on round
  // numbers like the files built from it. Drawn on a canvas: books run to
  // thousands of chapters.
  import { onMount } from 'svelte'
  import { theme } from '../lib/theme.svelte'
  import type { ChapterState, MapRun, OutputFile } from '../lib/types'

  let { map, outputs, buildEvery }: { map: MapRun[]; outputs: OutputFile[]; buildEvery: number } = $props()

  const STATES: ChapterState[] = ['cleaned', 'raw', 'missing', 'new']
  const LABELS: Record<ChapterState, string> = {
    cleaned: 'cleaned',
    raw: 'downloaded, not cleaned',
    missing: 'missing',
    new: 'new on the site',
  }
  const VARS: Record<ChapterState, string> = { cleaned: '--ok', raw: '--raw', missing: '--bad', new: '--accent' }

  interface Segment {
    label: string | null
    base: number // the chapter at column 0, row 0
    from: number
    to: number
    y: number
    rows: number
    built: boolean
  }

  let wrap: HTMLDivElement
  let canvas: HTMLCanvasElement
  let width = $state(0)
  let tip = $state<{ x: number; y: number; text: string } | null>(null)

  const phone = $derived(width < 640)
  const cell = $derived(phone ? 6 : 8)
  const gap = $derived(phone ? 1.5 : 2)
  const pitch = $derived(cell + gap)
  const gutter = $derived(buildEvery && !phone ? 92 : 0)
  const blockGap = $derived(phone ? 26 : 14)

  const first = $derived(map.length ? map[0][1] : 1)
  const last = $derived(map.length ? map[map.length - 1][2] : 0)
  const counts = $derived(
    Object.fromEntries(STATES.map(s => [s, map.filter(r => r[0] === s).reduce((n, r) => n + r[2] - r[1] + 1, 0)])) as Record<
      ChapterState,
      number
    >,
  )

  const cols = $derived.by(() => {
    const fit = Math.max(1, Math.floor((width - gutter + gap) / pitch))
    if (!buildEvery) return fit
    const neat = [100, 50, 40, 25, 20, 10, 5].find(c => c <= fit && buildEvery % c === 0)
    return neat ?? fit
  })

  const segments = $derived.by((): Segment[] => {
    if (!map.length || !width) return []
    const covered = (a: number, b: number) => outputs.some(o => o.first != null && o.last != null && o.first <= a && o.last >= b)
    if (!buildEvery) {
      const rows = Math.ceil((last - first + 1) / cols)
      return [{ label: null, base: first, from: first, to: last, y: 0, rows, built: false }]
    }
    const out: Segment[] = []
    let y = 0
    for (let block = Math.floor((first - 1) / buildEvery); block <= Math.floor((last - 1) / buildEvery); block++) {
      const base = block * buildEvery + 1
      const from = Math.max(first, base)
      const to = Math.min(last, base + buildEvery - 1)
      const top = phone ? y + 18 : y
      const rows = Math.ceil((to - base + 1) / cols)
      out.push({ label: `${from.toLocaleString('en-GB')}–${to.toLocaleString('en-GB')}`, base, from, to, y: top, rows, built: covered(from, to) })
      y = top + rows * pitch + blockGap
    }
    return out
  })

  const height = $derived(
    segments.length ? Math.max(...segments.map(s => s.y + s.rows * pitch)) : 0,
  )

  function runAt(n: number): MapRun | null {
    return map.find(([, a, b]) => n >= a && n <= b) ?? null
  }

  function draw() {
    if (!canvas || !width) return
    const dpr = devicePixelRatio || 1
    canvas.width = Math.round(width * dpr)
    canvas.height = Math.round(height * dpr)
    canvas.style.height = `${height}px`
    const ctx = canvas.getContext('2d')!
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
    ctx.clearRect(0, 0, width, height)
    const css = getComputedStyle(document.documentElement)
    const colour = Object.fromEntries(STATES.map(s => [s, css.getPropertyValue(VARS[s]).trim()])) as Record<ChapterState, string>
    const radius = phone ? 1.2 : 1.8
    for (const seg of segments) {
      for (const [state, a, b] of map) {
        const lo = Math.max(a, seg.from)
        const hi = Math.min(b, seg.to)
        if (lo > hi) continue
        ctx.fillStyle = colour[state]
        ctx.globalAlpha = state === 'new' ? 0.55 : 1
        for (let n = lo; n <= hi; n++) {
          const i = n - seg.base
          const x = gutter + (i % cols) * pitch
          const y = seg.y + Math.floor(i / cols) * pitch
          ctx.beginPath()
          ctx.roundRect(x, y, cell, cell, radius)
          ctx.fill()
        }
      }
    }
    ctx.globalAlpha = 1
  }

  $effect(() => {
    // redraw whenever the layout, the data or the theme changes
    void [segments, height, cols, theme.current, map]
    requestAnimationFrame(draw)
  })

  function onMove(e: PointerEvent) {
    const rect = canvas.getBoundingClientRect()
    const x = e.clientX - rect.left
    const y = e.clientY - rect.top
    const seg = segments.find(s => y >= s.y && y < s.y + s.rows * pitch)
    const col = Math.floor((x - gutter) / pitch)
    if (!seg || x < gutter || col >= cols) return (tip = null)
    const n = seg.base + Math.floor((y - seg.y) / pitch) * cols + col
    const run = n >= seg.from && n <= seg.to ? runAt(n) : null
    if (!run) return (tip = null)
    const [state, a, b] = run
    const span = a === b ? `Chapter ${a.toLocaleString('en-GB')}` : `Chapters ${a.toLocaleString('en-GB')}–${b.toLocaleString('en-GB')}`
    tip = { x: Math.min(x, width - 220), y, text: `${span} · ${LABELS[state]}` }
  }

  onMount(() => {
    const observer = new ResizeObserver(entries => (width = Math.floor(entries[0].contentRect.width)))
    observer.observe(wrap)
    return () => observer.disconnect()
  })
</script>

<div class="card p-5 sm:p-6">
  <div class="mb-5 flex flex-wrap items-baseline justify-between gap-3">
    <h2 class="font-serif text-xl font-semibold">Chapters</h2>
    <div class="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted">
      {#each STATES as s}
        {#if counts[s]}
          <span class="flex items-center gap-1.5 tabular">
            <span class="h-2.5 w-2.5 rounded-[3px]" style="background: var({VARS[s]}); opacity: {s === 'new' ? 0.6 : 1}"></span>
            {counts[s].toLocaleString('en-GB')} {LABELS[s]}
          </span>
        {/if}
      {/each}
    </div>
  </div>

  <div bind:this={wrap} class="relative" role="img" aria-label="Map of {last} chapters">
    {#if !map.length}
      <p class="py-8 text-center text-muted">No chapters yet. Download to fill the map.</p>
    {/if}
    {#each segments as seg}
      {#if seg.label}
        <div
          class="pointer-events-none absolute left-0 flex flex-col text-[0.72rem] leading-tight tabular {phone ? 'flex-row items-center gap-2' : ''}"
          style="top: {phone ? seg.y - 17 : seg.y - 1}px"
        >
          <span class="font-semibold text-muted">{seg.label}</span>
          <span class={seg.built ? 'text-ok' : 'text-faint'}>{seg.built ? '✓ built' : 'not built'}</span>
        </div>
      {/if}
    {/each}
    <canvas
      bind:this={canvas}
      class="block w-full touch-none"
      onpointermove={onMove}
      onpointerdown={onMove}
      onpointerleave={() => (tip = null)}
    ></canvas>
    {#if tip}
      <div
        class="pointer-events-none absolute z-10 whitespace-nowrap rounded-lg border border-line bg-surface-3 px-2.5 py-1.5 text-xs font-medium shadow-lg"
        style="left: {tip.x}px; top: {tip.y + 14}px"
      >
        {tip.text}
      </div>
    {/if}
  </div>
</div>
