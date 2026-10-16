import { ref } from 'vue'
import { api } from '../api/client'
import type { Workshop } from '../api/types'

function describeFailure(error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

/** Workshops with their remaining seats. */
export function useWorkshops() {
  const workshops = ref<Workshop[]>([])
  // Starts true so the empty state never shows before the first load.
  const loading = ref(true)
  const error = ref<string | null>(null)
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

  return { workshops, loading, error, load }
}
