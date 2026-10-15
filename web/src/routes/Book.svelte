<script lang="ts">
  import type { Tab } from '../lib/router.svelte'
  let { name, tab }: { name: string; tab: Tab } = $props()
</script>

<h1 class="mt-10 font-serif text-4xl">{name} · {tab}</h1>
