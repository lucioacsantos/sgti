<script setup lang="ts">
import { ref, computed } from 'vue'

const props = defineProps<{
  title: string
  message: string
  confirmLabel?: string
  danger?: boolean
}>()

const emit = defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()

const busy = ref(false)

const btnClass = computed(() =>
  props.danger
    ? 'bg-rose-600 hover:bg-rose-500 text-white'
    : 'bg-emerald-600 hover:bg-emerald-500 text-slate-950'
)

async function onConfirm() {
  busy.value = true
  try {
    emit('confirm')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
    <div class="w-full max-w-sm bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl">
      <h3 class="text-sm font-bold text-slate-100">{{ title }}</h3>
      <p class="text-xs text-slate-400 mt-2 leading-relaxed">{{ message }}</p>
      <div class="flex justify-end gap-3 mt-6 pt-4 border-t border-slate-800">
        <button
          @click="emit('cancel')"
          class="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
        >
          Cancelar
        </button>
        <button
          @click="onConfirm"
          :disabled="busy"
          class="px-4 py-2 rounded-lg font-semibold text-xs transition-colors disabled:opacity-50"
          :class="btnClass"
        >
          {{ confirmLabel || 'Confirmar' }}
        </button>
      </div>
    </div>
  </div>
</template>