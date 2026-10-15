<script lang="ts">
  import { X } from '@lucide/svelte'
  import type { Snippet } from 'svelte'

  let {
    open = $bindable(false),
    title,
    wide = false,
    children,
    footer,
  }: { open?: boolean; title: string; wide?: boolean; children: Snippet; footer?: Snippet } = $props()

  let dialog: HTMLDialogElement

  $effect(() => {
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  })
</script>

<dialog
  bind:this={dialog}
  onclose={() => (open = false)}
  onclick={e => e.target === dialog && (open = false)}
  class="sheet m-auto w-full {wide ? 'max-w-2xl' : 'max-w-lg'} bg-transparent p-0 text-text backdrop:bg-black/55 backdrop:backdrop-blur-sm"
>
  {#if open}
    <div class="card flex max-h-[min(88dvh,820px)] flex-col overflow-hidden !shadow-2xl">
      <div class="flex items-center justify-between gap-4 border-b border-line px-6 py-4">
        <h2 class="font-serif text-xl font-semibold">{title}</h2>
        <button class="btn btn-ghost btn-icon btn-sm" onclick={() => (open = false)} aria-label="Close">
          <X size={18} />
        </button>
      </div>
      <div class="overflow-y-auto px-6 py-5">
        {@render children()}
      </div>
      {#if footer}
        <div class="flex flex-wrap justify-end gap-2 border-t border-line bg-surface-2/50 px-6 py-4">
          {@render footer()}
        </div>
      {/if}
    </div>
  {/if}
</dialog>

<style>
  dialog[open] {
    animation: rise 220ms cubic-bezier(0.2, 0.8, 0.2, 1);
  }
  dialog[open]::backdrop {
    animation: fade 220ms ease;
  }
  @keyframes rise {
    from {
      opacity: 0;
      transform: translateY(14px) scale(0.98);
    }
  }
  @keyframes fade {
    from {
      opacity: 0;
    }
  }
  /* On a phone the dialog becomes a sheet from the bottom. */
  @media (max-width: 640px) {
    .sheet {
      margin: auto 0 0;
      max-width: 100%;
    }
    .sheet :global(.card) {
      border-radius: 18px 18px 0 0;
      max-height: 92dvh;
    }
  }
</style>
