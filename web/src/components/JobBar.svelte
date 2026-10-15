<script lang="ts">
  import { Loader2, X } from '@lucide/svelte'
  import { api } from '../lib/api'
  import { KIND_LABEL } from '../lib/describe'
  import { percent, type LiveJob } from '../lib/events.svelte'
  import { eta } from '../lib/ranges'

  let { job, compact = false }: { job: LiveJob; compact?: boolean } = $props()

  const pct = $derived(percent(job))
  const left = $derived(job.progress ? eta(job.progress.done, job.progress.total, job.rate) : '')
  let stopping = $state(false)

  async function stop() {
    stopping = true
    await api.cancel(job.id).catch(() => (stopping = false))
  }
</script>

<div class="w-full">
  <div class="flex items-center gap-3">
    <Loader2 size={compact ? 14 : 16} class="shrink-0 animate-spin text-accent" />
    <div class="min-w-0 flex-1">
      <div class="flex items-baseline justify-between gap-3 text-sm">
        <span class="truncate font-semibold">
          {KIND_LABEL[job.kind]}{#if job.status === 'queued'} · waiting its turn{/if}
          {#if job.progress}<span class="font-normal text-muted"> · {job.progress.label}</span>{/if}
        </span>
        <span class="shrink-0 text-xs text-muted tabular">
          {#if left}{left} · {/if}{pct === null ? '' : `${pct}%`}
        </span>
      </div>
      <div class="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-3">
        {#if pct === null}
          <div class="indeterminate h-full w-1/3 rounded-full bg-accent"></div>
        {:else}
          <div class="h-full rounded-full bg-accent transition-[width] duration-300 ease-out" style="width: {pct}%"></div>
        {/if}
      </div>
    </div>
    {#if job.kind === 'download' || job.kind === 'update'}
      <button class="btn btn-ghost btn-sm shrink-0" onclick={stop} disabled={stopping} aria-label="Stop">
        <X size={15} />{#if !compact}{stopping ? 'Stopping…' : 'Stop'}{/if}
      </button>
    {/if}
  </div>
</div>

<style>
  .indeterminate {
    animation: slide 1.3s ease-in-out infinite;
  }
  @keyframes slide {
    from {
      transform: translateX(-100%);
    }
    to {
      transform: translateX(300%);
    }
  }
</style>
