import { describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import axios from 'axios'
import ui from '@nuxt/ui/vue-plugin'
import App from './App.vue'

vi.mock('axios')

describe('App', () => {
  it('shows the health response', async () => {
    vi.mocked(axios.get).mockResolvedValue({ data: { status: 'ok' } })
    const wrapper = mount(App, { global: { plugins: [ui] } })
    await flushPromises()
    expect(wrapper.text()).toContain('{"status":"ok"}')
  })
})
