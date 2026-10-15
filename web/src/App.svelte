<script lang="ts">
  import { Moon, Sun, WifiOff } from '@lucide/svelte'
  import { jobsStore } from './lib/events.svelte'
  import { router } from './lib/router.svelte'
  import { theme } from './lib/theme.svelte'
  import Library from './routes/Library.svelte'
  import Book from './routes/Book.svelte'
  import Dock from './components/Dock.svelte'
  import Toasts from './components/Toasts.svelte'
  import Logo from './components/Logo.svelte'

  jobsStore.connect()

  // A short grace period, so a page load doesn't flash "reconnecting".
  let showOffline = $state(false)
  $effect(() => {
    if (jobsStore.connected) {
      showOffline = false
      return
    }
    const timer = setTimeout(() => (showOffline = true), 2500)
    return () => clearTimeout(timer)
  })

  $effect(() => {
    const route = router.route
    document.title = route.page === 'book' ? `${route.name} · Folio` : 'Folio'
  })
</script>

<header class="sticky top-0 z-30 border-b border-line/60 bg-bg/75 backdrop-blur-xl">
  <div class="mx-auto flex h-14 max-w-[1200px] items-center gap-3 px-4 sm:px-6">
    <a href="#/" class="group flex items-center gap-2.5" aria-label="Folio, your library">
      <Logo />
      <span class="font-serif text-[1.35rem] font-semibold tracking-tight">Folio</span>
    </a>
    <div class="flex-1"></div>
    {#if showOffline}
      <span class="chip !border-bad/40 !text-bad" role="status">
        <WifiOff size={13} /> Reconnecting…
      </span>
    {/if}
    <button
      class="btn btn-ghost btn-icon"
      onclick={() => theme.toggle()}
      aria-label={theme.current === 'dark' ? 'Use the light theme' : 'Use the dark theme'}
      title={theme.current === 'dark' ? 'Light theme' : 'Dark theme'}
    >
      {#if theme.current === 'dark'}<Sun size={18} />{:else}<Moon size={18} />{/if}
    </button>
  </div>
</header>

<main class="mx-auto max-w-[1200px] px-4 pb-32 sm:px-6">
  {#if router.route.page === 'book'}
    {#key router.route.name}
      <Book name={router.route.name} tab={router.route.tab} />
    {/key}
  {:else}
    <Library />
  {/if}
</main>

<Dock />
<Toasts />
