<script setup lang="ts">
import type { Workshop } from '../api/types'
import type { CancelOutcome, ReserveOutcome } from '../composables/useWorkshops'
import type { ReserveValues } from '../schemas'
import WorkshopCard from './WorkshopCard.vue'

const PLACEHOLDER_CARDS = 3

defineProps<{
  workshops: Workshop[]
  loading: boolean
  error: string | null
  busy: boolean
  bookedEmails: Record<number, string>
  reserve: (workshopId: number, values: ReserveValues) => Promise<ReserveOutcome>
  cancel: (workshopId: number, email: string) => Promise<CancelOutcome>
}>()
</script>

<template>
  <section class="space-y-6">
    <UAlert v-if="error" color="error" variant="subtle" :description="error" />
    <p v-if="!loading && !error && workshops.length === 0" class="text-lg text-toned">
      No workshops are scheduled yet. Check back soon.
    </p>
    <div class="grid items-start gap-5 sm:grid-cols-2 lg:grid-cols-3">
      <template v-if="loading && workshops.length === 0">
        <USkeleton
          v-for="placeholder in PLACEHOLDER_CARDS"
          :key="placeholder"
          class="h-56 rounded-[1.25rem] bg-default"
        />
      </template>
      <WorkshopCard
        v-for="workshop in workshops"
        :key="workshop.id"
        :workshop="workshop"
        :busy="busy"
        :booked-email="bookedEmails[workshop.id]"
        :reserve="reserve"
        :cancel="cancel"
      />
    </div>
  </section>
</template>
