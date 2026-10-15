<script lang="ts">
  import { Minus, Plus, X } from '@lucide/svelte'
  import { fade, fly } from 'svelte/transition'
  import { getDevice, renameDevice } from '../../lib/reader/device'
  import { LEADING, MEASURES, SIZE, THEMES, type ReaderSettings } from '../../lib/reader/settings'

  let {
    open = $bindable(false),
    settings,
    onchange,
  }: { open?: boolean; settings: ReaderSettings; onchange: (s: ReaderSettings) => void } = $props()

  const SPACING = [
    { label: 'Compact', value: 1.5 },
    { label: 'Comfortable', value: 1.65 },
    { label: 'Airy', value: 1.85 },
  ]
  const SWATCH = { paper: '#fbf8f1', sepia: '#f1e6d0', night: '#14161b' }
  let deviceName = $state(getDevice().name)

  const set = (patch: Partial<ReaderSettings>) => onchange({ ...settings, ...patch })
</script>

{#if open}
  <button class="fixed inset-0 z-40" aria-label="Close text settings" onclick={() => (open = false)} transition:fade={{ duration: 120 }}></button>
  <div
    class="panel fixed inset-x-0 bottom-0 z-50 max-h-[85dvh] overflow-y-auto rounded-t-2xl p-5 pb-[max(1.25rem,env(safe-area-inset-bottom))] shadow-2xl sm:inset-x-auto sm:bottom-auto sm:right-4 sm:top-16 sm:w-80 sm:rounded-2xl"
    transition:fly={{ y: 24, duration: 180 }}
    role="dialog"
    aria-label="Text settings"
  >
    <div class="mb-4 flex items-center justify-between">
      <h2 class="font-serif text-lg font-semibold">Text</h2>
      <button class="rbtn !h-9 !w-9" onclick={() => (open = false)} aria-label="Close"><X size={18} /></button>
    </div>

    <p class="lbl">Size</p>
    <div class="mt-2 flex items-center gap-3">
      <button class="step" onclick={() => set({ size: Math.max(SIZE.min, settings.size - 1) })} disabled={settings.size <= SIZE.min} aria-label="Smaller text"><Minus size={16} /></button>
      <span class="flex-1 text-center font-[Literata_Variable,serif] tabular" style="font-size: {settings.size}px">Aa · {settings.size}</span>
      <button class="step" onclick={() => set({ size: Math.min(SIZE.max, settings.size + 1) })} disabled={settings.size >= SIZE.max} aria-label="Larger text"><Plus size={16} /></button>
    </div>

    <p class="lbl mt-5">Line spacing</p>
    <div class="seg mt-2">
      {#each SPACING as s}
        <button class:on={Math.abs(settings.leading - s.value) < 0.06} onclick={() => set({ leading: Math.min(LEADING.max, s.value) })}>{s.label}</button>
      {/each}
    </div>

    <p class="lbl mt-5">Width</p>
    <div class="seg mt-2">
      {#each MEASURES as m}
        <button class:on={settings.measure === m} onclick={() => set({ measure: m })} class="capitalize">{m}</button>
      {/each}
    </div>

    <p class="lbl mt-5">Theme</p>
    <div class="mt-2 grid grid-cols-4 gap-2">
      <button class="swatch" class:on={settings.theme === null} onclick={() => set({ theme: null })} style="background: linear-gradient(135deg, #fbf8f1 50%, #14161b 50%)" aria-label="Follow Folio's theme"></button>
      {#each THEMES as t}
        <button class="swatch" class:on={settings.theme === t} onclick={() => set({ theme: t })} style="background: {SWATCH[t]}" aria-label="{t} theme"></button>
      {/each}
    </div>
    <div class="mt-1 grid grid-cols-4 gap-2 text-center text-[0.68rem] opacity-60"><span>Auto</span><span>Paper</span><span>Sepia</span><span>Night</span></div>

    <p class="lbl mt-5">Typeface</p>
    <div class="seg mt-2">
      <button class:on={settings.font === 'serif'} onclick={() => set({ font: 'serif' })} style="font-family: 'Literata Variable', serif">Literata</button>
      <button class:on={settings.font === 'sans'} onclick={() => set({ font: 'sans' })} style="font-family: 'Inter Variable', sans-serif">Sans</button>
    </div>

    <label class="mt-5 flex cursor-pointer items-center justify-between text-sm">
      Justify text
      <input type="checkbox" checked={settings.justify} onchange={e => set({ justify: e.currentTarget.checked })} class="h-4 w-4 accent-[var(--r-accent)]" />
    </label>

    <p class="lbl mt-6">This device</p>
    <input
      class="mt-2 h-10 w-full rounded-xl bg-[var(--r-hover)] px-3 text-sm outline-none"
      bind:value={deviceName}
      onchange={() => (deviceName = renameDevice(deviceName).name)}
      aria-label="This device's name"
    />
    <p class="mt-1.5 text-xs opacity-55">Shown on your other devices when they ask where to continue.</p>
  </div>
{/if}

<style>
  .panel {
    background: var(--r-bg);
    color: var(--r-ink);
    border: 1px solid var(--r-rule);
  }
  .lbl {
    font-size: 0.7rem;
    font-weight: 650;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    opacity: 0.55;
  }
  .step {
    display: grid;
    place-items: center;
    width: 2.5rem;
    height: 2.5rem;
    border-radius: 999px;
    background: var(--r-hover);
  }
  .step:disabled {
    opacity: 0.35;
  }
  .seg {
    display: flex;
    gap: 2px;
    padding: 3px;
    border-radius: 12px;
    background: var(--r-hover);
  }
  .seg button {
    flex: 1;
    height: 2.1rem;
    border-radius: 9px;
    font-size: 0.82rem;
  }
  .seg button.on {
    background: var(--r-bg);
    font-weight: 600;
    box-shadow: 0 1px 3px rgb(0 0 0 / 0.15);
  }
  .swatch {
    height: 2.5rem;
    border-radius: 12px;
    border: 1px solid var(--r-rule);
  }
  .swatch.on {
    outline: 2px solid var(--r-accent);
    outline-offset: 2px;
  }
</style>
