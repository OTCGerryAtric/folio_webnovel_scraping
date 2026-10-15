<script lang="ts">
  import Reader from './Reader.svelte'

  let { name, chapter }: { name: string; chapter: number | null } = $props()
</script>

<Reader {name} {chapter} />
