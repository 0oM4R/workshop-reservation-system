import axios, { AxiosError, HttpStatusCode } from 'axios'
import { onMounted, onScopeDispose, ref } from 'vue'
import { api } from '../api/client'
import type { CancelResult, Reservation, SeatsChanged, Workshop } from '../api/types'
import type { ReserveValues } from '../schemas'

const EVENTS_URL = '/api/events'
const STREAM_RETRY_DELAY_MS = 5000

/** What a reserve attempt came to, with a message fit to show the user. */
export interface ReserveOutcome {
  kind: 'reserved' | 'already' | 'full' | 'error'
  message: string
}

/** What a cancel attempt came to; the server's message is shown as is. */
export interface CancelOutcome {
  kind: 'cancelled' | 'error'
  message: string
}

/** FastAPI's error body: a message, or one entry per invalid field for a 422. */
interface ErrorBody {
  detail?: string | { msg: string }[]
}

function describeFailure(error: unknown): string {
  if (axios.isAxiosError<ErrorBody>(error)) {
    if (error.code === AxiosError.ECONNABORTED) return 'the server took too long to answer'
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail)) return detail.map((issue) => issue.msg).join('; ')
  }
  return error instanceof Error ? error.message : String(error)
}

function isTimeout(error: unknown): boolean {
  return axios.isAxiosError(error) && ['ECONNABORTED', 'ETIMEDOUT'].includes(error.code ?? '')
}

/** Workshops with their remaining seats, kept current by the live event stream. */
export function useWorkshops() {
  const workshops = ref<Workshop[]>([])
  // Starts true so the empty state never shows before the first load.
  const loading = ref(true)
  const error = ref<string | null>(null)
  const submitting = ref(false)
  const bookedEmails = ref<Record<number, string>>({})
  const streamDown = ref(false)
  let startedLoads = 0
  let appliedLoad = 0
  // Numbered so a list load can tell which events arrived while it was in flight.
  let eventCount = 0
  const lastEvents = new Map<number, { at: number; remaining: number }>()
  let events: EventSource | null = null
  let retryTimer: ReturnType<typeof setTimeout> | undefined

  // Loads overlap (on mount, on every stream open, after our own change while the stream is
  // down). A list is applied unless a newer one already was, so a failed newer load can't
  // discard it. Events that arrived while it was in flight are applied again on top: one
  // received before the request went out is already in the list, but a later one may be newer.
  async function load(): Promise<void> {
    const thisLoad = ++startedLoads
    const eventsBefore = eventCount
    loading.value = true
    error.value = null
    try {
      const response = await api.get<Workshop[]>('/workshops')
      if (thisLoad < appliedLoad) return
      appliedLoad = thisLoad
      workshops.value = response.data
      error.value = null
      for (const [workshopId, event] of lastEvents) {
        if (event.at > eventsBefore) setRemaining(workshopId, event.remaining)
      }
    } catch (failure) {
      if (thisLoad > appliedLoad) {
        error.value = `Could not load workshops: ${describeFailure(failure)}`
      }
    } finally {
      if (thisLoad === startedLoads) loading.value = false
    }
  }

  // While the stream is down nothing patches the counts, so fetch them after our own change.
  // No events flow then, so a newer count can't arrive first and be overwritten.
  function resyncIfStreamDown(): void {
    if (streamDown.value) void load()
  }

  function setRemaining(workshopId: number, remaining: number): void {
    const workshop = workshops.value.find((candidate) => candidate.id === workshopId)
    if (workshop) workshop.remaining = remaining
  }

  async function reserve(workshopId: number, values: ReserveValues): Promise<ReserveOutcome> {
    submitting.value = true
    try {
      const response = await api.post<Reservation>(`/workshops/${workshopId}/reservations`, values)
      bookedEmails.value[workshopId] = values.email
      // Ignore response.data.remaining: it can arrive after a newer stream event.
      // A 200 can be the retry of a 201 whose answer was lost, so both outcomes resync.
      resyncIfStreamDown()
      if (response.status === HttpStatusCode.Created) {
        return { kind: 'reserved', message: 'Your seat is reserved.' }
      }
      return { kind: 'already', message: 'You already hold a seat in this workshop.' }
    } catch (failure) {
      if (isTimeout(failure)) {
        return {
          kind: 'error',
          message:
            'The request timed out. Your seat may already be reserved; retry with the same email.',
        }
      }
      if (axios.isAxiosError(failure) && failure.response?.status === HttpStatusCode.Conflict) {
        return { kind: 'full', message: 'Sorry, this workshop is full.' }
      }
      return { kind: 'error', message: `Could not reserve: ${describeFailure(failure)}` }
    } finally {
      submitting.value = false
    }
  }

  async function cancel(workshopId: number, email: string): Promise<CancelOutcome> {
    submitting.value = true
    try {
      const response = await api.post<CancelResult>(
        `/workshops/${workshopId}/reservations/cancel`,
        { email },
      )
      if (bookedEmails.value[workshopId]?.toLowerCase() === email.toLowerCase()) {
        delete bookedEmails.value[workshopId]
      }
      resyncIfStreamDown()
      return { kind: 'cancelled', message: response.data.message }
    } catch (failure) {
      if (isTimeout(failure)) {
        return {
          kind: 'error',
          message:
            'The request timed out. Your seat may already be cancelled; retry with the same email.',
        }
      }
      return { kind: 'error', message: `Could not cancel: ${describeFailure(failure)}` }
    } finally {
      submitting.value = false
    }
  }

  function handleMessage(message: MessageEvent<string>): void {
    const change: SeatsChanged = JSON.parse(message.data)
    lastEvents.set(change.workshop_id, { at: ++eventCount, remaining: change.remaining })
    setRemaining(change.workshop_id, change.remaining)
  }

  function connect(): void {
    void load()
    openStream()
  }

  function openStream(): void {
    const stream = new EventSource(EVENTS_URL)
    events = stream
    stream.onopen = () => {
      streamDown.value = false
      void load()
    }
    stream.onmessage = handleMessage
    stream.onerror = () => {
      streamDown.value = true
      if (stream.readyState === EventSource.CLOSED) {
        clearTimeout(retryTimer)
        retryTimer = setTimeout(openStream, STREAM_RETRY_DELAY_MS)
      }
    }
  }

  function disconnect(): void {
    clearTimeout(retryTimer)
    events?.close()
    events = null
  }

  onMounted(connect)
  onScopeDispose(disconnect)

  return {
    workshops,
    loading,
    error,
    submitting,
    streamDown,
    bookedEmails,
    load,
    reserve,
    cancel,
  }
}
