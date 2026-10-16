<script setup lang="ts">
import { computed, useId } from 'vue'
import type { Workshop } from '../api/types'

const MAX_SEAT_DOTS = 20

const monthFormat = new Intl.DateTimeFormat(undefined, { month: 'short' })
const dayAndTimeFormat = new Intl.DateTimeFormat(undefined, {
  weekday: 'long',
  hour: 'numeric',
  minute: '2-digit',
})

const props = defineProps<{ workshop: Workshop }>()

const titleId = useId()

const startsAt = computed(() => new Date(props.workshop.starts_at))
const isFull = computed(() => props.workshop.remaining === 0)
const takenSeats = computed(() => props.workshop.capacity - props.workshop.remaining)
const seatsLabel = computed(() =>
  isFull.value ? 'Full' : `${props.workshop.remaining} of ${props.workshop.capacity} seats left`,
)
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
            seat <= takenSeats ? 'bg-(--ui-border-accented)' : 'bg-amber-400 dark:bg-amber-300'
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
  </article>
</template>
