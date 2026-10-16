import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type AxiosResponse } from 'axios'
import { DOMWrapper, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import ui from '@nuxt/ui/vue-plugin'
import { api } from './api/client'
import App from './App.vue'

vi.mock('./api/client', () => ({ api: { get: vi.fn(), post: vi.fn() } }))

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

function buttonNamed(wrapper: VueWrapper, name: string) {
  return wrapper.findAll('button').find((button) => button.text() === name)
}

function openDialog() {
  return new DOMWrapper(document.querySelector('[role="dialog"]'))
}

async function reserveThroughDialog(wrapper: VueWrapper) {
  await buttonNamed(wrapper, 'Reserve a seat')?.trigger('click')
  await flushPromises()
  const dialog = openDialog()
  await dialog.find('input[autocomplete="name"]').setValue('Ada')
  await dialog.find('input[type="email"]').setValue('ada@example.com')
  await dialog.find('form').trigger('submit')
  await flushPromises()
}

async function waitForDialogToClose() {
  await vi.waitFor(() => expect(document.querySelector('[role="dialog"]')).toBeNull())
}

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

  it('disables Reserve on a full workshop', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [workshop(2, 'Knife Skills', 0)] })
    const wrapper = mount(App, { global: { plugins: [ui] } })
    await flushPromises()

    expect(buttonNamed(wrapper, 'Reserve a seat')?.attributes('disabled')).toBeDefined()
  })

  it('closes the dialog and swaps Reserve for a booked badge after reserving', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [workshop(1, 'Pottery', 3)] })
    vi.mocked(api.post).mockResolvedValue({
      status: 201,
      data: { id: 9, workshop_id: 1, name: 'Ada', remaining: 2 },
    })
    const wrapper = mount(App, { global: { plugins: [ui] }, attachTo: document.body })
    await flushPromises()

    await reserveThroughDialog(wrapper)
    await waitForDialogToClose()

    expect(api.post).toHaveBeenCalledWith('/workshops/1/reservations', {
      name: 'Ada',
      email: 'ada@example.com',
    })
    expect(wrapper.text()).toContain("You're booked")
    expect(buttonNamed(wrapper, 'Reserve a seat')).toBeUndefined()
    expect(wrapper.text()).toContain('3 of 5 seats left')
    wrapper.unmount()
  })

  it('keeps the dialog open with the reason when the workshop filled up', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [workshop(1, 'Pottery', 1)] })
    vi.mocked(api.post).mockRejectedValue(
      new AxiosError('full', '409', undefined, undefined, { status: 409 } as AxiosResponse),
    )
    const wrapper = mount(App, { global: { plugins: [ui] }, attachTo: document.body })
    await flushPromises()

    await reserveThroughDialog(wrapper)

    expect(openDialog().text()).toContain('Sorry, this workshop is full.')
    expect(wrapper.text()).not.toContain("You're booked")
    wrapper.unmount()
  })
})
