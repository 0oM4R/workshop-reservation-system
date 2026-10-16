import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AxiosError, type AxiosResponse } from 'axios'
import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent } from 'vue'
import { api } from '../api/client'
import type { Workshop } from '../api/types'
import { FakeEventSource, installFakeEventSource } from '../test/FakeEventSource'
import { useWorkshops } from './useWorkshops'

vi.mock('../api/client', () => ({ api: { get: vi.fn(), post: vi.fn() } }))

// Fresh objects per test: the composable mutates what the mocked API returned.
let pottery: Workshop
let baking: Workshop
const values = { name: 'Ada', email: 'ada@example.com' }

/** Run the composable inside a mounted component, so its mount and unmount hooks fire. */
function mountWorkshops() {
  let workshops!: ReturnType<typeof useWorkshops>
  const wrapper = mount(
    defineComponent({
      setup() {
        workshops = useWorkshops()
        return () => null
      },
    }),
  )
  return { ...workshops, unmount: () => wrapper.unmount() }
}

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
  installFakeEventSource()
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

  it('shows the server validation message for a 422', async () => {
    vi.mocked(api.post).mockRejectedValue(
      new AxiosError('failed', '422', undefined, undefined, {
        status: 422,
        data: { detail: [{ msg: 'value is not a valid email address' }] },
      } as AxiosResponse),
    )
    const { reserve } = useWorkshops()

    expect((await reserve(1, values)).message).toBe(
      'Could not reserve: value is not a valid email address',
    )
  })

  it('explains a request that timed out', async () => {
    vi.mocked(api.post).mockRejectedValue(
      new AxiosError('timeout of 10000ms exceeded', AxiosError.ECONNABORTED),
    )
    const { reserve } = useWorkshops()

    expect((await reserve(1, values)).message).toBe(
      'The request timed out. Your seat may already be reserved; retry with the same email.',
    )
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

  it('forgets the booking once that email cancels, in any letter case', async () => {
    vi.mocked(api.post)
      .mockResolvedValueOnce({ status: 201, data: { remaining: 7 } })
      .mockResolvedValue({ data: { message: 'Done.' } })
    const { bookedEmails, reserve, cancel } = useWorkshops()
    await reserve(1, values)

    await cancel(1, 'someone@example.com')
    expect(bookedEmails.value).toEqual({ 1: 'ada@example.com' })
    await cancel(1, 'ADA@example.com')

    expect(bookedEmails.value).toEqual({})
  })
})

describe('cancel', () => {
  it('returns the server message', async () => {
    vi.mocked(api.post).mockResolvedValue({ data: { message: 'Done.' } })
    const { cancel } = useWorkshops()

    const outcome = await cancel(1, 'ada@example.com')

    expect(api.post).toHaveBeenCalledWith('/workshops/1/reservations/cancel', {
      email: 'ada@example.com',
    })
    expect(outcome).toEqual({ kind: 'cancelled', message: 'Done.' })
  })

  it("reports a failure with the server's message", async () => {
    vi.mocked(api.post).mockRejectedValue(
      new AxiosError('failed', '404', undefined, undefined, {
        status: 404,
        data: { detail: 'Workshop not found' },
      } as AxiosResponse),
    )
    const { cancel } = useWorkshops()

    expect(await cancel(1, 'ada@example.com')).toEqual({
      kind: 'error',
      message: 'Could not cancel: Workshop not found',
    })
  })
})

describe('request timeouts', () => {
  it.each(['ECONNABORTED', 'ETIMEDOUT'])('releases submission state after %s', async (code) => {
    let rejectRequest: (error: Error) => void = () => {}
    vi.mocked(api.post).mockImplementation(
      () => new Promise((_, reject) => (rejectRequest = reject)),
    )
    const { submitting, reserve, cancel, bookedEmails } = useWorkshops()

    const reservation = reserve(1, values)
    expect(submitting.value).toBe(true)
    rejectRequest(new AxiosError('timeout', code))
    const reserveOutcome = await reservation
    expect(submitting.value).toBe(false)
    expect(reserveOutcome.kind).toBe('error')
    expect(reserveOutcome.message).toContain('may already be reserved')
    expect(reserveOutcome.message).toContain('same email')
    expect(bookedEmails.value).toEqual({})

    bookedEmails.value[1] = values.email
    const cancellation = cancel(1, values.email)
    expect(submitting.value).toBe(true)
    rejectRequest(new AxiosError('timeout', code))
    const cancelOutcome = await cancellation
    expect(submitting.value).toBe(false)
    expect(cancelOutcome.kind).toBe('error')
    expect(cancelOutcome.message).toContain('may already be cancelled')
    expect(cancelOutcome.message).toContain('same email')
    expect(bookedEmails.value[1]).toBe(values.email)
  })
})

describe('live updates', () => {
  it('loads the list on mount, before the stream opens', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [pottery] })

    const { workshops } = mountWorkshops()
    await flushPromises()

    expect(FakeEventSource.instances[0]?.url).toBe('/api/events')
    expect(workshops.value).toEqual([pottery])
  })

  it('reloads the list each time the stream opens, including reconnects', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [pottery] })

    mountWorkshops()
    const [stream] = FakeEventSource.instances
    stream?.onopen?.()
    stream?.onopen?.()
    await flushPromises()

    expect(api.get).toHaveBeenCalledTimes(3)
  })

  it('keeps the latest list when an older load answers last', async () => {
    let answerFirstLoad: (value: { data: Workshop[] }) => void = () => {}
    vi.mocked(api.get)
      .mockReturnValueOnce(new Promise((resolve) => (answerFirstLoad = resolve)))
      .mockRejectedValueOnce(new Error('timeout'))
      .mockResolvedValueOnce({ data: [{ ...pottery, remaining: 4 }] })

    const { workshops, error } = mountWorkshops()
    const stream = FakeEventSource.instances[0]
    stream?.onopen?.()
    stream?.onopen?.()
    await flushPromises()
    answerFirstLoad({ data: [pottery] })
    await flushPromises()

    expect(workshops.value.map((workshop) => workshop.remaining)).toEqual([4])
    expect(error.value).toBeNull()
  })

  it('shows an older list that succeeds after a newer load failed', async () => {
    let answerFirstLoad: (value: { data: Workshop[] }) => void = () => {}
    vi.mocked(api.get)
      .mockReturnValueOnce(new Promise((resolve) => (answerFirstLoad = resolve)))
      .mockRejectedValueOnce(new Error('Request failed with status code 502'))
    const { workshops, error } = mountWorkshops()
    FakeEventSource.instances[0]?.onopen?.()
    await flushPromises()

    answerFirstLoad({ data: [pottery] })
    await flushPromises()

    expect(workshops.value).toEqual([pottery])
    expect(error.value).toBeNull()
  })

  it('keeps an event that arrives while a list load is in flight', async () => {
    let answerReload: (value: { data: Workshop[] }) => void = () => {}
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: [pottery] })
      .mockReturnValueOnce(new Promise((resolve) => (answerReload = resolve)))
    const { workshops } = mountWorkshops()
    await flushPromises()
    const stream = FakeEventSource.instances[0]

    // The reload's list is read before the reservation behind the event commits.
    stream?.onopen?.()
    stream?.onmessage?.({ data: JSON.stringify({ workshop_id: 1, remaining: 7 }) })
    answerReload({ data: [{ ...pottery, remaining: 8 }] })
    await flushPromises()

    expect(workshops.value[0]?.remaining).toBe(7)
  })

  it('lets a list load replace events received before it started', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: [pottery] })
      .mockResolvedValueOnce({ data: [{ ...pottery, remaining: 5 }] })
    const { workshops } = mountWorkshops()
    await flushPromises()
    const stream = FakeEventSource.instances[0]
    stream?.onmessage?.({ data: JSON.stringify({ workshop_id: 1, remaining: 7 }) })

    stream?.onopen?.()
    await flushPromises()

    expect(workshops.value[0]?.remaining).toBe(5)
  })

  it('reopens the stream after the browser gives up on it, then resyncs', async () => {
    vi.useFakeTimers()
    vi.mocked(api.get).mockResolvedValue({ data: [pottery] })
    const { streamDown } = mountWorkshops()
    const stream = FakeEventSource.instances[0]

    if (stream) stream.readyState = FakeEventSource.CLOSED
    stream?.onerror?.()
    vi.advanceTimersByTime(5000)
    vi.useRealTimers()
    expect(streamDown.value).toBe(true)
    FakeEventSource.instances[1]?.onopen?.()
    await flushPromises()

    expect(FakeEventSource.instances).toHaveLength(2)
    expect(api.get).toHaveBeenCalledTimes(2)
    expect(streamDown.value).toBe(false)
  })

  it('leaves reconnecting to the browser while it is still retrying', () => {
    vi.useFakeTimers()
    vi.mocked(api.get).mockResolvedValue({ data: [pottery] })
    mountWorkshops()

    FakeEventSource.instances[0]?.onerror?.()
    vi.advanceTimersByTime(5000)
    vi.useRealTimers()

    expect(FakeEventSource.instances).toHaveLength(1)
  })

  it('patches only the workshop named in an event', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [pottery, baking] })
    const { workshops } = mountWorkshops()
    await flushPromises()

    FakeEventSource.instances[0]?.onmessage?.({
      data: JSON.stringify({ workshop_id: 2, remaining: 1 }),
    })

    expect(workshops.value.map((workshop) => workshop.remaining)).toEqual([8, 1])
  })

  it('flags the stream as down without hiding the list, then clears it on reopen', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [pottery] })
    const { workshops, error, streamDown } = mountWorkshops()
    await flushPromises()
    const stream = FakeEventSource.instances[0]

    stream?.onerror?.()
    expect(streamDown.value).toBe(true)
    expect(error.value).toBeNull()
    expect(workshops.value).toEqual([pottery])
    stream?.onopen?.()

    expect(streamDown.value).toBe(false)
  })

  it.each([201, 200])(
    'reloads counts after reserve %s or cancel while disconnected',
    async (status) => {
      vi.mocked(api.get)
        .mockResolvedValueOnce({ data: [pottery] })
        .mockResolvedValueOnce({ data: [{ ...pottery, remaining: 7 }] })
        .mockResolvedValueOnce({ data: [{ ...pottery, remaining: 8 }] })
      vi.mocked(api.post)
        .mockResolvedValueOnce({ status, data: { remaining: 7 } })
        .mockResolvedValueOnce({ data: { message: 'Done.' } })
      const { workshops, reserve, cancel } = mountWorkshops()
      await flushPromises()
      FakeEventSource.instances[0]?.onerror?.()

      await reserve(1, values)
      await flushPromises()
      expect(workshops.value[0]?.remaining).toBe(7)
      await cancel(1, 'ada@example.com')
      await flushPromises()

      expect(workshops.value[0]?.remaining).toBe(8)
    },
  )

  it('keeps events received during the initial list load, including zero seats', async () => {
    let finish: (value: { data: Workshop[] }) => void = () => {}
    vi.mocked(api.get).mockReturnValueOnce(new Promise((resolve) => (finish = resolve)))
    const { workshops, loading } = mountWorkshops()
    const stream = FakeEventSource.instances[0]

    stream?.onmessage?.({ data: JSON.stringify({ workshop_id: 1, remaining: 2 }) })
    stream?.onmessage?.({ data: JSON.stringify({ workshop_id: 1, remaining: 0 }) })
    finish({ data: [pottery, baking] })
    await flushPromises()

    expect(workshops.value.map((workshop) => workshop.remaining)).toEqual([0, 3])
    expect(loading.value).toBe(false)
  })

  it('preserves live counts over a delayed reload, but lets later loads resync', async () => {
    let finish: (value: { data: Workshop[] }) => void = () => {}
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: [{ ...pottery }] })
      .mockReturnValueOnce(new Promise((resolve) => (finish = resolve)))
      .mockResolvedValueOnce({ data: [{ ...pottery, remaining: 6 }, baking] })
    const { workshops, load } = mountWorkshops()
    await flushPromises()
    const pending = load()
    FakeEventSource.instances[0]?.onmessage?.({
      data: JSON.stringify({ workshop_id: 1, remaining: 4 }),
    })
    expect(workshops.value[0]?.remaining).toBe(4)

    finish({ data: [pottery, baking] })
    await pending
    expect(workshops.value.map((workshop) => workshop.remaining)).toEqual([4, 3])

    await load()
    expect(workshops.value.map((workshop) => workshop.remaining)).toEqual([6, 3])
  })

  it('preserves events across overlapping successful loads', async () => {
    let finishOlder: (value: { data: Workshop[] }) => void = () => {}
    let finishNewer: (value: { data: Workshop[] }) => void = () => {}
    vi.mocked(api.get)
      .mockReturnValueOnce(new Promise((resolve) => (finishOlder = resolve)))
      .mockReturnValueOnce(new Promise((resolve) => (finishNewer = resolve)))
    const { workshops, loading, load } = mountWorkshops()
    const newer = load()
    FakeEventSource.instances[0]?.onmessage?.({
      data: JSON.stringify({ workshop_id: 1, remaining: 3 }),
    })

    finishOlder({ data: [pottery] })
    await flushPromises()
    expect(loading.value).toBe(true)
    expect(workshops.value[0]?.remaining).toBe(3)

    finishNewer({ data: [{ ...pottery, remaining: 5 }] })
    await newer
    expect(workshops.value[0]?.remaining).toBe(3)
    expect(loading.value).toBe(false)
  })

  it('reloads after an already-held seat too, in case the first answer was lost', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [pottery] })
    vi.mocked(api.post).mockResolvedValue({ status: 200, data: { remaining: 7 } })
    const { reserve } = mountWorkshops()
    await flushPromises()
    FakeEventSource.instances[0]?.onerror?.()

    await reserve(1, values)
    await flushPromises()

    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('leaves the counts to the stream after a reserve while it is up', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: [pottery] })
    vi.mocked(api.post).mockResolvedValue({ status: 201, data: { remaining: 7 } })
    const { reserve } = mountWorkshops()
    FakeEventSource.instances[0]?.onopen?.()
    await flushPromises()

    await reserve(1, values)
    await flushPromises()

    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('closes the stream on unmount', () => {
    vi.mocked(api.get).mockResolvedValue({ data: [pottery] })
    const { unmount } = mountWorkshops()

    unmount()

    expect(FakeEventSource.instances[0]?.closed).toBe(true)
  })

  it('cancels a pending reopen on unmount', () => {
    vi.useFakeTimers()
    vi.mocked(api.get).mockResolvedValue({ data: [pottery] })
    const { unmount } = mountWorkshops()
    const stream = FakeEventSource.instances[0]
    if (stream) stream.readyState = FakeEventSource.CLOSED
    stream?.onerror?.()

    unmount()
    vi.advanceTimersByTime(5000)
    vi.useRealTimers()

    expect(FakeEventSource.instances).toHaveLength(1)
  })
})
