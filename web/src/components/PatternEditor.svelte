<script lang="ts">
  import { AlertTriangle, Check, Loader2 } from '@lucide/svelte'
  import { untrack } from 'svelte'
  import { api, ApiError } from '../lib/api'
  import { jobsStore } from '../lib/events.svelte'
  import { toasts } from '../lib/toasts.svelte'
  import type { PatternResult } from '../lib/types'
  import Dialog from './Dialog.svelte'
  import Marked from './Marked.svelte'

  let {
    open = $bindable(false),
    name,
    sentence,
    phrases,
    onsaved,
  }: { open?: boolean; name: string; sentence: string; phrases: string[]; onsaved?: () => void } = $props()

  let pattern = $state('')
  let result = $state<PatternResult | null>(null)
  let problem = $state<string | null>(null)
  let testing = $state(false)
  let saving = $state(false)
  let asked = 0

  $effect(() => {
    if (!open) return
    const given = sentence
    untrack(async () => {
      pattern = ''
      result = null
      problem = null
      try {
        pattern = given ? (await api.suggest(name, given)).pattern : ''
      } catch (e) {
        problem = (e as ApiError).message
      }
    })
  })

  // Try the pattern against the whole book as it is typed.
  $effect(() => {
    const current = pattern
    if (!open) return
    const ticket = ++asked
    if (!current.trim()) {
      // nothing to try yet; drop any answer still on its way
      result = null
      testing = false
      return
    }
    testing = true
    const timer = setTimeout(async () => {
      try {
        const answer = await api.testPattern(name, current)
        if (ticket !== asked) return
        result = answer
        problem = null
      } catch (e) {
        if (ticket !== asked) return
        result = null
        problem = (e as ApiError).message
      } finally {
        if (ticket === asked) testing = false
      }
    }, 300)
    return () => clearTimeout(timer)
  })

  const duplicate = $derived(phrases.includes(pattern.trim()))

  async function save() {
    saving = true
    try {
      await api.saveSettings(name, { values: { remove_phrases: [...phrases, pattern.trim()] } })
      jobsStore.track(await api.startJob(name, { kind: 'clean' }))
      toasts.show({ tone: 'ok', title: 'Pattern saved', body: 'Re-cleaning the book with it now.' })
      open = false
      onsaved?.()
    } catch (e) {
      problem = (e as ApiError).message
    } finally {
      saving = false
    }
  }
</script>

<Dialog bind:open title="Remove a watermark" wide>
  {#if sentence}
    <p class="label">The sentence</p>
    <blockquote class="mt-2 border-l-2 border-accent pl-3 font-serif text-[1.02rem] italic text-muted">{sentence}</blockquote>
  {/if}

  <label class="label mt-5 block" for="pattern">Pattern</label>
  <input id="pattern" class="input mono mt-2" bind:value={pattern} spellcheck="false" autocomplete="off" placeholder="words to match" />
  <p class="mt-2 text-xs text-faint">
    Any sentence matching this is removed; the rest of its paragraph stays. Case is ignored, and
    <code class="font-mono text-muted">[\W_]+</code> means any spaces or punctuation.
  </p>

  <div class="mt-5 min-h-24 rounded-xl border border-line bg-surface-2/50 p-4" aria-live="polite">
    {#if !pattern.trim() && !problem}
      <p class="text-sm text-faint">Type a few words, or a pattern, to see what it would remove from the book.</p>
    {:else if problem}
      <p class="flex items-start gap-2 text-sm text-bad"><AlertTriangle size={16} class="mt-0.5 shrink-0" />{problem}</p>
    {:else if result}
      <p class="text-sm">
        Would remove <strong class="font-serif text-lg tabular">{result.sentences.toLocaleString('en-GB')}</strong>
        sentence{result.sentences === 1 ? '' : 's'} in
        <strong class="font-serif text-lg tabular">{result.chapters.toLocaleString('en-GB')}</strong>
        chapter{result.chapters === 1 ? '' : 's'}
        {#if testing}<Loader2 size={14} class="ml-1 inline animate-spin text-faint" />{/if}
      </p>
      {#if result.warning}
        <p class="mt-2 flex items-start gap-2 text-sm text-warn"><AlertTriangle size={15} class="mt-0.5 shrink-0" />{result.warning}</p>
      {/if}
      {#if result.examples.length}
        <ul class="mt-3 max-h-64 space-y-2 overflow-y-auto pr-1">
          {#each result.examples as ex}
            <li class="flex gap-3 text-sm leading-relaxed">
              <span class="w-14 shrink-0 pt-0.5 text-right text-xs text-faint tabular">ch {ex.chapter}</span>
              <span class="text-muted"><Marked text={ex.text} span={[ex.start, ex.end]} /></span>
            </li>
          {/each}
        </ul>
      {/if}
    {:else}
      <p class="flex items-center gap-2 text-sm text-faint"><Loader2 size={14} class="animate-spin" /> Trying it against the book…</p>
    {/if}
  </div>

  {#snippet footer()}
    {#if duplicate}<span class="mr-auto self-center text-sm text-muted">Already in your list.</span>{/if}
    <button class="btn btn-ghost" onclick={() => (open = false)}>Cancel</button>
    <button class="btn btn-primary" onclick={save} disabled={saving || testing || !!problem || !result || !result.sentences || duplicate}>
      {#if saving}<Loader2 size={16} class="animate-spin" />{:else}<Check size={16} />{/if}
      Save & re-clean
    </button>
  {/snippet}
</Dialog>
