<script setup lang="ts">
withDefaults(
  defineProps<{
    isLoading?: boolean
    label?: string
  }>(),
  {
    isLoading: true,
    label: 'Consultando base de dados...'
  }
)
</script>

<template>
  <div v-if="isLoading" class="p-12 flex flex-col items-center justify-center text-slate-500">
    <svg class="w-6 h-6 animate-spin mb-2 text-emerald-400" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
    <span class="text-xs">{{ label }}</span>
  </div>
</template>