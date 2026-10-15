<script lang="ts">
  import { ArrowLeft, Download, ExternalLink, Hammer, RefreshCw, Sparkles, Globe } from '@lucide/svelte'
  import { onMount } from 'svelte'
  import { api, ApiError } from '../lib/api'
  import { jobsStore } from '../lib/events.svelte'
  import { timeAgo } from '../lib/ranges'
  import { bookPath, router, type Tab } from '../lib/router.svelte'
  import { toasts } from '../lib/toasts.svelte'
  import type { BookDetail, JobRequest } from '../lib/types'
  import ActionMenu from '../components/ActionMenu.svelte'
  import Activity from '../components/Activity.svelte'
  import ChapterMap from '../components/ChapterMap.svelte'
  import Cover from '../components/Cover.svelte'
  import JobBar from '../components/JobBar.svelte'
  import Tabs from '../components/Tabs.svelte'
  import AddBook from '../components/AddBook.svelte'
  import Watermarks from './tabs/Watermarks.svelte'
  import Files from './tabs/Files.svelte'
  import Settings from './tabs/Settings.svelte'

  let { name, tab }: { name: string; tab: Tab } = $props()

  let book = $state<BookDetail | null>(null)
  let error = $state<string | null>(null)
  let checking = $state(false)
  let settingUp = $state(false)

  const job = $derived(jobsStore.byBook(name))
  const host = $derived(book?.source ? new URL(book.source).host.replace(/^www\./, '') : null)
  const lastUpdated = $derived(
    book?.activity.find(a => (a.kind === 'update' || a.kind === 'download') && a.status === 'done'),
  )

  async function load() {
    try {
      book = await api.book(name)
      error = null
    } catch (e) {
      error = (e as ApiError).message
    }
  }

  async function checkSite(fresh = false) {
    if (!book?.source) return
    checking = true
    try {
      await api.site(name, fresh)
      await load()
    } catch {
      // the hero just shows no site figure
    } finally {
      checking = false
    }
  }

  async function start(request: JobRequest) {
    try {
      jobsStore.track(await api.startJob(name, request))
    } catch (e) {
      toasts.show({ tone: 'bad', title: `Could not start ${request.kind}`, body: (e as ApiError).message })
    }
  }

  onMount(() => {
    load().then(() => checkSite())
    const stop = jobsStore.onFinish(j => j.book === name && load())
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (e.key === 'u' && !e.ctrlKey && !e.metaKey && !['INPUT', 'TEXTAREA'].includes(target.tagName) && !job && book?.ready) {
        start({ kind: 'update' })
      }
    }
    addEventListener('keydown', onKey)
    return () => {
      stop()
      removeEventListener('keydown', onKey)
    }
  })
</script>

<a href="#/" class="mt-6 inline-flex items-center gap-1.5 text-sm text-muted transition hover:text-accent">
  <ArrowLeft size={15} /> Library
</a>

<AddBook bind:open={settingUp} folder={name} />

{#if error}
  <div class="card mt-8 border-bad/40 p-6">
    <p class="text-bad">{error}</p>
    <a class="btn mt-4" href="#/">Back to the library</a>
  </div>
{:else if !book}
  <div class="mt-8 flex flex-col gap-8 sm:flex-row">
    <div class="skeleton mx-auto aspect-[2/3] w-44 sm:mx-0 sm:w-52"></div>
    <div class="flex-1 space-y-4 pt-4">
      <div class="skeleton h-10 w-2/3"></div>
      <div class="skeleton h-4 w-1/3"></div>
      <div class="skeleton mt-8 h-20 w-full"></div>
    </div>
  </div>
{:else}
  <section class="mt-6 flex flex-col items-center gap-8 sm:flex-row sm:items-end">
    <div class="w-40 shrink-0 sm:w-52">
      <Cover name={book.name} title={book.title} author={book.author} hasCover={book.has_cover} />
    </div>
    <div class="w-full min-w-0 flex-1 text-center sm:text-left">
      {#if host && book.source}
        <a href={book.source} target="_blank" rel="noreferrer" class="label inline-flex items-center gap-1.5 hover:text-accent">
          {host} <ExternalLink size={11} />
        </a>
      {/if}
      <h1 class="mt-2 font-serif text-[clamp(1.9rem,4.5vw,3rem)] font-semibold leading-[1.08] tracking-tight text-balance">
        {book.title}
      </h1>
      {#if book.author}<p class="mt-2 text-lg text-muted">by {book.author}</p>{/if}

      <dl class="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
        {#each [
          { label: 'Chapters held', value: book.downloaded.toLocaleString('en-GB') },
          { label: 'On the site', value: book.latest ? book.latest.toLocaleString('en-GB') : checking ? '…' : '—' },
          { label: 'New', value: book.new ? book.new.toLocaleString('en-GB') : '0', accent: book.new > 0 },
          { label: 'Last updated', value: lastUpdated ? timeAgo(lastUpdated.finished ?? lastUpdated.created) : '—' },
        ] as stat}
          <div class="rounded-xl border border-line bg-surface/70 px-4 py-3 text-left">
            <dt class="label">{stat.label}</dt>
            <dd class="mt-1 font-serif text-2xl font-semibold tabular {stat.accent ? 'text-accent' : ''}">{stat.value}</dd>
          </div>
        {/each}
      </dl>

      <div class="mt-5 flex items-center gap-2">
        {#if job}
          <div class="card flex-1 px-4 py-3"><JobBar {job} /></div>
        {:else}
          <button class="btn btn-primary h-11 flex-1 px-6 text-[0.95rem] sm:flex-none" onclick={() => start({ kind: 'update' })} disabled={!book.ready}>
            <RefreshCw size={17} /> Update
            {#if book.new}<span class="rounded-full bg-accent-ink/15 px-2 py-0.5 text-xs tabular">{book.new} new</span>{/if}
          </button>
        {/if}
        <ActionMenu
          actions={[
            { label: 'Download only', hint: 'Fetch new chapters, nothing else', icon: Download, run: () => start({ kind: 'download' }), disabled: !!job || !book.ready },
            { label: 'Clean', hint: 'Rebuild the cleaned text from the raw pages', icon: Sparkles, run: () => start({ kind: 'clean' }), disabled: !!job || !book.ready },
            { label: 'Build…', hint: 'Choose a format and range', icon: Hammer, run: () => router.go(bookPath(name, 'files')), disabled: !book.ready },
            { label: 'Check the site again', hint: 'See whether new chapters are out', icon: Globe, run: () => checkSite(true), disabled: !book.source },
          ]}
        />
      </div>
      {#if !book.ready}
        <div class="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-warn/30 bg-warn/10 px-4 py-3 text-left">
          <p class="flex-1 text-sm text-warn">
            {book.error?.includes('no book.toml') ? 'This folder has no settings yet, so Folio does not know where its chapters come from.' : book.error}
          </p>
          <button class="btn btn-sm btn-primary" onclick={() => (settingUp = true)}>Set up this book</button>
        </div>
      {/if}
    </div>
  </section>

  <Tabs {name} active={tab} />

  <div class="mt-6 sm:mt-8">
    {#if tab === 'overview'}
      <div class="grid gap-6">
        <ChapterMap map={book.map} outputs={book.outputs} buildEvery={book.build_every} />
        <Activity items={book.activity} />
      </div>
    {:else if tab === 'watermarks'}
      <Watermarks {book} />
    {:else if tab === 'files'}
      <Files {book} onchange={load} />
    {:else}
      <Settings {book} onchange={load} />
    {/if}
  </div>
{/if}
