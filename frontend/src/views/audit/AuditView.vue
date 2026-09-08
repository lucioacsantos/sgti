<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { auditService } from '@/services/cmdb.services'
import type { AuditLog } from '@/services/cmdb'
import PaginationBar from '@/components/PaginationBar.vue'
import ErrorAlert from '@/components/ErrorAlert.vue'
import LoadingState from '@/components/LoadingState.vue'
import {
  ShieldAlert, RefreshCw, ChevronDown, ChevronRight, History
} from 'lucide-vue-next'

const logs = ref<AuditLog[]>([])
const page = ref(1)
const pageSize = ref(50)
const hasMore = ref(false)
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)

const entidadeFilter = ref('')

// Expansão de snapshots JSON
const expanded = ref<Set<number>>(new Set())

async function loadPage() {
  isLoading.value = true
  errorMessage.value = null
  try {
    const params: Record<string, unknown> = {
      skip: (page.value - 1) * pageSize.value,
      limit: pageSize.value
    }
    if (entidadeFilter.value) params.entidade = entidadeFilter.value

    logs.value = await auditService.list(params)
    hasMore.value = logs.value.length >= pageSize.value
    expanded.value.clear()
  } catch (err) {
    errorMessage.value = String(err)
    logs.value = []
  } finally {
    isLoading.value = false
  }
}

watch([page, entidadeFilter], () => {
  if (isLoading.value) return
  loadPage()
})

function toggleExpand(id: number) {
  if (expanded.value.has(id)) {
    expanded.value.delete(id)
  } else {
    expanded.value.add(id)
  }
}

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function acaoClass(acao?: string | null): string {
  switch (acao) {
    case 'CREATE': return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    case 'UPDATE': return 'bg-sky-500/10 text-sky-400 border-sky-500/20'
    case 'DELETE': return 'bg-rose-500/10 text-rose-400 border-rose-500/20'
    default: return 'bg-slate-800 text-slate-400 border-slate-700'
  }
}

onMounted(loadPage)
</script>

<template>
  <div class="space-y-6">
    <!-- Cabeçalho -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 class="text-lg font-bold text-slate-100 flex items-center gap-2">
          <ShieldAlert class="w-5 h-5 text-amber-400" />
          Trilha de Auditoria
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">
          Registro imutável de todas as alterações feitas por usuários e automações.
        </p>
      </div>

      <button
        @click="loadPage"
        :disabled="isLoading"
        class="inline-flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs rounded-lg transition-colors disabled:opacity-50"
      >
        <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
        Atualizar
      </button>
    </div>

    <ErrorAlert :error="errorMessage" />

    <!-- Filtros -->
    <div class="flex flex-wrap items-center gap-3">
      <label class="text-xs text-slate-400 font-medium uppercase tracking-wider">Entidade:</label>
      <select
        v-model="entidadeFilter"
        class="px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-amber-500 transition-colors"
      >
        <option value="">Todas</option>
        <option value="ativo">Ativo</option>
        <option value="endereco_ip">Endereço IP</option>
      </select>
    </div>

    <!-- Tabela -->
    <div class="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
      <LoadingState v-if="isLoading" />

      <template v-else>
        <table class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-900/50 text-slate-400 font-semibold uppercase tracking-wider">
              <th class="p-3 pl-4 w-8"></th>
              <th class="p-3">Data/Hora</th>
              <th class="p-3">Ação</th>
              <th class="p-3">Entidade</th>
              <th class="p-3">Usuário</th>
              <th class="p-3 pr-4">Detalhe</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="logs.length === 0">
              <td colspan="6" class="p-8 text-center text-slate-500">Nenhum evento registrado.</td>
            </tr>
            <template v-for="log in logs" :key="log.id">
              <tr class="hover:bg-slate-900/40 transition-colors cursor-pointer" @click="toggleExpand(log.id)">
                <td class="p-3 pl-4 text-slate-500">
                  <component
                    :is="expanded.has(log.id) ? ChevronDown : ChevronRight"
                    v-if="log.antes || log.depois"
                    class="w-3.5 h-3.5"
                  />
                </td>
                <td class="p-3 font-mono text-slate-400">{{ fmtDate(log.created_at) }}</td>
                <td class="p-3">
                  <span
                    class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-bold font-mono border"
                    :class="acaoClass(log.acao)"
                  >
                    {{ log.acao || '—' }}
                  </span>
                </td>
                <td class="p-3 text-slate-200">
                  {{ log.entidade }}<template v-if="log.entidade_id"> <span class="font-mono text-slate-500">#{{ log.entidade_id }}</span></template>
                </td>
                <td class="p-3 font-mono text-slate-400">{{ log.usuario || 'sistema' }}</td>
                <td class="p-3 pr-4 text-slate-500">
                  <History v-if="log.antes || log.depois" class="w-3.5 h-3.5 text-slate-600" />
                  <span v-else>—</span>
                </td>
              </tr>

              <!-- Linha expandida: diff antes/depois -->
              <tr v-if="expanded.has(log.id)">
                <td :colspan="6" class="p-4 bg-slate-900/60 border-b border-slate-800">
                  <div class="grid grid-cols-1 lg:grid-cols-2 gap-4">
                    <div v-if="log.antes">
                      <h5 class="text-[10px] font-bold uppercase tracking-wider text-rose-400 mb-2">Antes</h5>
                      <pre class="text-[10px] text-slate-400 bg-slate-950 p-3 rounded-lg overflow-x-auto font-mono border border-slate-800">{{ JSON.stringify(log.antes, null, 2) }}</pre>
                    </div>
                    <div v-if="log.depois">
                      <h5 class="text-[10px] font-bold uppercase tracking-wider text-emerald-400 mb-2">Depois</h5>
                      <pre class="text-[10px] text-slate-400 bg-slate-950 p-3 rounded-lg overflow-x-auto font-mono border border-slate-800">{{ JSON.stringify(log.depois, null, 2) }}</pre>
                    </div>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>

        <PaginationBar
          v-model:page="page"
          :page-size="pageSize"
          :has-more="hasMore"
          :count="logs.length"
          :disabled="isLoading"
        />
      </template>
    </div>
  </div>
</template>