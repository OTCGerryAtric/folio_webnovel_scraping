<script lang="ts">
  import { Ellipsis } from '@lucide/svelte'
  import type { Component } from 'svelte'

  export interface Action {
    label: string
    hint?: string
    icon: Component
    run: () => void
    disabled?: boolean
  }

  let { actions }: { actions: Action[] } = $props()
  let open = $state(false)
  let root: HTMLDivElement

  $effect(() => {
    if (!open) return
    const close = (e: Event) => {
      if (e instanceof KeyboardEvent ? e.key === 'Escape' : !root.contains(e.target as Node)) open = false
    }
    addEventListener('pointerdown', close)
    addEventListener('keydown', close)
    return () => {
      removeEventListener('pointerdown', close)
      removeEventListener('keydown', close)
    }
  })
</script>

<div class="relative" bind:this={root}>
  <button class="btn btn-icon" onclick={() => (open = !open)} aria-haspopup="menu" aria-expanded={open} aria-label="More actions">
    <Ellipsis size={18} />
  </button>
  {#if open}
    <div class="card menu absolute right-0 top-12 z-20 w-64 p-1.5 !shadow-2xl" role="menu">
      {#each actions as action}
        {@const Icon = action.icon}
        <button
          class="flex w-full items-start gap-3 rounded-lg px-3 py-2.5 text-left transition hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-40"
          role="menuitem"
          disabled={action.disabled}
          onclick={() => ((open = false), action.run())}
        >
          <Icon size={16} class="mt-0.5 shrink-0 text-muted" />
          <span>
            <span class="block text-sm font-medium">{action.label}</span>
            {#if action.hint}<span class="block text-xs text-faint">{action.hint}</span>{/if}
          </span>
        </button>
      {/each}
    </div>
  {/if}
</div>

<style>
  .menu {
    animation: pop 140ms ease-out;
    transform-origin: top right;
  }
  @keyframes pop {
    from {
      opacity: 0;
      transform: scale(0.96) translateY(-4px);
    }
  }
</style>
