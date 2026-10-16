import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import ui from '@nuxt/ui/vite'

const API_URL = 'http://localhost:8000'

export default defineConfig({
  plugins: [
    vue(),
    ui({
      router: false,
      ui: {
        colors: { primary: 'emerald', neutral: 'olive' },
        button: { slots: { base: 'rounded-full' }, defaultVariants: { size: 'lg' } },
        input: { defaultVariants: { size: 'lg' } },
      },
    }),
  ],
  server: { proxy: { '/api': API_URL } },
  test: { environment: 'jsdom' },
})
