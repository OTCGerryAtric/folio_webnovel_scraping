<script lang="ts">
  // The reader: one chapter at a time, scrolled, set like a book. The place
  // is a paragraph and a fraction of it, so it survives text-size changes.
  import { ArrowLeft, ArrowRight, BookOpen, Loader2 } from '@lucide/svelte'
  import { onMount, tick, untrack } from 'svelte'
  import { api, ApiError } from '../lib/api'
  import { scrollTarget, topParagraph, type Rect, type Spot } from '../lib/reader/locate'
  import { loadSettings, MEASURE_EM, saveSettings, type ReaderSettings } from '../lib/reader/settings'
  import { networkSource, withRetry } from '../lib/reader/source'
  import { bookPath, readPath } from '../lib/router.svelte'
  import { theme as appTheme } from '../lib/theme.svelte'
  import type { Chapter, ChapterList } from '../lib/types'
  import ChapterDrawer from '../components/reader/ChapterDrawer.svelte'
  import SettingsPanel from '../components/reader/SettingsPanel.svelte'
  import Toolbar from '../components/reader/Toolbar.svelte'

  let {
    name,
    chapter = null,
    onspot,
    onchapter,
    start,
  }: {
    name: string
    chapter?: number | null
    /** Hears where the reader is, as it reads. */
    onspot?: (place: { chapter: number } & Spot) => void
    /** Hears each chapter opened. */
    onchapter?: (c: Chapter) => void
    /** Where to open when no chapter is asked for: resolved by the caller (the saved place). */
    start?: (list: ChapterList) => Promise<{ chapter: number; paragraph: number; offset: number; note?: string } | null>
  } = $props()

  const TOP = 72 // the reading line sits just under the toolbar
  const isPhone = matchMedia('(max-width: 640px)').matches
  // The page is rebuilt for each book (keyed in App), so its name is fixed.
  const book = untrack(() => name)
  const source = networkSource(book)

  let settings = $state<ReaderSettings>(loadSettings(isPhone))
  let bookTitle = $state(book)
  let list = $state<ChapterList | null>(null)
  let current = $state<Chapter | null>(null)
  let status = $state<'loading' | 'ready' | 'retrying' | 'error' | 'empty' | 'gone'>('loading')
  let message = $state('')
  let note = $state<string | null>(null)
  let chrome = $state(true)
  let drawer = $state(false)
  let panel = $state(false)
  let progress = $state(0)
  let article = $state<HTMLElement>()

  const readerTheme = $derived(settings.theme ?? (appTheme.current === 'dark' ? 'night' : 'paper'))
  const next = $derived(current?.next ?? null)
  const nextIsGap = $derived(!!current && next !== null && next !== current.number + 1)

  function rects(): Rect[] {
    if (!article) return []
    return [...article.querySelectorAll<HTMLElement>('[data-p]')].map(el => {
      const r = el.getBoundingClientRect()
      return { top: r.top + scrollY, height: r.height }
    })
  }

  function here(): Spot {
    return topParagraph(rects(), scrollY + TOP)
  }

  function goTo(paragraph: number, offset: number) {
    scrollTo({ top: Math.max(0, scrollTarget(rects(), paragraph, offset) - TOP) })
  }

  export async function open(n: number, place?: { paragraph: number; offset: number }, withNote?: string) {
    if (!current) status = 'loading'
    note = withNote ?? null
    try {
      const loaded = await withRetry(() => source.chapter(n), {
        wait: ms => {
          status = 'retrying'
          return new Promise(resolve => setTimeout(resolve, ms))
        },
      })
      current = loaded
      status = 'ready'
      await tick()
      if (place && (place.paragraph > 0 || place.offset > 0)) goTo(place.paragraph, place.offset)
      else scrollTo({ top: 0 })
      // Keep the address on "resume", so a reload comes back to the saved place.
      history.replaceState(null, '', readPath(name))
      onchapter?.(loaded)
      report()
    } catch (e) {
      status = 'error'
      message = (e as ApiError).status === 404 ? `Chapter ${n.toLocaleString('en-GB')} isn't available.` : (e as ApiError).message
    }
  }

  export function place() {
    return current ? { chapter: current.number, ...here() } : null
  }

  function report() {
    if (current && status === 'ready') onspot?.({ chapter: current.number, ...here() })
  }

  function changeSettings(s: ReaderSettings) {
    const spot = here()
    settings = s
    saveSettings(s)
    tick().then(() => goTo(spot.paragraph, spot.offset)) // the same words stay at the top
  }

  // Scrolling: progress, hide the toolbar going down, prefetch, report.
  let lastY = 0
  let frame = 0
  function onScroll() {
    if (frame) return
    frame = requestAnimationFrame(() => {
      frame = 0
      const max = document.documentElement.scrollHeight - innerHeight
      progress = max > 0 ? Math.min(1, scrollY / max) : 1
      if (Math.abs(scrollY - lastY) > 6) {
        chrome = scrollY < lastY || scrollY < 80
        lastY = scrollY
      }
      if (progress > 0.7 && next !== null) source.prefetch(next)
      report()
    })
  }

  function onKey(e: KeyboardEvent) {
    const target = e.target as HTMLElement
    if (['INPUT', 'TEXTAREA', 'SELECT'].includes(target.tagName) || e.ctrlKey || e.metaKey || e.altKey) return
    if (e.key === 'Escape') {
      drawer = panel = false
    } else if (drawer || panel) {
      return
    } else if (e.key === 'ArrowRight' && current?.next != null) {
      open(current.next)
    } else if (e.key === 'ArrowLeft' && current?.prev != null) {
      open(current.prev)
    } else if (e.key === 't') {
      drawer = true
    }
  }

  onMount(() => {
    ;(async () => {
      try {
        const [chapters, summary] = await Promise.all([source.chapters(), api.book(name)])
        list = chapters
        bookTitle = summary.title
      } catch (e) {
        status = (e as ApiError).status === 404 ? 'gone' : 'error'
        message = (e as ApiError).message
        return
      }
      if (!list.chapters.length) return (status = 'empty')
      if (chapter && list.chapters.some(c => c.number === chapter)) return open(chapter)
      const resumed = start ? await start(list) : null
      if (resumed) return open(resumed.chapter, resumed, resumed.note)
      open(chapter ?? list.first!)
    })()
    addEventListener('scroll', onScroll, { passive: true })
    addEventListener('keydown', onKey)
    return () => {
      removeEventListener('scroll', onScroll)
      removeEventListener('keydown', onKey)
      cancelAnimationFrame(frame)
    }
  })
</script>

<div
  class="reader theme-{readerTheme} min-h-dvh"
  style="--r-size: {settings.size}px; --r-leading: {settings.leading}; --r-measure: {MEASURE_EM[settings.measure]}em"
>
  <Toolbar
    {name}
    {bookTitle}
    chapterTitle={current?.title ?? (current ? `Chapter ${current.number}` : '')}
    visible={chrome || drawer || panel}
    {progress}
    ondrawer={() => (drawer = true)}
    onsettings={() => (panel = !panel)}
  />

  <main class="mx-auto px-5 pb-32 pt-24 sm:px-8" style="max-width: calc(var(--r-measure) + 4rem)">
    {#if status === 'loading'}
      <div class="mx-auto mt-16 space-y-4 opacity-40" style="max-width: var(--r-measure)">
        <div class="ph h-8 w-2/3"></div>
        {#each Array(8) as _}<div class="ph h-4"></div>{/each}
      </div>
    {:else if status === 'retrying'}
      <p class="state"><Loader2 size={18} class="animate-spin" /> This chapter is being re-cleaned - trying again…</p>
    {:else if status === 'gone'}
      <div class="state flex-col">
        <p>This book is no longer in your library.</p>
        <a href="#/" class="link">Back to the library</a>
      </div>
    {:else if status === 'empty'}
      <div class="state flex-col">
        <BookOpen size={28} class="opacity-50" />
        <p>Nothing to read yet - this book has no cleaned chapters.</p>
        <a href={bookPath(name)} class="link">Back to the book</a>
      </div>
    {:else if status === 'error'}
      <div class="state flex-col">
        <p>{message}</p>
        <div class="flex gap-4">
          {#if current}<button class="link" onclick={() => open(current!.number)}>Try again</button>{/if}
          <button class="link" onclick={() => (drawer = true)}>Choose a chapter</button>
        </div>
      </div>
    {:else if current}
      {#if note}
        <p class="note mx-auto mb-8" style="max-width: var(--r-measure)" role="status">
          {note} <button class="link ml-1" onclick={() => (note = null)}>OK</button>
        </p>
      {/if}
      <article
        bind:this={article}
        class="text mx-auto {settings.font === 'sans' ? 'sans' : ''} {settings.justify ? 'justify' : ''}"
        style="max-width: var(--r-measure)"
        onclick={() => (chrome = !chrome)}
        role="presentation"
      >
        <p class="kicker">Chapter {current.number.toLocaleString('en-GB')}</p>
        <h1 class="heading">{(current.title ?? '').replace(/^Chapter\s+\d+\s*[:.-]?\s*/i, '') || `Chapter ${current.number}`}</h1>
        {#each current.paragraphs as html, i (i)}
          <!-- server-rendered and escaped (scraper/assemble.py block_html): the only HTML inserted -->
          <div class="para" data-p={i}>{@html html}</div>
        {/each}
      </article>

      <nav class="mx-auto mt-16" style="max-width: var(--r-measure)" aria-label="Chapters">
        {#if next !== null}
          <button class="endcard w-full text-left" onclick={() => open(next!)}>
            <span class="text-xs font-semibold uppercase tracking-[0.12em] opacity-60">
              {nextIsGap ? `Chapter ${(current.number + 1).toLocaleString('en-GB')} isn't downloaded - next available` : 'Next'}
            </span>
            <span class="mt-1 flex items-center justify-between gap-3 text-lg font-semibold">
              Chapter {next.toLocaleString('en-GB')} <ArrowRight size={20} />
            </span>
          </button>
        {:else}
          <p class="endcard text-center opacity-75">You're at the latest chapter you have.</p>
        {/if}
        {#if current.prev !== null}
          <button class="link mt-6 inline-flex items-center gap-1.5 text-sm" onclick={() => open(current!.prev!)}>
            <ArrowLeft size={15} /> Chapter {current.prev.toLocaleString('en-GB')}
          </button>
        {/if}
      </nav>
    {/if}
  </main>

  {#if list}
    <ChapterDrawer bind:open={drawer} {list} current={current?.number ?? null} onpick={n => open(n)} />
  {/if}
  <SettingsPanel bind:open={panel} {settings} onchange={changeSettings} />
</div>

<style>
  .reader {
    background: var(--r-bg);
    color: var(--r-ink);
    transition: background-color 200ms ease, color 200ms ease;
  }
  .theme-paper {
    --r-bg: #fbf8f1;
    --r-ink: #2b2620;
    --r-soft: #6f655a;
    --r-rule: #e6dfd1;
    --r-hover: rgb(60 45 20 / 0.07);
    --r-accent: #b86b17;
  }
  .theme-sepia {
    --r-bg: #f1e6d0;
    --r-ink: #3d3022;
    --r-soft: #77634a;
    --r-rule: #dccdb0;
    --r-hover: rgb(70 50 20 / 0.08);
    --r-accent: #a05a12;
  }
  .theme-night {
    --r-bg: #14161b;
    --r-ink: #c9c4b8;
    --r-soft: #8a8679;
    --r-rule: #262932;
    --r-hover: rgb(255 255 255 / 0.06);
    --r-accent: #e0a24a;
  }
  .text {
    font-family: 'Literata Variable', Georgia, serif;
    font-size: var(--r-size);
    line-height: var(--r-leading);
    font-optical-sizing: auto;
    hyphens: manual;
    overflow-wrap: break-word;
  }
  .text.sans {
    font-family: 'Inter Variable', system-ui, sans-serif;
  }
  .text.justify .para :global(p) {
    text-align: justify;
    hyphens: auto;
  }
  .kicker {
    font-family: 'Inter Variable', sans-serif;
    font-size: 0.72rem;
    font-weight: 650;
    letter-spacing: 0.16em;
    text-transform: uppercase;
    color: var(--r-accent);
    margin: 0 0 0.6rem;
  }
  .heading {
    font-family: 'Fraunces Variable', Georgia, serif;
    font-size: 1.75em;
    line-height: 1.2;
    font-weight: 600;
    margin: 0 0 1.2em;
    text-wrap: balance;
  }
  .para :global(p) {
    margin: 0;
    text-indent: 1.4em;
  }
  .para:first-of-type :global(p),
  .heading + .para :global(p) {
    text-indent: 0;
  }
  .para :global(hr) {
    border: 0;
    margin: 1.4em 0;
    text-align: center;
  }
  .para :global(hr)::after {
    content: '⁂';
    color: var(--r-soft);
  }
  .para :global(h2),
  .para :global(h3),
  .para :global(h4) {
    font-size: 1em;
    font-weight: 650;
    margin: 1.4em 0 0.6em;
  }
  .para :global(blockquote) {
    margin: 0.8em 0;
    padding-left: 1em;
    border-left: 2px solid var(--r-rule);
    color: var(--r-soft);
    font-style: italic;
  }
  .para :global(blockquote p) {
    text-indent: 0;
  }
  .para :global(ul),
  .para :global(ol) {
    margin: 0.6em 0;
    padding-left: 1.4em;
  }
  .state {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 0.75rem;
    margin-top: 6rem;
    text-align: center;
    color: var(--r-soft);
  }
  .link {
    color: var(--r-accent);
    text-decoration: underline;
    text-underline-offset: 3px;
  }
  .note {
    padding: 0.7rem 1rem;
    border-radius: 12px;
    background: var(--r-hover);
    font-size: 0.88rem;
    color: var(--r-soft);
  }
  .endcard {
    display: block;
    padding: 1.1rem 1.25rem;
    border-radius: 16px;
    border: 1px solid var(--r-rule);
    background: var(--r-hover);
    transition: border-color 150ms ease;
  }
  button.endcard:hover {
    border-color: var(--r-accent);
  }
  .ph {
    border-radius: 6px;
    background: var(--r-hover);
  }
</style>
