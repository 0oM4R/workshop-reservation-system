import { computed, onScopeDispose, ref, watch, type Ref } from 'vue'
import { api } from '../api/client'
import type { SearchMode, Workshop } from '../api/types'

// Waits for a pause in typing, so each keystroke doesn't send a request.
export const SEARCH_DELAY_MS = 250

/**
 * Free-text search over the workshop list. The server ranks the workshops; the rows shown are
 * taken from the live list, so seat counts keep updating while results are on screen.
 */
export function useSearch(workshops: Ref<Workshop[]>) {
  const query = ref('')
  const mode = ref<SearchMode>('hybrid')
  const rankedIds = ref<number[] | null>(null)
  const searching = ref(false)
  const error = ref<string | null>(null)
  let latestSearch = 0
  let timer: ReturnType<typeof setTimeout> | undefined

  const active = computed(() => rankedIds.value !== null)

  const results = computed(() => {
    if (rankedIds.value === null) {
      return workshops.value
    }

    const workshopsById = new Map<number, Workshop>()
    for (const workshop of workshops.value) {
      workshopsById.set(workshop.id, workshop)
    }

    const ranked: Workshop[] = []
    for (const id of rankedIds.value) {
      const workshop = workshopsById.get(id)
      // An id the list doesn't have yet is skipped until the next list load.
      if (workshop !== undefined) {
        ranked.push(workshop)
      }
    }
    return ranked
  })

  async function search(text: string, searchMode: SearchMode, thisSearch: number): Promise<void> {
    try {
      const response = await api.get<number[]>('/workshops/search', {
        params: { q: text, mode: searchMode },
      })
      if (thisSearch !== latestSearch) {
        return
      }
      rankedIds.value = response.data
      error.value = null
    } catch {
      if (thisSearch !== latestSearch) {
        return
      }
      rankedIds.value = null
      error.value = 'Search is unavailable right now, so all workshops are shown.'
    } finally {
      if (thisSearch === latestSearch) {
        searching.value = false
      }
    }
  }

  function clear(): void {
    rankedIds.value = null
    searching.value = false
    error.value = null
  }

  watch([query, mode], ([text, searchMode]) => {
    const thisSearch = ++latestSearch
    clearTimeout(timer)
    const trimmed = text.trim()
    if (trimmed === '') {
      clear()
      return
    }
    searching.value = true
    timer = setTimeout(() => {
      void search(trimmed, searchMode, thisSearch)
    }, SEARCH_DELAY_MS)
  })

  onScopeDispose(() => clearTimeout(timer))

  return { query, mode, results, active, searching, error }
}
