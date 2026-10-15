<script lang="ts">
  // Running jobs, always in view: a pill that opens into progress bars and
  // the live log. Hidden when nothing is running.
  import { ChevronDown, Loader2 } from '@lucide/svelte'
  import { fly } from 'svelte/transition'
  import { KIND_ACTIVE } from '../lib/describe'
  import { jobsStore, percent } from '../lib/events.svelte'
  import { router } from '../lib/router.svelte'
  import JobBar from './JobBar.svelte'

  let open = $state(false)
  let logBox = $state<HTMLDivElement>()

  const active = $derived(jobsStore.active)
  const lead = $derived(active.find(j => j.status === 'running') ?? active[0])
  const leadPct = $derived(percent(lead))
  const log = $derived(lead?.log.slice(-200) ?? [])
  // On a phone the book page has a tab bar along the bottom; sit above it.
  const lifted = $derived(router.route.page === 'book')

  $effect(() => {
    void log.length
    if (logBox) logBox.scrollTop = logBox.scrollHeight
  })
</script>

{#if lead}
  <div
    class="fixed right-4 z-40 w-[min(400px,calc(100%-2rem))] sm:bottom-6 sm:right-6 {lifted ? 'bottom-20' : 'bottom-4'}"
    transition:fly={{ y: 30, duration: 220 }}
  >
    {#if open}
      <div class="card mb-2 overflow-hidden !shadow-2xl" transition:fly={{ y: 12, duration: 180 }}>
        <div class="space-y-3 border-b border-line p-4">
          {#each active as job (job.id)}
            <div>
              <p class="mb-1.5 truncate text-xs font-semibold text-muted">{job.book}</p>
              <JobBar {job} compact />
            </div>
          {/each}
        </div>
        <div bind:this={logBox} class="max-h-56 overflow-y-auto bg-bg/60 px-4 py-3 font-mono text-[0.7rem] leading-relaxed text-muted">
          {#each log as line}<div class="whitespace-pre-wrap break-words">{line}</div>{:else}<div class="text-faint">Waiting for output…</div>{/each}
        </div>
      </div>
    {/if}
    <button
      class="card ml-auto flex w-full items-center gap-3 px-4 py-3 text-left !shadow-2xl transition hover:border-line-strong"
      onclick={() => (open = !open)}
      aria-expanded={open}
    >
      <Loader2 size={16} class="shrink-0 animate-spin text-accent" />
      <span class="min-w-0 flex-1">
        <span class="block truncate text-sm font-semibold">
          {KIND_ACTIVE[lead.kind]} {lead.book}
        </span>
        <span class="mt-1 block h-1 overflow-hidden rounded-full bg-surface-3">
          <span class="block h-full rounded-full bg-accent transition-[width] duration-300" style="width: {leadPct ?? 30}%"></span>
        </span>
      </span>
      <span class="shrink-0 text-xs text-muted tabular">
        {leadPct === null ? '' : `${leadPct}%`}{#if active.length > 1} · +{active.length - 1}{/if}
      </span>
      <ChevronDown size={16} class="shrink-0 text-muted transition-transform {open ? '' : 'rotate-180'}" />
    </button>
  </div>
{/if}
