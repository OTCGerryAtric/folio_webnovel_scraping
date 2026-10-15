<script lang="ts">
  import type { BookDetail } from '../../lib/types'
  let { book, onchange }: { book: BookDetail; onchange?: () => void } = $props()
</script>

<p class="text-muted">Files for {book.title}</p>
