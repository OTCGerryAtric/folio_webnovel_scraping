<script lang="ts">
  import { AlertTriangle } from '@lucide/svelte'
  import { percent, type LiveJob } from '../lib/events.svelte'
  import { plural } from '../lib/ranges'
  import { bookPath } from '../lib/router.svelte'
  import type { BookSummary } from '../lib/types'
  import Cover from './Cover.svelte'
  import ProgressStrip from './ProgressStrip.svelte'

  let { book, job }: { book: BookSummary; job?: LiveJob } = $props()
  const pct = $derived(percent(job))
</script>

<a href={bookPath(book.name)} class="group block rounded-xl outline-offset-4" title={book.error ?? book.title}>
  <div class="relative transition-transform duration-300 ease-out group-hover:-translate-y-1.5">
    <div class="transition-shadow duration-300 {job ? 'ring-2 ring-accent ring-offset-4 ring-offset-bg rounded-[4px_10px_10px_4px] animate-pulse' : ''}">
      <Cover name={book.name} title={book.title} author={book.author} hasCover={book.has_cover} />
    </div>
    {#if book.new > 0 && !job}
      <span class="absolute -right-2 -top-2 rounded-full bg-accent px-2.5 py-1 text-[0.72rem] font-bold text-accent-ink shadow-lg tabular">
        {book.new.toLocaleString('en-GB')} new
      </span>
    {/if}
    {#if !book.ready}
      <span class="absolute left-2 top-2 chip !bg-bg/85 !text-warn"><AlertTriangle size={12} /> Needs setup</span>
    {/if}
    {#if job}
      <div class="absolute inset-x-2 bottom-2 rounded-lg bg-black/70 p-2 text-[0.7rem] text-white backdrop-blur">
        <div class="mb-1 flex justify-between font-semibold capitalize">
          <span>{job.kind}…</span><span class="tabular">{pct === null ? '' : `${pct}%`}</span>
        </div>
        <div class="h-1 overflow-hidden rounded-full bg-white/20">
          <div class="h-full rounded-full bg-accent transition-[width] duration-300" style="width: {pct ?? 35}%"></div>
        </div>
      </div>
    {/if}
  </div>
  <div class="mt-4 space-y-1.5">
    <h3 class="font-serif text-[1.05rem] font-semibold leading-snug line-clamp-2 group-hover:text-accent transition-colors">
      {book.title}
    </h3>
    {#if book.author}<p class="text-sm text-muted truncate">{book.author}</p>{/if}
    <div class="pt-1"><ProgressStrip {book} /></div>
    <p class="text-xs text-faint tabular">
      {plural(book.downloaded, 'chapter')}{#if book.latest} · site has {book.latest.toLocaleString('en-GB')}{/if}
    </p>
  </div>
</a>
