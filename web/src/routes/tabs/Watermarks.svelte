<script lang="ts">
  import { AlertTriangle, BookOpen, ChevronDown, Eraser, Loader2, PartyPopper, Plus, ShieldCheck, Sparkles, X } from '@lucide/svelte'
  import { onMount } from 'svelte'
  import { fade, slide } from 'svelte/transition'
  import { api, ApiError } from '../../lib/api'
  import { jobsStore } from '../../lib/events.svelte'
  import { findSpan } from '../../lib/highlight'
  import { toasts } from '../../lib/toasts.svelte'
  import { SIGNAL_LABEL, splitRows } from '../../lib/watermarks'
  import type { BookDetail, Review, ReviewRow } from '../../lib/types'
  import Marked from '../../components/Marked.svelte'
  import PatternEditor from '../../components/PatternEditor.svelte'

  let { book }: { book: BookDetail; onchange?: () => void } = $props()

  const MINIMUMS = [2, 3, 4, 6, 10, 20]
  let min = $state(4)
  let review = $state<Review | null>(null)
  let error = $state<string | null>(null)
  let loading = $state(false)
  let editing = $state(false)
  let editSentence = $state('')

  const cleaning = $derived(jobsStore.byBook(book.name)?.kind === 'clean')

  async function load() {
    loading = true
    try {
      review = await api.review(book.name, min)
      error = null
    } catch (e) {
      error = (e as ApiError).message
    } finally {
      loading = false
    }
  }

  async function keep(row: ReviewRow) {
    if (!review) return
    const before = review.rows
    review.rows = review.rows.filter(r => r.key !== row.key)
    try {
      await api.ignore(book.name, row.text)
    } catch (e) {
      review.rows = before
      toasts.show({ tone: 'bad', title: 'Could not keep that sentence', body: (e as ApiError).message })
    }
  }

  async function dropPhrase(phrase: string) {
    if (!review) return
    try {
      const saved = await api.saveSettings(book.name, {
        values: { remove_phrases: review.phrases.filter(p => p !== phrase) },
      })
      review.phrases = (saved.values.remove_phrases as string[]) ?? []
      toasts.show({
        tone: 'neutral',
        title: 'Pattern removed',
        body: 'Re-clean for the change to reach the text.',
        action: { label: 'Re-clean now', run: () => clean() },
      })
    } catch (e) {
      toasts.show({ tone: 'bad', title: 'Could not remove it', body: (e as ApiError).message })
    }
  }

  async function clean() {
    try {
      jobsStore.track(await api.startJob(book.name, { kind: 'clean' }))
    } catch (e) {
      toasts.show({ tone: 'bad', title: 'Could not start cleaning', body: (e as ApiError).message })
    }
  }

  let showStory = $state(false)
  let confirming = $state<string | null>(null)
  let keepingAll = $state(false)

  async function keepAll(rows: ReviewRow[]) {
    if (!review) return
    keepingAll = true
    const before = review.rows
    const keys = new Set(rows.map(r => r.key))
    review.rows = review.rows.filter(r => !keys.has(r.key))
    try {
      const { ignored } = await api.ignoreAll(book.name, rows.map(r => r.text))
      toasts.show({ tone: 'ok', title: `Kept ${ignored} line${ignored === 1 ? '' : 's'} as the author's own`, body: "They won't be listed again." })
      load() // lines further down the list can now surface
    } catch (e) {
      review.rows = before
      toasts.show({ tone: 'bad', title: 'Could not keep those lines', body: (e as ApiError).message })
    } finally {
      keepingAll = false
    }
  }

  function edit(sentence: string) {
    editSentence = sentence
    editing = true
  }

  onMount(() => {
    load()
    return jobsStore.onFinish(j => j.book === book.name && (j.kind === 'clean' || j.kind === 'update') && load())
  })
</script>

{#snippet item(row: ReviewRow, total: number)}
  {@const share = row.chapters / total}
  <li class="rounded-xl border border-line bg-surface-2/40 p-4" out:slide={{ duration: 200 }}>
    <p class="font-serif text-[1.05rem] leading-snug">{row.text}</p>
    {#if row.signals.length}
      <div class="mt-2 flex flex-wrap gap-1.5">
        {#each row.signals as signal}<span class="chip !border-accent/40 !text-accent">{SIGNAL_LABEL[signal] ?? signal}</span>{/each}
      </div>
    {/if}
    <div class="mt-2.5 flex items-center gap-3">
      <div class="h-1.5 w-28 overflow-hidden rounded-full bg-surface-3">
        <div class="h-full rounded-full bg-accent" style="width: {Math.max(share * 100, 3)}%"></div>
      </div>
      <span class="text-xs text-muted tabular">
        in {row.chapters.toLocaleString('en-GB')} of {total.toLocaleString('en-GB')} chapters · first in {row.first}
      </span>
    </div>
    {#if row.contexts[0]}
      <p class="mt-3 border-l-2 border-line-strong pl-3 text-sm leading-relaxed text-muted">
        <span class="mr-1 text-xs text-faint tabular">ch {row.contexts[0].chapter}</span>
        <Marked text={row.contexts[0].text} span={findSpan(row.contexts[0].text, row.text)} />
      </p>
    {/if}
    {#if confirming === row.key}
      <div class="mt-3 flex flex-wrap items-center gap-2 rounded-lg border border-warn/40 bg-warn/10 px-3 py-2 text-sm">
        <AlertTriangle size={15} class="shrink-0 text-warn" />
        <span class="flex-1">This looks like part of the story. Remove it anyway?</span>
        <button class="btn btn-sm" onclick={() => ((confirming = null), edit(row.text))}>Yes, choose a pattern</button>
        <button class="btn btn-sm btn-ghost" onclick={() => (confirming = null)}>No</button>
      </div>
    {:else}
      <div class="mt-3 flex gap-2">
        {#if row.kind === 'junk'}
          <button class="btn btn-sm hover:!border-accent hover:!text-accent" onclick={() => edit(row.text)}><Eraser size={14} /> Remove…</button>
          <button class="btn btn-sm btn-ghost" onclick={() => keep(row)} title="The author's own: stop listing it">Keep</button>
        {:else}
          <button class="btn btn-sm" onclick={() => keep(row)} title="The author's own: stop listing it">Keep</button>
          <button class="btn btn-sm btn-ghost" onclick={() => (confirming = row.key)}><Eraser size={14} /> Remove…</button>
        {/if}
      </div>
    {/if}
  </li>
{/snippet}

<div class="grid gap-6 lg:grid-cols-[1fr_320px]">
  <section class="card p-5 sm:p-6">
    <div class="flex flex-wrap items-center justify-between gap-3">
      <div>
        <h2 class="font-serif text-xl font-semibold">Repeated sentences</h2>
        <p class="mt-1 text-sm text-muted">Junk the site adds tends to repeat. So do some authors - keep those.</p>
      </div>
      <label class="flex items-center gap-2 text-sm text-muted">
        In at least
        <select class="input !h-9 !w-auto !py-0 tabular" bind:value={min} onchange={load}>
          {#each MINIMUMS as m}<option value={m}>{m}</option>{/each}
        </select>
        chapters
      </label>
    </div>

    {#if cleaning}
      <p class="mt-5 flex items-center gap-2 rounded-lg bg-accent-soft px-3 py-2 text-sm"><Loader2 size={15} class="animate-spin" /> Re-cleaning - the list will refresh when it's done.</p>
    {/if}

    {#if error}
      <div class="mt-6 rounded-xl border border-line bg-surface-2/50 p-6 text-center">
        <p class="text-muted">{error}</p>
        {#if error.includes('clean')}
          <button class="btn btn-primary mt-4" onclick={clean} disabled={cleaning}><Sparkles size={16} /> Clean now</button>
        {/if}
      </div>
    {:else if !review}
      <div class="mt-6 space-y-3">{#each Array(4) as _}<div class="skeleton h-20"></div>{/each}</div>
    {:else}
      {@const groups = splitRows(review.rows)}
      <p class="mt-5 flex items-start gap-2 rounded-lg bg-surface-2/60 px-3 py-2 text-xs text-muted">
        <ShieldCheck size={14} class="mt-px shrink-0 text-ok" />
        Removing is never permanent: your downloaded pages are kept, and deleting a pattern under "Currently removed" and re-cleaning puts the text back.
      </p>

      <h3 class="mt-6 flex items-center gap-2 text-sm font-semibold">
        <Eraser size={15} class="text-accent" /> Looks like site or author notes
        <span class="chip">{groups.junk.length}</span>
      </h3>
      {#if groups.junk.length}
        <ul class="mt-3 space-y-3 {loading ? 'opacity-60' : ''}">
          {#each groups.junk as row (row.key)}
            {@render item(row, review.chapters)}
          {/each}
        </ul>
      {:else}
        <div class="mt-3 rounded-xl border border-line bg-surface-2/50 p-6 text-center" in:fade>
          <PartyPopper size={26} class="mx-auto text-accent" />
          <p class="mt-2 font-serif font-semibold">Nothing that looks like junk</p>
          <p class="mt-1 text-sm text-muted">No repeated line names a website, talks to the reader, or is mostly symbols.</p>
        </div>
      {/if}

      {#if groups.story.length}
        <div class="mt-7 rounded-xl border border-line">
          <button class="flex w-full items-center gap-2 px-4 py-3 text-left text-sm" onclick={() => (showStory = !showStory)} aria-expanded={showStory}>
            <BookOpen size={15} class="text-muted" />
            <span class="font-semibold">Probably the author's writing</span>
            <span class="chip">{groups.story.length}</span>
            <span class="flex-1"></span>
            <ChevronDown size={16} class="text-muted transition-transform {showStory ? 'rotate-180' : ''}" />
          </button>
          {#if showStory}
            <div class="border-t border-line px-4 pb-4 pt-3" transition:slide={{ duration: 200 }}>
              <div class="flex flex-wrap items-center justify-between gap-2">
                <p class="text-sm text-muted">Dialogue and narration the author repeats. Usually best kept.</p>
                <button class="btn btn-sm" onclick={() => keepAll(groups.story)} disabled={keepingAll}>
                  {#if keepingAll}<Loader2 size={14} class="animate-spin" />{/if} Keep all of these
                </button>
              </div>
              <ul class="mt-3 space-y-3 {loading ? 'opacity-60' : ''}">
                {#each groups.story as row (row.key)}
                  {@render item(row, review.chapters)}
                {/each}
              </ul>
            </div>
          {/if}
        </div>
      {/if}
    {/if}
  </section>

  <aside class="card h-fit p-5 sm:p-6">
    <h2 class="font-serif text-lg font-semibold">Currently removed</h2>
    <p class="mt-1 text-sm text-muted">Sentences matching these are taken out when the book is cleaned.</p>
    {#if review?.phrases.length}
      <ul class="mt-4 space-y-2">
        {#each review.phrases as phrase (phrase)}
          <li class="group flex items-center gap-2 rounded-lg border border-line bg-surface-2/50 py-1.5 pl-3 pr-1.5" transition:slide={{ duration: 180 }}>
            <code class="min-w-0 flex-1 truncate font-mono text-xs text-muted" title={phrase}>{phrase}</code>
            <button class="btn btn-ghost btn-icon !h-7 !w-7 shrink-0" onclick={() => dropPhrase(phrase)} aria-label="Stop removing {phrase}">
              <X size={14} />
            </button>
          </li>
        {/each}
      </ul>
    {:else if review}
      <p class="mt-4 text-sm text-faint">None yet.</p>
    {/if}
    <button class="btn btn-sm mt-4 w-full" onclick={() => edit('')} disabled={!review}><Plus size={14} /> Write a pattern</button>
  </aside>
</div>

{#if review}
  <PatternEditor bind:open={editing} name={book.name} sentence={editSentence} phrases={review.phrases} onsaved={load} />
{/if}
