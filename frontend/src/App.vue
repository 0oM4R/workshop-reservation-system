<script setup lang="ts">
import WorkshopList from './components/WorkshopList.vue'
import { useWorkshops } from './composables/useWorkshops'

const { workshops, loading, error, submitting, streamDown, bookedEmails, reserve, cancel } =
  useWorkshops()
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
      <WorkshopList
        :workshops="workshops"
        :loading="loading"
        :error="error"
        :stale="streamDown"
        :booked-emails="bookedEmails"
        :busy="submitting"
        :reserve="reserve"
        :cancel="cancel"
      />
    </UContainer>
  </UApp>
</template>
