import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type AxiosResponse } from 'axios'
import { api } from '../api/client'
import type { Workshop } from '../api/types'
import { useWorkshops } from './useWorkshops'

vi.mock('../api/client', () => ({ api: { get: vi.fn(), post: vi.fn() } }))

// Fresh objects per test: the composable keeps what the mocked API returned.
let pottery: Workshop
let baking: Workshop
const values = { name: 'Ada', email: 'ada@example.com' }

function failureWithStatus(status: number): AxiosError {
  return new AxiosError('failed', String(status), undefined, undefined, {
    status,
  } as AxiosResponse)
}

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

describe('reserve', () => {
  it('reports a new seat on 201 and leaves the count to the live stream', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [pottery] })
    vi.mocked(api.post).mockResolvedValue({ status: 201, data: { remaining: 7 } })
    const { workshops, load, reserve } = useWorkshops()
    await load()

    const outcome = await reserve(1, values)

    expect(api.post).toHaveBeenCalledWith('/workshops/1/reservations', values)
    expect(outcome.kind).toBe('reserved')
    expect(workshops.value[0]?.remaining).toBe(8)
  })

  it('reports an existing seat on 200', async () => {
    vi.mocked(api.post).mockResolvedValue({ status: 200, data: { remaining: 7 } })
    const { reserve } = useWorkshops()

    expect((await reserve(1, values)).kind).toBe('already')
  })

  it('reports a full workshop on 409', async () => {
    vi.mocked(api.post).mockRejectedValue(failureWithStatus(409))
    const { reserve } = useWorkshops()

    expect((await reserve(1, values)).kind).toBe('full')
  })

  it('reports any other failure as an error', async () => {
    vi.mocked(api.post).mockRejectedValue(failureWithStatus(500))
    const { reserve } = useWorkshops()

    expect((await reserve(1, values)).kind).toBe('error')
  })

  it('is marked submitting only while the request runs', async () => {
    let finish: (value: unknown) => void = () => {}
    vi.mocked(api.post).mockReturnValue(new Promise((resolve) => (finish = resolve)))
    const { submitting, reserve } = useWorkshops()

    const pending = reserve(1, values)
    expect(submitting.value).toBe(true)
    finish({ status: 201, data: { remaining: 1 } })
    await pending

    expect(submitting.value).toBe(false)
  })
})

describe('booked workshops', () => {
  it('remembers the email a seat was reserved with, new or already held', async () => {
    vi.mocked(api.post)
      .mockResolvedValueOnce({ status: 201, data: { remaining: 7 } })
      .mockResolvedValueOnce({ status: 200, data: { remaining: 2 } })
    const { bookedEmails, reserve } = useWorkshops()

    await reserve(1, values)
    await reserve(2, values)

    expect(bookedEmails.value).toEqual({ 1: 'ada@example.com', 2: 'ada@example.com' })
  })

  it('remembers nothing when the workshop is full', async () => {
    vi.mocked(api.post).mockRejectedValue(failureWithStatus(409))
    const { bookedEmails, reserve } = useWorkshops()

    await reserve(1, values)

    expect(bookedEmails.value).toEqual({})
  })
})
