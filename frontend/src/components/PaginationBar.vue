<script setup lang="ts">
import { computed } from 'vue'
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-vue-next'

const props = defineProps<{
  page: number
  pageSize: number
  hasMore: boolean
  count: number
  disabled?: boolean
}>()

const emit = defineEmits<{
  (e: 'update:page', value: number): void
}>()

const firstItem = computed(() => (props.page - 1) * props.pageSize + 1)
const lastItem = computed(() => (props.page - 1) * props.pageSize + props.count)

function go(page: number) {
  if (props.disabled) return
  if (page < 1) return
  if (!props.hasMore && page > props.page) return
  emit('update:page', page)
}
</script>

<template>
  <div class="flex items-center justify-between gap-4 px-4 py-3 border-t border-slate-800 bg-slate-950/60">
    <p class="text-[11px] text-slate-500 font-mono">
      <template v-if="count > 0">
        Registros {{ firstItem }}–{{ lastItem }}
        <span v-if="hasMore" class="text-slate-400">· há mais páginas</span>
        <span v-else class="text-slate-600">· fim da listagem</span>
      </template>
      <template v-else>Nenhum registro</template>
    </p>

    <div class="flex items-center gap-1">
      <button
        @click="go(1)"
        :disabled="disabled || page === 1"
        class="p-1.5 rounded text-slate-400 hover:bg-slate-800 hover:text-slate-100 disabled:opacity-30 disabled:pointer-events-none transition-colors"
        title="Primeira página"
      >
        <ChevronsLeft class="w-4 h-4" />
      </button>
      <button
        @click="go(page - 1)"
        :disabled="disabled || page === 1"
        class="p-1.5 rounded text-slate-400 hover:bg-slate-800 hover:text-slate-100 disabled:opacity-30 disabled:pointer-events-none transition-colors"
        title="Anterior"
      >
        <ChevronLeft class="w-4 h-4" />
      </button>
      <span class="px-3 py-1 rounded bg-slate-800/60 text-xs font-mono text-slate-300">
        pág. {{ page }}
      </span>
      <button
        @click="go(page + 1)"
        :disabled="disabled || !hasMore"
        class="p-1.5 rounded text-slate-400 hover:bg-slate-800 hover:text-slate-100 disabled:opacity-30 disabled:pointer-events-none transition-colors"
        title="Próxima"
      >
        <ChevronRight class="w-4 h-4" />
      </button>
      <button
        @click="go(page + 5)"
        :disabled="disabled || !hasMore"
        class="p-1.5 rounded text-slate-400 hover:bg-slate-800 hover:text-slate-100 disabled:opacity-30 disabled:pointer-events-none transition-colors"
        title="Avançar 5 páginas"
      >
        <ChevronsRight class="w-4 h-4" />
      </button>
    </div>
  </div>
</template>