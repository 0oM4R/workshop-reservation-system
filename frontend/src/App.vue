<script setup lang="ts">
import axios from 'axios'
import { ref } from 'vue'

const health = ref('loading...')

axios
  .get('/api/health')
  .then((response) => {
    health.value = JSON.stringify(response.data)
  })
  .catch((error: unknown) => {
    health.value = `unreachable: ${error instanceof Error ? error.message : String(error)}`
  })
</script>

<template>
  <UApp>
    <UContainer class="py-8">
      <h1 class="text-2xl font-bold">Workshop Reservations</h1>
      <p class="mt-4">API health: {{ health }}</p>
    </UContainer>
  </UApp>
</template>
