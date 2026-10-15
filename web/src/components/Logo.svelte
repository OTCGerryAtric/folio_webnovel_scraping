<script lang="ts">
  let { size = 26 }: { size?: number } = $props()
</script>

<svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" class="transition-transform duration-300 group-hover:-rotate-6">
  <rect width="32" height="32" rx="8" fill="var(--surface-2)" stroke="var(--line-strong)" />
  <path d="M9 8.5c2.6-.9 5-.6 7 .9v14.2c-2-1.5-4.4-1.8-7-.9z" fill="var(--accent)" />
  <path d="M23 8.5c-2.6-.9-5-.6-7 .9v14.2c2-1.5 4.4-1.8 7-.9z" fill="var(--accent)" opacity="0.55" />
</svg>
