<script lang="ts">
  import { Eraser, FolderDown, LayoutGrid, SlidersHorizontal } from '@lucide/svelte'
  import { bookPath, type Tab } from '../lib/router.svelte'

  let { name, active }: { name: string; active: Tab } = $props()

  const TABS = [
    { id: 'overview', label: 'Overview', icon: LayoutGrid },
    { id: 'watermarks', label: 'Watermarks', icon: Eraser },
    { id: 'files', label: 'Files', icon: FolderDown },
    { id: 'settings', label: 'Settings', icon: SlidersHorizontal },
  ] as const
</script>

<!-- Wide screens: tabs under the hero. Phones: a bar along the bottom. -->
<nav class="mt-10 hidden gap-1 border-b border-line sm:flex" aria-label="Book sections">
  {#each TABS as tab}
    {@const Icon = tab.icon}
    <a
      href={bookPath(name, tab.id)}
      class="-mb-px flex items-center gap-2 border-b-2 px-4 py-3 text-sm font-medium transition
        {active === tab.id ? 'border-accent text-text' : 'border-transparent text-muted hover:text-text'}"
      aria-current={active === tab.id ? 'page' : undefined}
    >
      <Icon size={16} />{tab.label}
    </a>
  {/each}
</nav>

<nav
  class="fixed inset-x-0 bottom-0 z-30 grid grid-cols-4 border-t border-line bg-surface/90 pb-[env(safe-area-inset-bottom)] backdrop-blur-xl sm:hidden"
  aria-label="Book sections"
>
  {#each TABS as tab}
    {@const Icon = tab.icon}
    <a
      href={bookPath(name, tab.id)}
      class="flex flex-col items-center gap-1 py-2.5 text-[0.68rem] font-medium {active === tab.id ? 'text-accent' : 'text-muted'}"
      aria-current={active === tab.id ? 'page' : undefined}
    >
      <Icon size={20} />{tab.label}
    </a>
  {/each}
</nav>
