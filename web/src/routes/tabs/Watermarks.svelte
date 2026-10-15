<script lang="ts">
  import { Eraser, Loader2, PartyPopper, Plus, Sparkles, X } from '@lucide/svelte'
  import { onMount } from 'svelte'
  import { flip } from 'svelte/animate'
  import { fade, slide } from 'svelte/transition'
  import { api, ApiError } from '../../lib/api'
  import { jobsStore } from '../../lib/events.svelte'
  import { findSpan } from '../../lib/highlight'
  import { toasts } from '../../lib/toasts.svelte'
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

  function edit(sentence: string) {
    editSentence = sentence
    editing = true
  }

  onMount(() => {
    load()
    return jobsStore.onFinish(j => j.book === book.name && (j.kind === 'clean' || j.kind === 'update') && load())
  })
</script>

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
    {:else if !review.rows.length}
      <div class="mt-6 rounded-xl border border-line bg-surface-2/50 p-10 text-center" in:fade>
        <PartyPopper size={30} class="mx-auto text-accent" />
        <p class="mt-3 font-serif text-lg font-semibold">Nothing repeats suspiciously</p>
        <p class="mt-1 text-sm text-muted">Your book looks clean.</p>
      </div>
    {:else}
      <ul class="mt-6 space-y-3 {loading ? 'opacity-60' : ''}">
        {#each review.rows as row (row.key)}
          {@const share = row.chapters / review.chapters}
          <li class="rounded-xl border border-line bg-surface-2/40 p-4" animate:flip={{ duration: 250 }} out:slide={{ duration: 200 }}>
            <p class="font-serif text-[1.05rem] leading-snug">{row.text}</p>
            <div class="mt-2.5 flex items-center gap-3">
              <div class="h-1.5 w-28 overflow-hidden rounded-full bg-surface-3">
                <div class="h-full rounded-full bg-accent" style="width: {Math.max(share * 100, 3)}%"></div>
              </div>
              <span class="text-xs text-muted tabular">
                in {row.chapters.toLocaleString('en-GB')} of {review.chapters.toLocaleString('en-GB')} chapters · first in {row.first}
              </span>
            </div>
            {#if row.contexts[0]}
              <p class="mt-3 border-l-2 border-line-strong pl-3 text-sm leading-relaxed text-muted">
                <span class="mr-1 text-xs text-faint tabular">ch {row.contexts[0].chapter}</span>
                <Marked text={row.contexts[0].text} span={findSpan(row.contexts[0].text, row.text)} />
              </p>
            {/if}
            <div class="mt-3 flex gap-2">
              <button class="btn btn-sm hover:!border-accent hover:!text-accent" onclick={() => edit(row.text)}><Eraser size={14} /> Remove…</button>
              <button class="btn btn-sm btn-ghost" onclick={() => keep(row)} title="The author's own: stop listing it">Keep</button>
            </div>
          </li>
        {/each}
      </ul>
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
