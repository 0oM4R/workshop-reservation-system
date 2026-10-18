<script setup lang="ts">
import type { SearchMode } from '../api/types'

const SEARCH_QUERY_MAX_LENGTH = 200

const query = defineModel<string>('query', { required: true })
const mode = defineModel<SearchMode>('mode', { required: true })

defineProps<{
  searching: boolean
  error: string | null
  resultCount: number | null
}>()

const MODES: { label: string; value: SearchMode }[] = [
  { label: 'Hybrid', value: 'hybrid' },
  { label: 'Hybrid + rerank', value: 'rerank' },
  { label: 'Keyword', value: 'keyword' },
  { label: 'Semantic', value: 'semantic' },
]
</script>

<template>
  <section role="search" class="mb-8 space-y-3">
    <div class="flex flex-col gap-4 lg:flex-row lg:items-end">
      <UFormField label="Search workshops" class="w-full lg:max-w-xl">
        <UInput
          v-model="query"
          type="search"
          :maxlength="SEARCH_QUERY_MAX_LENGTH"
          placeholder="Describe what you want to learn"
          class="w-full"
        />
      </UFormField>
      <UFormField label="Rank by" class="w-full lg:w-44">
        <USelect v-model="mode" :items="MODES" class="w-full" />
      </UFormField>
    </div>
    <UAlert v-if="error" color="warning" variant="subtle" :description="error" />
    <p v-else class="text-sm text-toned" aria-live="polite">
      <template v-if="searching">Searching…</template>
      <template v-else-if="resultCount">
        {{ resultCount === 1 ? '1 workshop' : `${resultCount} workshops` }}, best match first
      </template>
    </p>
  </section>
</template>
