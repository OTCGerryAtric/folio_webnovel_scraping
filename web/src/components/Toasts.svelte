<script lang="ts">
  import { CircleAlert, CircleCheck, Download, Info, X } from '@lucide/svelte'
  import { onMount } from 'svelte'
  import { flip } from 'svelte/animate'
  import { fly } from 'svelte/transition'
  import { fileUrl } from '../lib/api'
  import { describeJob, KIND_LABEL } from '../lib/describe'
  import { jobsStore } from '../lib/events.svelte'
  import { toasts } from '../lib/toasts.svelte'

  // Every job that ends says so, wherever you are in the app.
  onMount(() =>
    jobsStore.onFinish(job => {
      const files = job.summary?.files ?? []
      const tone = job.status === 'done' ? 'ok' : job.status === 'error' ? 'bad' : 'neutral'
      const verb = job.status === 'done' ? 'finished' : job.status === 'error' ? 'failed' : 'stopped'
      toasts.show(
        {
          tone,
          title: `${job.book}: ${KIND_LABEL[job.kind].toLowerCase()} ${verb}`,
          body: describeJob(job),
          action: job.status === 'done' && files.length === 1
            ? { label: 'Download', href: fileUrl(job.book, files[0]), download: true }
            : undefined,
        },
        job.status === 'error' ? 12000 : 7000,
      )
    }),
  )

  const ICONS = { ok: CircleCheck, bad: CircleAlert, neutral: Info }
  const COLOURS = { ok: 'text-ok', bad: 'text-bad', neutral: 'text-muted' }
</script>

<div class="pointer-events-none fixed inset-x-4 top-16 z-50 flex flex-col items-end gap-2 sm:left-auto sm:right-6 sm:w-[380px]" aria-live="polite">
  {#each toasts.items as toast (toast.id)}
    {@const Icon = ICONS[toast.tone]}
    <div
      class="card pointer-events-auto flex w-full items-start gap-3 p-4 !shadow-2xl"
      role={toast.tone === 'bad' ? 'alert' : 'status'}
      animate:flip={{ duration: 200 }}
      in:fly={{ x: 40, duration: 220 }}
      out:fly={{ x: 40, duration: 180 }}
      onmouseenter={() => toasts.hold(toast.id)}
      onmouseleave={() => toasts.schedule(toast.id, 3000)}
    >
      <Icon size={18} class="mt-0.5 shrink-0 {COLOURS[toast.tone]}" />
      <div class="min-w-0 flex-1">
        <p class="text-sm font-semibold">{toast.title}</p>
        {#if toast.body}<p class="mt-0.5 break-words text-sm text-muted">{toast.body}</p>{/if}
        {#if toast.action}
          {#if toast.action.href}
            <a class="btn btn-sm mt-2.5" href={toast.action.href} download={toast.action.download ? '' : undefined} onclick={() => toasts.dismiss(toast.id)}>
              <Download size={14} />{toast.action.label}
            </a>
          {:else}
            <button class="btn btn-sm mt-2.5" onclick={() => (toast.action?.run?.(), toasts.dismiss(toast.id))}>{toast.action.label}</button>
          {/if}
        {/if}
      </div>
      <button class="btn btn-ghost btn-icon !h-7 !w-7 shrink-0" onclick={() => toasts.dismiss(toast.id)} aria-label="Dismiss">
        <X size={14} />
      </button>
    </div>
  {/each}
</div>
