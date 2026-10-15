import { defineConfig } from 'vitest/config'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import tailwindcss from '@tailwindcss/vite'

// Built into the Python package, so running Folio needs no Node.
export default defineConfig({
  plugins: [svelte(), tailwindcss()],
  build: { outDir: '../scraper/web/static', emptyOutDir: true },
  server: { proxy: { '/api': 'http://127.0.0.1:8765' } },
  test: { include: ['src/**/*.test.ts'] },
})
