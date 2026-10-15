<script lang="ts">
  import { AlertTriangle, ArrowLeft, Check, Loader2, Search, ShieldCheck } from '@lucide/svelte'
  import { tick, untrack } from 'svelte'
  import { api, ApiError } from '../lib/api'
  import { bookPath, router } from '../lib/router.svelte'
  import { toasts } from '../lib/toasts.svelte'
  import type { Preview } from '../lib/types'
  import Cover from './Cover.svelte'
  import Dialog from './Dialog.svelte'

  // folder: setting up a folder that already exists, so its name is fixed.
  let { open = $bindable(false), url = '', folder = '' }: { open?: boolean; url?: string; folder?: string } = $props()

  let mode = $state<'page' | 'manual'>('page')
  let pageUrl = $state('')
  let preview = $state<Preview | null>(null)
  let name = $state('')
  let download = $state(true)
  let template = $state('')
  let title = $state('')
  let busy = $state(false)
  let error = $state<string | null>(null)
  let urlInput = $state<HTMLInputElement>()

  const templateOk = $derived(template.includes('{n}'))

  // Each time the dialog opens, start afresh - looking up a URL handed in.
  $effect(() => {
    if (!open) return
    const given = url
    const fixed = folder
    untrack(() => {
      mode = 'page'
      preview = null
      error = null
      name = fixed
      pageUrl = given
      if (given) lookUp()
      tick().then(() => urlInput?.focus())
    })
  })

  async function lookUp() {
    if (!pageUrl.trim()) return
    busy = true
    error = null
    preview = null
    try {
      preview = await api.preview(pageUrl.trim())
      if (!folder) name = preview.name
    } catch (e) {
      error = (e as ApiError).message
    } finally {
      busy = false
    }
  }

  async function add() {
    busy = true
    error = null
    try {
      const book =
        mode === 'page'
          ? await api.add({ url: pageUrl.trim(), name: name.trim() || undefined, download })
          : await api.add({ url_template: template.trim(), title: title.trim(), name: name.trim() || undefined, download })
      open = false
      toasts.show({
        tone: 'ok',
        title: `Added ${book.title}`,
        body: download ? 'Downloading its chapters now.' : 'Ready when you are.',
      })
      router.go(bookPath(book.name))
    } catch (e) {
      error = (e as ApiError).message
    } finally {
      busy = false
    }
  }
</script>

<Dialog bind:open title={folder ? `Set up ${folder}` : 'Add a book'}>
  {#if mode === 'page'}
    <form class="space-y-3" onsubmit={e => (e.preventDefault(), lookUp())}>
      <label class="label" for="add-url">The book's main page</label>
      <div class="flex gap-2">
        <input
          id="add-url"
          class="input"
          type="url"
          placeholder="https://…/novel/some-book"
          bind:value={pageUrl}
          onpaste={() => setTimeout(lookUp)}
          bind:this={urlInput}
          required
        />
        <button class="btn btn-icon shrink-0" disabled={busy} aria-label="Look it up">
          {#if busy && !preview}<Loader2 size={18} class="animate-spin" />{:else}<Search size={18} />{/if}
        </button>
      </div>
    </form>

    {#if preview}
      <div class="mt-5 flex gap-5 rounded-xl border border-line bg-surface-2/60 p-4">
        <div class="w-24 shrink-0 sm:w-28">
          <Cover name={preview.name} title={preview.title} author={preview.author} src={preview.cover} />
        </div>
        <div class="min-w-0 space-y-1.5">
          <h3 class="font-serif text-lg font-semibold leading-snug">{preview.title}</h3>
          {#if preview.author}<p class="text-sm text-muted">by {preview.author}</p>{/if}
          <div class="flex flex-wrap gap-1.5 pt-1">
            {#if preview.status}<span class="chip">{preview.status}</span>{/if}
            {#if preview.latest}<span class="chip tabular">{preview.latest.toLocaleString('en-GB')} chapters</span>{/if}
          </div>
          <p class="truncate pt-1 font-mono text-[0.72rem] text-faint" title={preview.url_template}>{preview.url_template}</p>
          <p class="flex items-center gap-1.5 text-xs {preview.site_phrase ? 'text-ok' : 'text-warn'}">
            {#if preview.site_phrase}
              <ShieldCheck size={13} /> Sentences naming the site will be removed
            {:else}
              <AlertTriangle size={13} /> The site's name is too short to remove safely
            {/if}
          </p>
        </div>
      </div>
      <div class="mt-5 space-y-2">
        <label class="label" for="add-name">Folder name</label>
        <input id="add-name" class="input" bind:value={name} readonly={!!folder} />
        {#if preview.exists && name === preview.name}
          <p class="flex items-center gap-1.5 text-sm text-warn">
            <AlertTriangle size={14} /> A book called {preview.name} is already in your library. Choose another name.
          </p>
        {/if}
      </div>
    {/if}

    <button class="mt-5 text-sm text-muted underline-offset-4 hover:text-accent hover:underline" onclick={() => (mode = 'manual')}>
      Site doesn't show book details? Add it by chapter address instead.
    </button>
  {:else}
    <button class="mb-4 flex items-center gap-1.5 text-sm text-muted hover:text-accent" onclick={() => (mode = 'page')}>
      <ArrowLeft size={15} /> Back
    </button>
    <div class="space-y-4">
      <div class="space-y-2">
        <label class="label" for="add-template">Chapter address</label>
        <input id="add-template" class="input mono" placeholder={'https://example.com/book/chapter-{n}'} bind:value={template} />
        <p class="text-xs {template && !templateOk ? 'text-bad' : 'text-faint'}">
          Put <code class="font-mono">{'{n}'}</code> where the chapter number goes.
        </p>
      </div>
      <div class="space-y-2">
        <label class="label" for="add-title">Title</label>
        <input id="add-title" class="input" bind:value={title} />
      </div>
      <div class="space-y-2">
        <label class="label" for="add-folder">Folder name <span class="normal-case tracking-normal text-faint">(optional)</span></label>
        <input id="add-folder" class="input" bind:value={name} placeholder={title} readonly={!!folder} />
      </div>
    </div>
  {/if}

  {#if error}
    <p class="mt-4 rounded-lg border border-bad/30 bg-bad/10 px-3 py-2 text-sm text-bad" role="alert">{error}</p>
  {/if}

  {#snippet footer()}
    <label class="mr-auto flex cursor-pointer items-center gap-2 text-sm text-muted">
      <input type="checkbox" bind:checked={download} class="h-4 w-4 accent-[var(--accent)]" />
      Download chapters now
    </label>
    <button class="btn btn-ghost" onclick={() => (open = false)}>Cancel</button>
    <button
      class="btn btn-primary"
      onclick={add}
      disabled={busy || (mode === 'page' ? !preview || (preview.exists && name === preview.name) : !templateOk || !title.trim())}
    >
      {#if busy && (preview || mode === 'manual')}<Loader2 size={16} class="animate-spin" />{:else}<Check size={16} />{/if}
      Add to library
    </button>
  {/snippet}
</Dialog>
