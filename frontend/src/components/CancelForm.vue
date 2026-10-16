<script setup lang="ts">
import type { FormSubmitEvent } from '@nuxt/ui'
import { reactive, ref } from 'vue'
import type { CancelOutcome } from '../composables/useWorkshops'
import { cancelSchema, type CancelValues } from '../schemas'

const props = defineProps<{
  submit: (email: string) => Promise<CancelOutcome>
  busy: boolean
  email?: string
}>()
const emit = defineEmits<{ done: [outcome: CancelOutcome] }>()

const state = reactive({ email: props.email ?? '' })
const failure = ref<CancelOutcome | null>(null)

async function onSubmit(event: FormSubmitEvent<CancelValues>) {
  const outcome = await props.submit(event.data.email)
  if (outcome.kind === 'cancelled') {
    emit('done', outcome)
    return
  }
  failure.value = outcome
}
</script>

<template>
  <UForm :schema="cancelSchema" :state="state" class="space-y-4" @submit="onSubmit">
    <UFormField label="Email you reserved with" name="email">
      <UInput v-model="state.email" type="email" autocomplete="email" class="w-full" />
    </UFormField>
    <UAlert v-if="failure" color="error" variant="subtle" :description="failure.message" />
    <UButton type="submit" color="neutral" block :disabled="busy" :loading="busy">
      Cancel reservation
    </UButton>
  </UForm>
</template>
