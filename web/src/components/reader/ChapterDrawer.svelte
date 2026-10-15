<script lang="ts">
  // The chapter list. Books run to thousands of chapters, so only the rows
  // in view are drawn.
  import { Search, X } from '@lucide/svelte'
  import { tick } from 'svelte'
  import { fly, fade } from 'svelte/transition'
  import { chapterRows } from '../../lib/reader/rows'
  import type { ChapterList } from '../../lib/types'

  let {
    open = $bindable(false),
    list,
    current,
    onpick,
  }: { open?: boolean; list: ChapterList; current: number | null; onpick: (n: number) => void } = $props()

  const ROW = 44
  let query = $state('')
  let box = $state<HTMLDivElement>()
  let scrollTop = $state(0)
  let height = $state(600)
  let searchInput = $state<HTMLInputElement>()

  const rows = $derived(chapterRows(list.chapters, query))
  const first = $derived(Math.max(0, Math.floor(scrollTop / ROW) - 8))
  const last = $derived(Math.min(rows.length, Math.ceil((scrollTop + height) / ROW) + 8))
  const where = $derived(list.chapters.findIndex(c => c.number === current))

  // Open on the current chapter.
  $effect(() => {
    if (!open) return
    query = ''
    tick().then(() => {
      if (!box) return
      const index = rows.findIndex(r => r.kind === 'chapter' && r.number === current)
      box.scrollTop = Math.max(0, index * ROW - height / 2 + ROW)
      scrollTop = box.scrollTop
      if (matchMedia('(min-width: 640px)').matches) searchInput?.focus()
    })
  })

  function pick(n: number) {
    open = false
    onpick(n)
  }
</script>

{#if open}
  <button class="fixed inset-0 z-40 bg-black/40" aria-label="Close chapters" onclick={() => (open = false)} transition:fade={{ duration: 150 }}></button>
  <aside
    class="drawer fixed inset-y-0 right-0 z-50 flex w-[min(400px,100%)] flex-col shadow-2xl"
    transition:fly={{ x: 400, duration: 220 }}
    aria-label="Chapters"
  >
    <div class="flex items-center gap-2 px-4 pb-3 pt-[max(1rem,env(safe-area-inset-top))]">
      <h2 class="flex-1 font-serif text-xl font-semibold">Chapters</h2>
      <button class="rbtn" onclick={() => (open = false)} aria-label="Close"><X size={20} /></button>
    </div>
    <div class="px-4 pb-3">
      <label class="search flex items-center gap-2 rounded-xl px-3">
        <Search size={16} class="opacity-60" />
        <input bind:this={searchInput} bind:value={query} class="h-10 w-full bg-transparent text-sm outline-none" placeholder="Number or title" />
      </label>
      <p class="mt-2 text-xs opacity-60">
        {#if where >= 0}Chapter {current?.toLocaleString('en-GB')} · {(where + 1).toLocaleString('en-GB')} of {list.chapters.length.toLocaleString('en-GB')} available{:else}{list.chapters.length.toLocaleString('en-GB')} chapters available{/if}
      </p>
    </div>
    <div
      bind:this={box}
      bind:clientHeight={height}
      class="relative flex-1 overflow-y-auto pb-[env(safe-area-inset-bottom)]"
      onscroll={() => (scrollTop = box!.scrollTop)}
    >
      <div style="height: {rows.length * ROW}px" class="relative">
        {#each rows.slice(first, last) as row, i (first + i)}
          <div class="absolute inset-x-0" style="top: {(first + i) * ROW}px; height: {ROW}px">
            {#if row.kind === 'gap'}
              <p class="flex h-full items-center px-5 text-xs italic opacity-45">
                {row.from === row.to ? `Chapter ${row.from.toLocaleString('en-GB')}` : `Chapters ${row.from.toLocaleString('en-GB')}–${row.to.toLocaleString('en-GB')}`} not downloaded
              </p>
            {:else}
              <button
                class="row flex h-full w-full items-center gap-3 px-5 text-left text-sm {row.number === current ? 'is-current' : ''}"
                onclick={() => pick(row.number)}
              >
                <span class="w-12 shrink-0 text-xs tabular opacity-55">{row.number.toLocaleString('en-GB')}</span>
                <span class="truncate">{row.title ?? `Chapter ${row.number}`}</span>
              </button>
            {/if}
          </div>
        {/each}
      </div>
      {#if !rows.length}<p class="px-5 py-6 text-sm opacity-60">No chapter matches “{query}”.</p>{/if}
    </div>
  </aside>
{/if}

<style>
  .drawer {
    background: var(--r-bg);
    color: var(--r-ink);
    border-left: 1px solid var(--r-rule);
  }
  .search {
    background: var(--r-hover);
  }
  .row:hover {
    background: var(--r-hover);
  }
  .is-current {
    background: var(--r-hover);
    box-shadow: inset 3px 0 0 var(--r-accent);
    font-weight: 600;
  }
</style>
