<script lang="ts">
  import { CircleAlert, CircleCheck, CircleSlash, Download, Hammer, RefreshCw, Sparkles } from '@lucide/svelte'
  import { describeJob, KIND_LABEL } from '../lib/describe'
  import { timeAgo } from '../lib/ranges'
  import type { ActivityRecord } from '../lib/types'

  let { items }: { items: ActivityRecord[] } = $props()

  const ICONS = { download: Download, clean: Sparkles, build: Hammer, update: RefreshCw }
  let open = $state<string | null>(null)
</script>

<div class="card p-5 sm:p-6">
  <h2 class="mb-4 font-serif text-xl font-semibold">Activity</h2>
  {#if !items.length}
    <p class="text-sm text-muted">Nothing yet. Updates, cleans and builds will show here.</p>
  {:else}
    <ul class="divide-y divide-line">
      {#each items as item (item.id)}
        {@const Icon = ICONS[item.kind]}
        <li class="py-3 first:pt-0 last:pb-0">
          <button
            class="flex w-full items-start gap-3 text-left"
            onclick={() => (open = open === item.id ? null : item.id)}
            disabled={item.status !== 'error'}
          >
            <span class="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg bg-surface-2 text-muted">
              <Icon size={15} />
            </span>
            <span class="min-w-0 flex-1">
              <span class="flex items-center gap-2 text-sm font-semibold">
                {KIND_LABEL[item.kind]}
                {#if item.status === 'done'}<CircleCheck size={14} class="text-ok" />
                {:else if item.status === 'error'}<CircleAlert size={14} class="text-bad" />
                {:else}<CircleSlash size={14} class="text-faint" />{/if}
              </span>
              <span class="block text-sm text-muted {open === item.id ? '' : 'truncate'} {item.status === 'error' ? '!text-bad' : ''}">
                {describeJob(item)}
              </span>
            </span>
            <span class="shrink-0 text-xs text-faint">{timeAgo(item.finished ?? item.created)}</span>
          </button>
        </li>
      {/each}
    </ul>
  {/if}
</div>
