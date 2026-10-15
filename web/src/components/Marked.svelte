<script lang="ts">
  import { splitAt } from '../lib/highlight'

  let { text, span }: { text: string; span: [number, number] | null } = $props()
  const parts = $derived(span ? splitAt(text, span[0], span[1]) : [{ text, hit: false }])
</script>

{#each parts as part}{#if part.hit}<mark class="rounded-[3px] bg-accent-soft px-0.5 text-text ring-1 ring-accent/40">{part.text}</mark>{:else}{part.text}{/if}{/each}
