<script lang="ts">
  import { ArrowLeft, List, Type } from '@lucide/svelte'
  import { bookPath } from '../../lib/router.svelte'

  let {
    name,
    bookTitle,
    chapterTitle,
    visible,
    progress,
    ondrawer,
    onsettings,
  }: {
    name: string
    bookTitle: string
    chapterTitle: string
    visible: boolean
    progress: number
    ondrawer: () => void
    onsettings: () => void
  } = $props()
</script>

<header class="bar fixed inset-x-0 top-0 z-30 transition-transform duration-300 {visible ? '' : '-translate-y-full'}">
  <div class="mx-auto flex h-14 max-w-5xl items-center gap-1 px-2 sm:px-4">
    <a href={bookPath(name)} class="rbtn" aria-label="Back to {bookTitle}"><ArrowLeft size={20} /></a>
    <div class="min-w-0 flex-1 px-2 text-center">
      <p class="truncate text-[0.7rem] font-semibold uppercase tracking-[0.12em] opacity-60">{bookTitle}</p>
      <p class="truncate text-sm font-medium">{chapterTitle}</p>
    </div>
    <button class="rbtn" onclick={ondrawer} aria-label="Chapters" title="Chapters (t)"><List size={20} /></button>
    <button class="rbtn" onclick={onsettings} aria-label="Text settings" title="Text settings"><Type size={20} /></button>
  </div>
  <div class="h-[2px] w-full bg-[var(--r-rule)]">
    <div class="h-full bg-[var(--r-accent)] transition-[width] duration-150" style="width: {Math.round(progress * 1000) / 10}%"></div>
  </div>
</header>

<style>
  .bar {
    background: color-mix(in oklab, var(--r-bg) 88%, transparent);
    backdrop-filter: blur(14px);
    color: var(--r-ink);
    border-bottom: 1px solid var(--r-rule);
    padding-top: env(safe-area-inset-top);
  }
  :global(.rbtn) {
    display: grid;
    place-items: center;
    width: 2.75rem;
    height: 2.75rem;
    border-radius: 999px;
    color: inherit;
    opacity: 0.8;
    transition: background-color 150ms ease, opacity 150ms ease;
  }
  :global(.rbtn:hover) {
    opacity: 1;
    background: var(--r-hover);
  }
</style>
