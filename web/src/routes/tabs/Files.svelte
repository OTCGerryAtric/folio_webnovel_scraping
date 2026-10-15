<script lang="ts">
  import { untrack } from 'svelte'
  import { BookOpen, Check, Download, FileText, FileType, Hammer, Trash2 } from '@lucide/svelte'
  import { api, ApiError, fileUrl } from '../../lib/api'
  import { planBuild } from '../../lib/blocks'
  import { jobsStore } from '../../lib/events.svelte'
  import { expandRuns, formatBytes, plural, timeAgo } from '../../lib/ranges'
  import { toasts } from '../../lib/toasts.svelte'
  import type { BookDetail, Format } from '../../lib/types'

  let { book, onchange }: { book: BookDetail; onchange?: () => void } = $props()

  const FORMATS: { id: Format; label: string; hint: string }[] = [
    { id: 'epub', label: 'EPUB', hint: 'Phones, tablets, e-readers' },
    { id: 'pdf', label: 'PDF', hint: 'Print, or any device' },
    { id: 'md', label: 'Markdown', hint: 'Plain text with headings' },
    { id: 'txt', label: 'Text', hint: 'Plain text' },
  ]
  const ICONS: Record<string, typeof BookOpen> = { epub: BookOpen, pdf: FileType, md: FileText, txt: FileText }
  // The page is rebuilt for each book, so its first values are the ones to start from.
  const initial = untrack(() => ({ name: book.name, every: book.build_every }))
  const storeKey = `folio-format:${initial.name}`

  function remembered(): Format {
    try {
      const value = localStorage.getItem(storeKey)
      return FORMATS.some(f => f.id === value) ? (value as Format) : 'epub'
    } catch {
      return 'epub'
    }
  }

  let format = $state<Format>(remembered())
  let mode = $state<'whole' | 'blocks' | 'custom'>(initial.every ? 'blocks' : 'whole')
  let every = $state(initial.every || 500)
  let from = $state<number | null>(null)
  let to = $state<number | null>(null)
  let confirming = $state<string | null>(null)

  $effect(() => {
    try {
      localStorage.setItem(storeKey, format)
    } catch {
      // remembering is a nicety
    }
  })

  const cleaned = $derived(expandRuns(book.map, 'cleaned'))
  const plan = $derived(
    planBuild(cleaned, {
      every: mode === 'blocks' ? every : 0,
      start: mode === 'custom' ? from : null,
      end: mode === 'custom' ? to : null,
      bookName: book.name,
      format,
    }),
  )
  const existing = $derived(new Set(book.outputs.map(o => o.name)))
  const building = $derived(jobsStore.byBook(book.name))
  const files = $derived([...book.outputs].sort((a, b) => (a.first ?? 0) - (b.first ?? 0) || a.name.localeCompare(b.name)))

  async function build() {
    try {
      jobsStore.track(
        await api.startJob(book.name, {
          kind: 'build',
          format,
          every: mode === 'blocks' ? every : 0,
          ...(mode === 'custom' && from ? { start: from } : {}),
          ...(mode === 'custom' && to ? { end: to } : {}),
        }),
      )
    } catch (e) {
      toasts.show({ tone: 'bad', title: 'Could not start the build', body: (e as ApiError).message })
    }
  }

  async function remove(name: string) {
    confirming = null
    try {
      await api.deleteFile(book.name, name)
      onchange?.()
    } catch (e) {
      toasts.show({ tone: 'bad', title: 'Could not delete it', body: (e as ApiError).message })
    }
  }
</script>

<div class="grid gap-6 lg:grid-cols-[400px_1fr]">
  <section class="card h-fit p-5 sm:p-6">
    <h2 class="font-serif text-xl font-semibold">Build</h2>
    <p class="mt-1 text-sm text-muted">Join the cleaned chapters into files to read anywhere.</p>

    <p class="label mt-6">Format</p>
    <div class="mt-2 grid grid-cols-2 gap-2" role="radiogroup" aria-label="Format">
      {#each FORMATS as f}
        <button
          role="radio"
          aria-checked={format === f.id}
          class="rounded-xl border px-3 py-2.5 text-left transition {format === f.id
            ? 'border-accent bg-accent-soft'
            : 'border-line bg-surface-2/40 hover:border-line-strong'}"
          onclick={() => (format = f.id)}
        >
          <span class="block text-sm font-semibold">{f.label}</span>
          <span class="block text-xs text-muted">{f.hint}</span>
        </button>
      {/each}
    </div>

    <p class="label mt-6">Chapters</p>
    <div class="mt-2 space-y-2 text-sm">
      <label class="flex cursor-pointer items-center gap-2.5">
        <input type="radio" bind:group={mode} value="whole" class="accent-[var(--accent)]" /> The whole book in one file
      </label>
      <label class="flex cursor-pointer flex-wrap items-center gap-2.5">
        <input type="radio" bind:group={mode} value="blocks" class="accent-[var(--accent)]" /> In files of
        <input type="number" min="1" step="50" class="input !h-8 !w-24 tabular" bind:value={every} onfocus={() => (mode = 'blocks')} />
        chapters
      </label>
      <label class="flex cursor-pointer flex-wrap items-center gap-2.5">
        <input type="radio" bind:group={mode} value="custom" class="accent-[var(--accent)]" /> From
        <input type="number" min="1" class="input !h-8 !w-24 tabular" bind:value={from} placeholder={String(cleaned[0] ?? 1)} onfocus={() => (mode = 'custom')} />
        to
        <input type="number" min="1" class="input !h-8 !w-24 tabular" bind:value={to} placeholder={String(cleaned.at(-1) ?? '')} onfocus={() => (mode = 'custom')} />
      </label>
    </div>

    <div class="mt-6 rounded-xl border border-line bg-surface-2/40 p-3">
      <p class="label mb-2">Will write {plural(plan.length, 'file')}</p>
      {#if plan.length}
        <ul class="max-h-48 space-y-1 overflow-y-auto text-sm">
          {#each plan as file}
            <li class="flex items-center justify-between gap-3">
              <span class="truncate font-medium" title={file.name}>{file.name}</span>
              <span class="shrink-0 text-xs text-faint tabular">
                {plural(file.chapters, 'chapter')}{#if existing.has(file.name)} · <span class="text-warn">replaces</span>{/if}
              </span>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="text-sm text-muted">No cleaned chapters in that range.</p>
      {/if}
    </div>

    <button class="btn btn-primary mt-5 w-full" onclick={build} disabled={!plan.length || !!building}>
      <Hammer size={16} /> {building ? 'Busy…' : 'Build'}
    </button>
  </section>

  <section class="card p-5 sm:p-6">
    <h2 class="font-serif text-xl font-semibold">Built files</h2>
    <p class="mt-1 text-sm text-muted">Download straight to the device you're using.</p>
    {#if !files.length}
      <p class="mt-6 text-sm text-faint">Nothing built yet.</p>
    {:else}
      <ul class="mt-5 divide-y divide-line">
        {#each files as file (file.name)}
          {@const Icon = ICONS[file.format] ?? FileText}
          <li class="flex flex-wrap items-center gap-3 py-3 sm:flex-nowrap">
            <span class="grid h-10 w-10 shrink-0 place-items-center rounded-lg bg-surface-2 text-accent"><Icon size={18} /></span>
            <span class="min-w-0 flex-1">
              <span class="block truncate text-sm font-semibold" title={file.name}>{file.name}</span>
              <span class="block text-xs text-faint tabular">
                {file.format.toUpperCase()} · {formatBytes(file.size)} · {timeAgo(file.modified)}
              </span>
            </span>
            {#if confirming === file.name}
              <span class="flex items-center gap-1 text-sm">
                Delete?
                <button class="btn btn-sm btn-danger" onclick={() => remove(file.name)}><Check size={14} /> Yes</button>
                <button class="btn btn-sm btn-ghost" onclick={() => (confirming = null)}>No</button>
              </span>
            {:else}
              <a class="btn btn-sm" href={fileUrl(book.name, file.name)} download={file.name}><Download size={14} /> Download</a>
              <button class="btn btn-ghost btn-icon !h-8 !w-8" onclick={() => (confirming = file.name)} aria-label="Delete {file.name}">
                <Trash2 size={15} />
              </button>
            {/if}
          </li>
        {/each}
      </ul>
    {/if}
  </section>
</div>
