<script lang="ts">
  import { fly } from 'svelte/transition'
  import type { Theirs } from '../../lib/reader/sync'

  let { theirs, ongo, onkeep }: { theirs: Theirs; ongo: () => void; onkeep: () => void } = $props()
</script>

<div class="fixed inset-x-0 top-[calc(3.6rem+env(safe-area-inset-top))] z-40 flex justify-center px-3" transition:fly={{ y: -16, duration: 200 }}>
  <div class="banner flex w-full max-w-xl flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl px-4 py-3 text-sm shadow-xl" role="status">
    <p class="min-w-0 flex-1">
      Your <strong>{theirs.device_name}</strong> has moved on to chapter {theirs.resolvedChapter.toLocaleString('en-GB')}.
    </p>
    <div class="flex gap-2">
      <button class="act primary" onclick={ongo}>Go there</button>
      <button class="act" onclick={onkeep}>Keep reading here</button>
    </div>
  </div>
</div>

<style>
  .banner {
    background: var(--r-bg);
    color: var(--r-ink);
    border: 1px solid var(--r-accent);
  }
  .act {
    height: 2.1rem;
    padding: 0 0.85rem;
    border-radius: 999px;
    font-weight: 600;
    background: var(--r-hover);
  }
  .act.primary {
    background: var(--r-accent);
    color: var(--r-bg);
  }
</style>
