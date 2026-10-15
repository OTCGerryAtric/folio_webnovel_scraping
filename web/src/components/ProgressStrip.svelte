<script lang="ts">
  import type { BookSummary } from '../lib/types'

  let { book, height = 6 }: { book: BookSummary; height?: number } = $props()

  const total = $derived(Math.max(book.latest ?? 0, book.last ?? 0, book.downloaded, 1))
  const segments = $derived(
    [
      { key: 'cleaned', n: book.cleaned, color: 'var(--ok)', label: 'cleaned' },
      { key: 'raw', n: Math.max(book.downloaded - book.cleaned, 0), color: 'var(--raw)', label: 'downloaded, not cleaned' },
      { key: 'missing', n: book.missing, color: 'var(--bad)', label: 'missing' },
      { key: 'new', n: book.new, color: 'var(--accent)', label: 'new on the site' },
    ].filter(s => s.n > 0),
  )
  const description = $derived(segments.map(s => `${s.n.toLocaleString('en-GB')} ${s.label}`).join(' · ') || 'nothing yet')
</script>

<div
  class="flex w-full gap-[2px] overflow-hidden rounded-full bg-surface-3"
  style="height: {height}px"
  title={description}
  role="img"
  aria-label={description}
>
  {#each segments as s (s.key)}
    <div
      class="h-full transition-[width] duration-500 ease-out first:rounded-l-full last:rounded-r-full"
      style="width: {(s.n / total) * 100}%; background: {s.color}; opacity: {s.key === 'new' ? 0.75 : 1}"
    ></div>
  {/each}
</div>
