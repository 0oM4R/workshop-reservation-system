<script setup lang="ts">
import SearchBar from './components/SearchBar.vue'
import WorkshopList from './components/WorkshopList.vue'
import { useSearch } from './composables/useSearch'
import { useWorkshops } from './composables/useWorkshops'

const { workshops, loading, error, submitting, streamDown, bookedEmails, reserve, cancel } =
  useWorkshops()
const {
  query,
  mode,
  results,
  active: searchActive,
  searching,
  error: searchError,
} = useSearch(workshops)
</script>

<template>
  <UApp>
    <UContainer class="max-w-6xl py-10 sm:py-16">
      <header class="mb-8 max-w-xl sm:mb-12">
        <h1 class="font-display text-4xl font-semibold text-highlighted sm:text-5xl">
          Upcoming workshops
        </h1>
        <p class="mt-3 text-lg text-toned">
          Pick a class and reserve a seat. Seat counts change live as people book.
        </p>
      </header>
      <SearchBar
        v-model:query="query"
        v-model:mode="mode"
        :searching="searching"
        :error="searchError"
        :result-count="searchActive ? results.length : null"
      />
      <WorkshopList
        :workshops="results"
        :loading="loading"
        :error="error"
        :stale="streamDown"
        :booked-emails="bookedEmails"
        :busy="submitting"
        :reserve="reserve"
        :cancel="cancel"
        :empty-message="searchActive ? 'No workshops match your search.' : undefined"
      />
    </UContainer>
  </UApp>
</template>
