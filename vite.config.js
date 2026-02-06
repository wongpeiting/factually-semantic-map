import { defineConfig } from 'vite'
import { svelte } from '@sveltejs/vite-plugin-svelte'
import path from 'path'

export default defineConfig({
  plugins: [svelte()],
  resolve: {
    alias: {
      "$components": path.resolve('./src/components'),
      "$data": path.resolve("./src/data"),
      "$routes": path.resolve("./src/routes"),
    }
  },
  base: '/factually-semantic-map/', // Ensure this matches your repo name EXACTLY
  build: {
    outDir: 'dist' // Use 'dist' since you're using the `gh-pages` branch
  }
})
