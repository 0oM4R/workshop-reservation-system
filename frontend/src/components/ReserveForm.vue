<script setup lang="ts">
import type { FormSubmitEvent } from '@nuxt/ui'
import { reactive, ref } from 'vue'
import type { ReserveOutcome } from '../composables/useWorkshops'
import { reserveSchema, type ReserveValues } from '../schemas'

const props = defineProps<{
  submit: (values: ReserveValues) => Promise<ReserveOutcome>
  busy: boolean
}>()
const emit = defineEmits<{ done: [outcome: ReserveOutcome] }>()

const state = reactive({ name: '', email: '' })
const problem = ref<ReserveOutcome | null>(null)

async function onSubmit(event: FormSubmitEvent<ReserveValues>) {
  const outcome = await props.submit(event.data)
  if (outcome.kind === 'reserved' || outcome.kind === 'already') {
    emit('done', outcome)
    return
  }
  problem.value = outcome
}
</script>

<template>
  <UForm :schema="reserveSchema" :state="state" class="space-y-4" @submit="onSubmit">
    <UFormField label="Name" name="name">
      <UInput v-model="state.name" autocomplete="name" class="w-full" />
    </UFormField>
    <UFormField label="Email" name="email">
      <UInput v-model="state.email" type="email" autocomplete="email" class="w-full" />
    </UFormField>
    <UAlert
      v-if="problem"
      :color="problem.kind === 'full' ? 'warning' : 'error'"
      variant="subtle"
      :description="problem.message"
    />
    <UButton type="submit" block :disabled="busy" :loading="busy">Reserve a seat</UButton>
  </UForm>
</template>
