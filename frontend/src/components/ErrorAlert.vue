<script setup lang="ts">
defineProps<{
  error: string | null
}>()
</script>

<template>
  <div
    v-if="error"
    class="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-start gap-2.5 text-rose-400 text-xs leading-relaxed"
  >
    <svg class="w-4 h-4 shrink-0 mt-0.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="12" />
    </svg>
    <span>{{ error }}</span>
  </div>
</template>