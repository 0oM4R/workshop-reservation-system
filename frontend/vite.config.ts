import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import ui from '@nuxt/ui/vite'

const API_URL = 'http://localhost:8000'

export default defineConfig({
  plugins: [vue(), ui({ router: false })],
  server: { proxy: { '/api': API_URL } },
  test: { environment: 'jsdom' },
})
