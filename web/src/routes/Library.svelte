<script lang="ts">
  import { BookPlus, Plus, RefreshCw } from '@lucide/svelte'
  import { onMount } from 'svelte'
  import { api, ApiError } from '../lib/api'
  import { jobsStore } from '../lib/events.svelte'
  import { plural } from '../lib/ranges'
  import { toasts } from '../lib/toasts.svelte'
  import type { BookSummary } from '../lib/types'
  import AddBook from '../components/AddBook.svelte'
  import BookCard from '../components/BookCard.svelte'

  let books = $state<BookSummary[] | null>(null)
  let error = $state<string | null>(null)
  let adding = $state(false)
  let startUrl = $state('')
  let welcomeUrl = $state('')

  const chapters = $derived((books ?? []).reduce((sum, b) => sum + b.downloaded, 0))
  const updatable = $derived((books ?? []).filter(b => b.ready && b.source))
  const updatingAll = $derived(jobsStore.active.some(j => j.kind === 'update'))

  async function load() {
    try {
      books = await api.books()
      error = null
    } catch (e) {
      error = (e as ApiError).message
    }
  }

  /** Ask each book's site for its latest chapter, three at a time. */
  async function checkSites() {
    const queue = [...updatable]
    const worker = async () => {
      for (let book = queue.shift(); book; book = queue.shift()) {
        try {
          const { summary } = await api.site(book.name)
          books = (books ?? []).map(b => (b.name === summary.name ? summary : b))
        } catch {
          // an unreachable site just means no "new" badge
        }
      }
    }
    await Promise.all([worker(), worker(), worker()])
  }

  async function updateAll() {
    try {
      const started = await api.updateAll()
      started.forEach(job => jobsStore.track(job))
      toasts.show({ tone: 'neutral', title: `Updating ${plural(started.length, 'book')}`, body: 'One at a time, politely.' })
    } catch (e) {
      toasts.show({ tone: 'bad', title: 'Could not start the update', body: (e as ApiError).message })
    }
  }

  function openAdd(url = '') {
    startUrl = url
    adding = true
  }

  onMount(() => {
    load().then(checkSites)
    const stop = jobsStore.onFinish(() => load())
    const onKey = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement
      if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes(target.tagName)) {
        e.preventDefault()
        openAdd()
      }
    }
    addEventListener('keydown', onKey)
    return () => {
      stop()
      removeEventListener('keydown', onKey)
    }
  })
</script>

<section class="pt-10 sm:pt-14">
  <div class="flex flex-wrap items-end justify-between gap-4">
    <div>
      <p class="label mb-2">Folio</p>
      <h1 class="font-serif text-4xl font-semibold tracking-tight sm:text-5xl">Your library</h1>
      {#if books?.length}
        <p class="mt-2 text-muted tabular">
          {plural(books.length, 'book')} · {plural(chapters, 'chapter')}
        </p>
      {/if}
    </div>
    {#if books?.length}
      <div class="flex gap-2">
        <button class="btn" onclick={() => openAdd()}><Plus size={17} /> Add a book</button>
        <button class="btn btn-primary" onclick={updateAll} disabled={updatingAll || !updatable.length}>
          <RefreshCw size={16} class={updatingAll ? 'animate-spin' : ''} />
          {updatingAll ? 'Updating…' : 'Update all'}
        </button>
      </div>
    {/if}
  </div>

  {#if error}
    <div class="card mt-10 border-bad/40 p-5 text-bad">{error}</div>
  {:else if books === null}
    <div class="mt-12 grid grid-cols-2 gap-x-6 gap-y-10 sm:grid-cols-3 lg:grid-cols-5">
      {#each Array(5) as _}
        <div>
          <div class="skeleton aspect-[2/3]"></div>
          <div class="skeleton mt-4 h-4 w-3/4"></div>
          <div class="skeleton mt-2 h-3 w-1/2"></div>
        </div>
      {/each}
    </div>
  {:else if books.length === 0}
    <div class="card relative mt-12 overflow-hidden p-8 sm:p-14">
      <div class="pointer-events-none absolute -right-16 -top-16 h-64 w-64 rounded-full bg-accent-soft blur-2xl"></div>
      <BookPlus size={36} class="text-accent" />
      <h2 class="mt-5 font-serif text-3xl font-semibold">Start your library</h2>
      <p class="mt-2 max-w-lg text-muted">
        Paste the address of a book's main page. Folio reads its title, author and chapters, and keeps it up to date from then on.
      </p>
      <form class="mt-6 flex max-w-xl flex-col gap-2 sm:flex-row" onsubmit={e => (e.preventDefault(), openAdd(welcomeUrl))}>
        <input class="input" type="url" placeholder="https://…/novel/some-book" bind:value={welcomeUrl} required />
        <button class="btn btn-primary">Look it up</button>
      </form>
      <p class="mt-6 text-xs text-faint">Point Folio only at material you have the right to copy.</p>
    </div>
  {:else}
    <div class="mt-12 grid grid-cols-2 gap-x-5 gap-y-12 sm:grid-cols-3 sm:gap-x-7 lg:grid-cols-5">
      {#each books as book (book.name)}
        <BookCard {book} job={jobsStore.byBook(book.name)} />
      {/each}
      <button
        class="group flex aspect-[2/3] flex-col items-center justify-center gap-3 rounded-[4px_10px_10px_4px] border-2 border-dashed border-line-strong text-muted transition hover:-translate-y-1.5 hover:border-accent hover:text-accent"
        onclick={() => openAdd()}
      >
        <span class="grid h-12 w-12 place-items-center rounded-full bg-surface-2 transition group-hover:bg-accent-soft">
          <Plus size={22} />
        </span>
        <span class="font-medium">Add a book</span>
        <kbd class="chip">/</kbd>
      </button>
    </div>
  {/if}
</section>

<AddBook bind:open={adding} url={startUrl} />
