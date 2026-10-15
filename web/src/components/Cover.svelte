<script lang="ts">
  import { coverUrl } from '../lib/api'
  import { coverLines, coverPalette } from '../lib/cover'

  let {
    name,
    title,
    author = null,
    hasCover = false,
    src = null,
  }: { name: string; title: string; author?: string | null; hasCover?: boolean; src?: string | null } = $props()

  const id = $props.id()
  let failed = $state(false)
  const image = $derived(src ?? (hasCover ? coverUrl(name) : null))
  const palette = $derived(coverPalette(title))
  const lines = $derived(coverLines(title))
  const longest = $derived(Math.max(...lines.map(l => l.length), 6))
  const size = $derived(Math.min(30, 300 / longest))
  const lineHeight = $derived(size * 1.12)
  const top = $derived(128 - ((lines.length - 1) * lineHeight) / 2)
</script>

<div class="cover relative aspect-[2/3] w-full overflow-hidden rounded-[4px_10px_10px_4px] bg-surface-2 shadow-cover">
  {#if image && !failed}
    <img src={image} alt="" class="h-full w-full object-cover" loading="lazy" onerror={() => (failed = true)} />
  {:else}
    <svg viewBox="0 0 200 300" class="h-full w-full" role="img" aria-label={title}>
      <defs>
        <linearGradient id="{id}-g" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stop-color={palette.from} />
          <stop offset="1" stop-color={palette.to} />
        </linearGradient>
        <filter id="{id}-n">
          <feTurbulence type="fractalNoise" baseFrequency="0.9" numOctaves="2" stitchTiles="stitch" />
          <feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 0.09 0" />
        </filter>
      </defs>
      <rect width="200" height="300" fill="url(#{id}-g)" />
      <rect width="200" height="300" filter="url(#{id}-n)" />
      <rect x="14" y="14" width="172" height="272" fill="none" stroke={palette.ink} stroke-opacity="0.28" />
      <rect x="18" y="18" width="164" height="264" fill="none" stroke={palette.ink} stroke-opacity="0.14" />
      <circle cx="100" cy="62" r="3" fill={palette.accent} opacity="0.9" />
      <line x1="76" y1="62" x2="92" y2="62" stroke={palette.accent} stroke-opacity="0.7" />
      <line x1="108" y1="62" x2="124" y2="62" stroke={palette.accent} stroke-opacity="0.7" />
      <text
        x="100"
        text-anchor="middle"
        fill={palette.ink}
        font-family="'Fraunces Variable', Georgia, serif"
        font-weight="600"
        font-size={size}
        style="font-variation-settings: 'opsz' 96, 'SOFT' 60"
      >
        {#each lines as line, i}
          <tspan x="100" y={top + i * lineHeight + size * 0.35}>{line}</tspan>
        {/each}
      </text>
      <line
        x1="82"
        y1={top + (lines.length - 1) * lineHeight + size + 6}
        x2="118"
        y2={top + (lines.length - 1) * lineHeight + size + 6}
        stroke={palette.ink}
        stroke-opacity="0.45"
      />
      {#if author}
        <text
          x="100"
          y="258"
          text-anchor="middle"
          fill={palette.ink}
          fill-opacity="0.78"
          font-family="'Inter Variable', sans-serif"
          font-size="9.5"
          font-weight="600"
          letter-spacing="2.2"
        >
          {author.toUpperCase().slice(0, 26)}
        </text>
      {/if}
    </svg>
  {/if}
  <!-- the spine and a little gloss, so every cover reads as a book -->
  <div class="pointer-events-none absolute inset-y-0 left-0 w-[7%] bg-gradient-to-r from-black/45 via-black/15 to-transparent"></div>
  <div class="pointer-events-none absolute inset-y-0 left-[6%] w-px bg-white/15"></div>
  <div class="pointer-events-none absolute inset-0 bg-gradient-to-br from-white/12 via-transparent to-black/20"></div>
</div>
