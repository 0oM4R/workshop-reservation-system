import { beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import ui from '@nuxt/ui/vue-plugin'
import { api } from './api/client'
import App from './App.vue'

vi.mock('./api/client', () => ({ api: { get: vi.fn() } }))

const workshop = (id: number, title: string, remaining: number) => ({
  id,
  title,
  starts_at: '2026-11-01T10:00:00Z',
  capacity: 5,
  remaining,
})

beforeEach(() => {
  vi.resetAllMocks()
})

describe('App', () => {
  it('lists workshops and marks a full one', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: [workshop(1, 'Pottery', 3), workshop(2, 'Knife Skills', 0)],
    })
    const wrapper = mount(App, { global: { plugins: [ui] } })

    await flushPromises()

    expect(wrapper.text()).toContain('Pottery')
    expect(wrapper.text()).toContain('3 of 5 seats left')
    expect(wrapper.text()).toContain('Full')
  })

  it('shows the error when the list cannot be loaded', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Network Error'))
    const wrapper = mount(App, { global: { plugins: [ui] } })

    await flushPromises()

    expect(wrapper.text()).toContain('Could not load workshops: Network Error')
  })

  it('shows a bar instead of one dot per seat for a large workshop', async () => {
    vi.mocked(api.get).mockResolvedValue({
      data: [{ ...workshop(3, 'Choir', 637), capacity: 1000 }],
    })
    const wrapper = mount(App, { global: { plugins: [ui] } })

    await flushPromises()

    expect(wrapper.find('[role="progressbar"]').exists()).toBe(true)
    expect(wrapper.findAll('span.rounded-full')).toHaveLength(0)
    expect(wrapper.text()).toContain('637 of 1000 seats left')
  })
})
