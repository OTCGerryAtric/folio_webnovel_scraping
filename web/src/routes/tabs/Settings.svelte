<script lang="ts">
  import { Code, Loader2, Plus, RotateCcw, Save, X } from '@lucide/svelte'
  import { onMount } from 'svelte'
  import { fly } from 'svelte/transition'
  import { api, ApiError } from '../../lib/api'
  import { jobsStore } from '../../lib/events.svelte'
  import { changes, GROUPS, parseField, type Field } from '../../lib/fields'
  import { toasts } from '../../lib/toasts.svelte'
  import type { BookDetail, SettingsData, SettingValue } from '../../lib/types'

  let { book, onchange }: { book: BookDetail; onchange?: () => void } = $props()

  const KEYS = GROUPS.flatMap(g => g.fields.map(f => f.key))
  const CLEANING = new Set(GROUPS.filter(g => g.affectsCleaning).flatMap(g => g.fields.map(f => f.key)))

  let data = $state<SettingsData | null>(null)
  let edited = $state<Record<string, SettingValue>>({})
  let adding = $state<Record<string, string>>({})
  let raw = $state('')
  let advanced = $state(false)
  let saving = $state(false)
  let error = $state<string | null>(null)

  const saved = $derived(data ? Object.fromEntries(KEYS.map(k => [k, data!.values[k] ?? null])) : {})
  const pending = $derived(data ? changes(saved, edited) : {})
  const count = $derived(advanced ? (data && raw !== data.raw ? 1 : 0) : Object.keys(pending).length)

  function reset(from: SettingsData) {
    data = from
    edited = Object.fromEntries(KEYS.map(k => [k, from.values[k] ?? null]))
    raw = from.raw
    adding = {}
    error = null
  }

  async function load() {
    try {
      reset(await api.settings(book.name))
    } catch (e) {
      error = (e as ApiError).message
    }
  }

  async function save() {
    saving = true
    error = null
    const touched = advanced ? KEYS : Object.keys(pending)
    try {
      const fresh = await api.saveSettings(book.name, advanced ? { raw } : { values: pending })
      reset(fresh)
      onchange?.()
      if (touched.some(k => CLEANING.has(k)) || advanced) {
        toasts.show({
          tone: 'ok',
          title: 'Settings saved',
          body: 'Re-clean so the text follows the new rules.',
          action: { label: 'Re-clean now', run: reclean },
        })
      } else {
        toasts.show({ tone: 'ok', title: 'Settings saved' })
      }
    } catch (e) {
      error = (e as ApiError).message
    } finally {
      saving = false
    }
  }

  async function reclean() {
    try {
      jobsStore.track(await api.startJob(book.name, { kind: 'clean' }))
    } catch (e) {
      toasts.show({ tone: 'bad', title: 'Could not start cleaning', body: (e as ApiError).message })
    }
  }

  function text(field: Field): string {
    const value = edited[field.key]
    return value === null || value === undefined ? '' : String(value)
  }

  function placeholder(field: Field): string {
    const fallback = data?.defaults[field.key]
    return fallback === null || fallback === undefined || fallback === '' ? '' : `Default: ${fallback}`
  }

  function list(key: string): string[] {
    return (edited[key] as string[] | null) ?? []
  }

  function addTo(key: string) {
    const entry = (adding[key] ?? '').trim()
    if (!entry || list(key).includes(entry)) return
    edited[key] = [...list(key), entry]
    adding[key] = ''
  }

  const mentions = (key: string) => !!error && error.includes(key)

  onMount(load)
</script>

{#if !data}
  {#if error}<div class="card p-6 text-bad">{error}</div>{:else}<div class="skeleton h-96"></div>{/if}
{:else}
  <div class="mb-5 flex flex-wrap items-center justify-between gap-3">
    <p class="text-sm text-muted">
      Saved to <code class="font-mono text-xs">book.toml</code>, keeping any notes written in it. Empty fields use the default.
    </p>
    <button class="btn btn-sm" onclick={() => ((advanced = !advanced), reset(data!))}>
      <Code size={14} /> {advanced ? 'Back to the form' : 'Edit the file directly'}
    </button>
  </div>

  {#if error}
    <p class="mb-5 rounded-xl border border-bad/30 bg-bad/10 px-4 py-3 text-sm text-bad" role="alert">{error}</p>
  {/if}

  {#if advanced}
    <div class="card overflow-hidden">
      <textarea
        class="block min-h-[28rem] w-full resize-y bg-transparent p-5 font-mono text-[0.82rem] leading-relaxed text-text focus:outline-none"
        bind:value={raw}
        spellcheck="false"
        aria-label="book.toml"
      ></textarea>
    </div>
  {:else}
    <div class="grid gap-6 lg:grid-cols-2">
      {#each GROUPS as group}
        <section class="card p-5 sm:p-6">
          <h2 class="font-serif text-lg font-semibold">{group.title}</h2>
          <p class="mt-0.5 text-sm text-muted">{group.hint}</p>
          <div class="mt-5 space-y-5">
            {#each group.fields as field}
              {@const set = data.values[field.key] !== null && data.values[field.key] !== undefined}
              <div>
                <div class="mb-1.5 flex items-baseline justify-between gap-3">
                  <label class="text-sm font-medium {mentions(field.key) ? 'text-bad' : ''}" for="f-{field.key}">{field.label}</label>
                  {#if field.key !== 'url_template' && edited[field.key] !== null && (set || pending[field.key] !== undefined)}
                    <button class="flex items-center gap-1 text-xs text-faint hover:text-accent" onclick={() => (edited[field.key] = null)}>
                      <RotateCcw size={11} /> {data.defaults[field.key] === null ? 'clear' : 'default'}
                    </button>
                  {/if}
                </div>
                {#if field.kind === 'bool'}
                  {@const on = (edited[field.key] ?? data.defaults[field.key]) as boolean}
                  <button
                    id="f-{field.key}"
                    role="switch"
                    aria-checked={on}
                    aria-label={field.label}
                    class="relative h-6 w-11 rounded-full transition {on ? 'bg-accent' : 'bg-surface-3'}"
                    onclick={() => (edited[field.key] = !on)}
                  >
                    <span class="absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all {on ? 'left-[22px]' : 'left-0.5'}"></span>
                  </button>
                {:else if field.kind === 'list' || field.kind === 'patterns'}
                  <div class="space-y-1.5">
                    {#each list(field.key) as entry}
                      <div class="flex items-center gap-2 rounded-lg border border-line bg-surface-2/50 py-1 pl-3 pr-1">
                        <code class="min-w-0 flex-1 truncate font-mono text-xs" title={entry}>{entry}</code>
                        <button class="btn btn-ghost btn-icon !h-7 !w-7" aria-label="Remove {entry}" onclick={() => (edited[field.key] = list(field.key).filter(e => e !== entry))}>
                          <X size={13} />
                        </button>
                      </div>
                    {/each}
                    <form class="flex gap-2" onsubmit={e => (e.preventDefault(), addTo(field.key))}>
                      <input id="f-{field.key}" class="input mono !h-9" bind:value={adding[field.key]} placeholder={field.kind === 'patterns' ? 'a regular expression' : 'a CSS selector'} />
                      <button class="btn btn-sm btn-icon !h-9 !w-9 shrink-0" aria-label="Add"><Plus size={15} /></button>
                    </form>
                  </div>
                {:else}
                  <input
                    id="f-{field.key}"
                    class="input {field.mono ? 'mono' : ''} {mentions(field.key) ? '!border-bad' : ''}"
                    type={field.kind === 'int' || field.kind === 'float' ? 'number' : field.kind === 'url' ? 'url' : 'text'}
                    min={field.min}
                    max={field.max}
                    step={field.step ?? (field.kind === 'float' ? 'any' : 1)}
                    value={text(field)}
                    placeholder={placeholder(field)}
                    oninput={e => (edited[field.key] = parseField(field.kind, e.currentTarget.value))}
                  />
                {/if}
                {#if field.help}<p class="mt-1.5 text-xs text-faint">{field.help}</p>{/if}
              </div>
            {/each}
          </div>
        </section>
      {/each}
    </div>
  {/if}

  {#if count}
    <div
      class="fixed inset-x-0 bottom-20 z-40 mx-auto w-[min(560px,calc(100%-2rem))] sm:bottom-6"
      transition:fly={{ y: 24, duration: 200 }}
    >
      <div class="card flex items-center gap-3 px-4 py-3 !shadow-2xl">
        <span class="flex-1 text-sm font-medium">
          {advanced ? 'Unsaved edits to the file' : `${count} unsaved change${count === 1 ? '' : 's'}`}
        </span>
        <button class="btn btn-ghost btn-sm" onclick={() => reset(data!)}>Discard</button>
        <button class="btn btn-primary btn-sm" onclick={save} disabled={saving}>
          {#if saving}<Loader2 size={14} class="animate-spin" />{:else}<Save size={14} />{/if} Save
        </button>
      </div>
    </div>
  {/if}
{/if}
