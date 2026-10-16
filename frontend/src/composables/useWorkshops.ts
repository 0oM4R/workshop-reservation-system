import axios, { HttpStatusCode } from 'axios'
import { ref } from 'vue'
import { api } from '../api/client'
import type { Reservation, Workshop } from '../api/types'
import type { ReserveValues } from '../schemas'

/** What a reserve attempt came to, with a message fit to show the user. */
export interface ReserveOutcome {
  kind: 'reserved' | 'already' | 'full' | 'error'
  message: string
}

function describeFailure(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

/** Workshops with their remaining seats, and reserving a seat. */
export function useWorkshops() {
  const workshops = ref<Workshop[]>([])
  // Starts true so the empty state never shows before the first load.
  const loading = ref(true)
  const error = ref<string | null>(null)
  const submitting = ref(false)
  const bookedEmails = ref<Record<number, string>>({})
  let latestLoad = 0

  async function load(): Promise<void> {
    // Loads overlap (connect, then the stream opening); an older snapshot must not undo a newer one.
    const thisLoad = ++latestLoad
    loading.value = true
    error.value = null
    try {
      const response = await api.get<Workshop[]>('/workshops')
      if (thisLoad === latestLoad) workshops.value = response.data
    } catch (failure) {
      if (thisLoad === latestLoad)
        error.value = `Could not load workshops: ${describeFailure(failure)}`
    } finally {
      if (thisLoad === latestLoad) loading.value = false
    }
  }

  async function reserve(workshopId: number, values: ReserveValues): Promise<ReserveOutcome> {
    submitting.value = true
    try {
      const response = await api.post<Reservation>(`/workshops/${workshopId}/reservations`, values)
      bookedEmails.value[workshopId] = values.email
      if (response.status === HttpStatusCode.Created) {
        return { kind: 'reserved', message: 'Your seat is reserved.' }
      }
      return { kind: 'already', message: 'You already hold a seat in this workshop.' }
    } catch (failure) {
      if (axios.isAxiosError(failure) && failure.response?.status === HttpStatusCode.Conflict) {
        return { kind: 'full', message: 'Sorry, this workshop is full.' }
      }
      return { kind: 'error', message: `Could not reserve: ${describeFailure(failure)}` }
    } finally {
      submitting.value = false
    }
  }

  return { workshops, loading, error, submitting, bookedEmails, load, reserve }
}
