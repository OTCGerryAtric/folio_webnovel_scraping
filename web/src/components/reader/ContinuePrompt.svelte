<script lang="ts">
  import { Smartphone, Monitor } from '@lucide/svelte'
  import { fade, fly } from 'svelte/transition'
  import { timeAgo } from '../../lib/ranges'
  import type { OwnPlace } from '../../lib/reader/positionSync.svelte'
  import type { Theirs } from '../../lib/reader/sync'

  let {
    theirs,
    ours,
    skew = 0,
    onchoose,
  }: { theirs: Theirs; ours: OwnPlace; skew?: number; onchoose: (which: 'theirs' | 'ours') => void } = $props()

  // saved_at is the server's time; shift it onto this device's clock before comparing.
  const theirsAt = $derived((Date.parse(theirs.saved_at) + skew) / 1000)

  const snippet = (text: string) => {
    const words = text.split(' ').slice(0, 7).join(' ')
    return words ? `“${words.charAt(0).toUpperCase()}${words.slice(1)}…”` : ''
  }
</script>

<div class="fixed inset-0 z-50 grid place-items-end bg-black/45 p-0 sm:place-items-center sm:p-6" transition:fade={{ duration: 150 }}>
  <div
    class="prompt w-full max-w-md rounded-t-2xl p-6 pb-[max(1.5rem,env(safe-area-inset-bottom))] shadow-2xl sm:rounded-2xl"
    role="dialog"
    aria-modal="true"
    aria-labelledby="continue-title"
    transition:fly={{ y: 30, duration: 220 }}
  >
    <h2 id="continue-title" class="font-serif text-xl font-semibold">Where would you like to continue?</h2>
    <p class="mt-1 text-sm opacity-65">You've read this book on another device since you were last here.</p>

    <div class="mt-5 space-y-3">
      <button class="choice" onclick={() => onchoose('theirs')}>
        <Smartphone size={20} class="mt-0.5 shrink-0 opacity-70" />
        <span class="min-w-0">
          <span class="block font-semibold">Chapter {theirs.resolvedChapter.toLocaleString('en-GB')}</span>
          {#if theirs.excerpt}<span class="block truncate text-sm opacity-75">“{theirs.excerpt}”</span>
          {:else if theirs.anchor}<span class="block truncate text-sm opacity-75">{snippet(theirs.anchor)}</span>{/if}
          <span class="mt-0.5 block text-xs opacity-60">{theirs.device_name}, {timeAgo(theirsAt)}</span>
        </span>
      </button>
      <button class="choice" onclick={() => onchoose('ours')}>
        <Monitor size={20} class="mt-0.5 shrink-0 opacity-70" />
        <span class="min-w-0">
          <span class="block font-semibold">Chapter {ours.chapter.toLocaleString('en-GB')}</span>
          <span class="mt-0.5 block text-xs opacity-60">This device, {timeAgo(ours.at / 1000)}</span>
        </span>
      </button>
    </div>
  </div>
</div>

<style>
  .prompt {
    background: var(--r-bg);
    color: var(--r-ink);
    border: 1px solid var(--r-rule);
  }
  .choice {
    display: flex;
    width: 100%;
    gap: 0.9rem;
    padding: 1rem;
    text-align: left;
    border-radius: 14px;
    border: 1px solid var(--r-rule);
    background: var(--r-hover);
    transition: border-color 150ms ease;
  }
  .choice:hover,
  .choice:focus-visible {
    border-color: var(--r-accent);
  }
</style>
