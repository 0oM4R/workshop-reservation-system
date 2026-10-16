import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import type { Workshop } from '../api/types'
import { useWorkshops } from './useWorkshops'

vi.mock('../api/client', () => ({ api: { get: vi.fn() } }))

// Fresh objects per test: the composable keeps what the mocked API returned.
let pottery: Workshop
let baking: Workshop

beforeEach(() => {
  pottery = {
    id: 1,
    title: 'Pottery',
    starts_at: '2026-11-01T10:00:00Z',
    capacity: 8,
    remaining: 8,
  }
  baking = { ...pottery, id: 2, title: 'Baking', remaining: 3 }
  vi.resetAllMocks()
})

describe('load', () => {
  it('stores the workshops on success', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [pottery, baking] })
    const { workshops, loading, error, load } = useWorkshops()

    await load()

    expect(api.get).toHaveBeenCalledWith('/workshops')
    expect(workshops.value).toEqual([pottery, baking])
    expect(loading.value).toBe(false)
    expect(error.value).toBeNull()
  })

  it('reports the failure and keeps the old list', async () => {
    vi.mocked(api.get).mockResolvedValueOnce({ data: [pottery] })
    vi.mocked(api.get).mockRejectedValueOnce(new Error('Network Error'))
    const { workshops, loading, error, load } = useWorkshops()
    await load()

    await load()

    expect(error.value).toBe('Could not load workshops: Network Error')
    expect(workshops.value).toEqual([pottery])
    expect(loading.value).toBe(false)
  })
})
