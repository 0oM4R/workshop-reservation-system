import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref, type EffectScope } from 'vue'
import { api } from '../api/client'
import type { Workshop } from '../api/types'
import { SEARCH_DELAY_MS, useSearch } from './useSearch'

vi.mock('../api/client', () => ({ api: { get: vi.fn() } }))

const workshop = (id: number, title: string): Workshop => ({
  id,
  title,
  description: `About ${title}.`,
  starts_at: '2026-11-01T10:00:00Z',
  capacity: 5,
  remaining: 5,
})

let scope: EffectScope

/** Run the composable in an effect scope, so its watcher and cleanup work as in a component. */
function setUp() {
  const workshops = ref([workshop(1, 'Pottery'), workshop(2, 'Baking'), workshop(3, 'Bikes')])
  scope = effectScope()
  const search = scope.run(() => useSearch(workshops))!
  return { workshops, ...search }
}

async function type(query: { value: string }, text: string) {
  query.value = text
  await nextTick()
  await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS)
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason: Error) => void
  const promise = new Promise<T>((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}

beforeEach(() => {
  vi.resetAllMocks()
  vi.useFakeTimers()
})

afterEach(() => {
  scope.stop()
  vi.useRealTimers()
})

describe('useSearch', () => {
  it('shows every workshop while the query is empty', async () => {
    const { workshops, results, active } = setUp()

    await nextTick()

    expect(results.value).toEqual(workshops.value)
    expect(active.value).toBe(false)
    expect(api.get).not.toHaveBeenCalled()
  })

  it('shows the matches in the order the server ranked them', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [3, 1] })
    const { query, results, active } = setUp()

    await type(query, '  bikes and pots ')

    expect(api.get).toHaveBeenCalledWith('/workshops/search', {
      params: { q: 'bikes and pots', mode: 'hybrid' },
    })
    expect(results.value.map((match) => match.id)).toEqual([3, 1])
    expect(active.value).toBe(true)
  })

  it('skips a ranked id the list does not have yet', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [9, 2] })
    const { query, results } = setUp()

    await type(query, 'baking')

    expect(results.value.map((match) => match.id)).toEqual([2])
  })

  it('sends one request after a pause in typing', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [] })
    const { query } = setUp()

    query.value = 'p'
    await nextTick()
    await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS / 2)
    await type(query, 'pottery')

    expect(api.get).toHaveBeenCalledTimes(1)
    expect(vi.mocked(api.get).mock.calls[0]?.[1]).toEqual({
      params: { q: 'pottery', mode: 'hybrid' },
    })
  })

  it('searches again in the chosen mode', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [2] })
    const { query, mode } = setUp()
    await type(query, 'bread')

    mode.value = 'keyword'
    await nextTick()
    await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS)

    expect(api.get).toHaveBeenLastCalledWith('/workshops/search', {
      params: { q: 'bread', mode: 'keyword' },
    })
  })

  it('ignores a slow response once a newer search has finished', async () => {
    const slow = deferred<{ data: number[] }>()
    vi.mocked(api.get)
      .mockReturnValueOnce(slow.promise)
      .mockResolvedValueOnce({ data: [2] })
    const { query, results } = setUp()

    await type(query, 'old')
    await type(query, 'new')
    slow.resolve({ data: [1] })
    await vi.runAllTimersAsync()

    expect(results.value.map((match) => match.id)).toEqual([2])
  })

  it.each([
    ['query', 'success'],
    ['query', 'failure'],
    ['mode', 'success'],
    ['mode', 'failure'],
  ] as const)('ignores an old %s request’s %s during the next debounce', async (field, outcome) => {
    const old = deferred<{ data: number[] }>()
    const current = deferred<{ data: number[] }>()
    vi.mocked(api.get).mockReturnValueOnce(old.promise).mockReturnValueOnce(current.promise)
    const { query, mode, workshops, results, searching, error } = setUp()
    await type(query, 'pottery')

    if (field === 'query') query.value = 'baking'
    else mode.value = 'keyword'
    await nextTick()
    if (outcome === 'success') old.resolve({ data: [1] })
    else old.reject(new Error('Network Error'))
    await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS / 2)

    expect(api.get).toHaveBeenCalledTimes(1)
    expect(results.value).toEqual(workshops.value)
    expect(error.value).toBeNull()
    expect(searching.value).toBe(true)

    await vi.advanceTimersByTimeAsync(SEARCH_DELAY_MS / 2)
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(searching.value).toBe(true)

    current.resolve({ data: [2] })
    await vi.runAllTimersAsync()
    expect(results.value.map((match) => match.id)).toEqual([2])
    expect(searching.value).toBe(false)
  })

  it('keeps seat counts live while results are shown', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [1] })
    const { query, workshops, results } = setUp()
    await type(query, 'pottery')

    workshops.value[0]!.remaining = 2

    expect(results.value[0]?.remaining).toBe(2)
  })

  it('goes back to every workshop when the query is cleared', async () => {
    const pending = deferred<{ data: number[] }>()
    vi.mocked(api.get).mockReturnValue(pending.promise)
    const { query, workshops, results, searching } = setUp()
    await type(query, 'pottery')

    query.value = ''
    await nextTick()
    pending.resolve({ data: [1] })
    await vi.runAllTimersAsync()

    expect(results.value).toEqual(workshops.value)
    expect(searching.value).toBe(false)
  })

  it('falls back to every workshop with a message when search fails', async () => {
    vi.mocked(api.get).mockRejectedValue(new Error('Network Error'))
    const { query, workshops, results, error } = setUp()

    await type(query, 'pottery')

    expect(results.value).toEqual(workshops.value)
    expect(error.value).toBe('Search is unavailable right now, so all workshops are shown.')
  })
})
