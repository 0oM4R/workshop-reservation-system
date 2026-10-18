<script setup lang="ts">
import { useToast } from '@nuxt/ui/composables'
import { computed, ref, useId } from 'vue'
import type { Workshop } from '../api/types'
import type { CancelOutcome, ReserveOutcome } from '../composables/useWorkshops'
import type { ReserveValues } from '../schemas'
import CancelForm from './CancelForm.vue'
import ReserveForm from './ReserveForm.vue'

const MAX_SEAT_DOTS = 15

const monthFormat = new Intl.DateTimeFormat(undefined, { month: 'short' })
const dayAndTimeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'long',
  hour: 'numeric',
  minute: '2-digit',
})
const fullDateFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'long',
  month: 'long',
  day: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

const props = defineProps<{
  workshop: Workshop
  busy: boolean
  bookedEmail?: string
  reserve: (workshopId: number, values: ReserveValues) => Promise<ReserveOutcome>
  cancel: (workshopId: number, email: string) => Promise<CancelOutcome>
}>()

const dialogUi = { title: 'font-display text-lg font-medium' }

const titleId = useId()
const toast = useToast()
const reserveOpen = ref(false)
const cancelOpen = ref(false)

const startsAt = computed(() => new Date(props.workshop.starts_at))
const isFull = computed(() => props.workshop.remaining === 0)
const seatsLabel = computed(() =>
  isFull.value ? 'Full' : `${props.workshop.remaining} of ${props.workshop.capacity} seats left`,
)
const dialogDescription = computed(
  () => `${props.workshop.title}, ${fullDateFormat.format(startsAt.value)}`,
)

function onReserved(outcome: ReserveOutcome) {
  reserveOpen.value = false
  toast.add({
    title: outcome.message,
    description: dialogDescription.value,
    color: outcome.kind === 'reserved' ? 'success' : 'info',
  })
}

function onCancelled(outcome: CancelOutcome) {
  cancelOpen.value = false
  toast.add({ title: outcome.message, description: dialogDescription.value, color: 'neutral' })
}
</script>

<template>
  <article
    class="rounded-[1.25rem] bg-default p-5 shadow-[0_3px_0_var(--ui-border-accented)] ring-1 ring-default sm:p-6"
  >
    <div class="flex items-start gap-4">
      <time
        :datetime="workshop.starts_at"
        class="flex size-16 shrink-0 flex-col items-center justify-center rounded-[0.875rem]"
        :class="isFull ? 'bg-elevated text-muted' : 'bg-primary/10 text-primary'"
      >
        <span class="text-xs font-semibold">{{ monthFormat.format(startsAt) }}</span>
        <span class="font-display text-2xl leading-none font-semibold">
          {{ startsAt.getDate() }}
        </span>
      </time>
      <div class="min-w-0">
        <h2 :id="titleId" class="font-display text-xl font-medium text-highlighted">
          {{ workshop.title }}
        </h2>
        <p class="mt-0.5 text-sm text-toned">{{ dayAndTimeFormat.format(startsAt) }}</p>
      </div>
    </div>

    <div class="mt-5">
      <div
        v-if="workshop.capacity <= MAX_SEAT_DOTS"
        class="flex flex-wrap gap-1.5"
        aria-hidden="true"
      >
        <span
          v-for="seat in workshop.capacity"
          :key="seat"
          class="size-3.5 rounded-full motion-safe:transition-colors motion-safe:duration-700"
          :class="
            seat <= workshop.remaining
              ? 'bg-amber-400 dark:bg-amber-300'
              : 'ring-2 ring-(--ui-border-accented) ring-inset'
          "
        />
      </div>
      <UProgress
        v-else
        :model-value="workshop.remaining"
        :max="workshop.capacity"
        color="warning"
        aria-hidden="true"
      />
      <p class="mt-2 text-sm font-medium" :class="isFull ? 'text-muted' : 'text-default'">
        {{ seatsLabel }}
      </p>
    </div>

    <div class="mt-5 flex flex-wrap items-center gap-2">
      <UBadge v-if="bookedEmail" color="primary" variant="soft" size="xl" class="rounded-full px-4">
        You're booked
      </UBadge>
      <UButton :aria-describedby="titleId" :disabled="busy || isFull" @click="reserveOpen = true">
        Reserve a seat
      </UButton>
      <UButton
        color="neutral"
        variant="ghost"
        :aria-describedby="titleId"
        :disabled="busy"
        @click="cancelOpen = true"
      >
        Cancel reservation
      </UButton>
    </div>

    <UModal
      v-model:open="reserveOpen"
      title="Reserve a seat"
      :dismissible="!busy"
      :close="!busy"
      :ui="dialogUi"
      :description="dialogDescription"
    >
      <template #body>
        <ReserveForm
          :busy="busy"
          :submit="(values) => reserve(workshop.id, values)"
          @done="onReserved"
        />
      </template>
    </UModal>
    <UModal
      v-model:open="cancelOpen"
      title="Cancel your reservation"
      :dismissible="!busy"
      :close="!busy"
      :ui="dialogUi"
      :description="dialogDescription"
    >
      <template #body>
        <CancelForm
          :busy="busy"
          :email="bookedEmail"
          :submit="(email) => cancel(workshop.id, email)"
          @done="onCancelled"
        />
      </template>
    </UModal>
  </article>
</template>
