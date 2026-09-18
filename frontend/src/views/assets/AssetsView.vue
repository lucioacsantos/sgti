<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import * as XLSX from 'xlsx'
import { useAuthStore } from '@/stores/auth'
import {
  ativosService, ipService, auditService, referenceService
} from '@/services/cmdb.services'
import type { Ativo, EnderecoIp, AuditLog, Ambiente, Area, TipoAtivo } from '@/services/cmdb'
import PaginationBar from '@/components/PaginationBar.vue'
import ErrorAlert from '@/components/ErrorAlert.vue'
import LoadingState from '@/components/LoadingState.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import {
  Server, Search, Trash2, Eye, X, Globe, History, RefreshCw, Download, Pencil, Loader2, Check
} from 'lucide-vue-next'

const authStore = useAuthStore()

// ===== Listagem paginada =====
const ativos = ref<Ativo[]>([])
const page = ref(1)
const pageSize = ref(50)
const hasMore = ref(false)
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)
const search = ref('')
const tipoFilter = ref<number | null>(null)
const ambienteFilter = ref<number | null>(null)
const areaFilter = ref<number | null>(null)

const hasActiveFilter = computed(() =>
  !!search.value.trim() || tipoFilter.value !== null || ambienteFilter.value !== null || areaFilter.value !== null
)

// ===== Debounce da busca =====
const searchInput = ref('')
let searchTimer: ReturnType<typeof setTimeout> | undefined
watch(searchInput, (val) => {
  clearTimeout(searchTimer)
  searchTimer = setTimeout(() => { search.value = val }, 350)
})

// ===== Referências para exibição =====
const tipos = ref<Map<number, string>>(new Map())
const ambientes = ref<Map<number, string>>(new Map())
const statuses = ref<Map<number, string>>(new Map())
const criticidades = ref<Map<number, string>>(new Map())
const areas = ref<Map<number, string>>(new Map())
const tipoOptions = ref<TipoAtivo[]>([])
const ambienteOptions = ref<Ambiente[]>([])
const areaOptions = ref<Area[]>([])

// ===== Detalhe do ativo =====
const selected = ref<Ativo | null>(null)
const detailIps = ref<EnderecoIp[]>([])
const detailLogs = ref<AuditLog[]>([])
const detailLoading = ref(false)

// ===== Exclusão =====
const toDelete = ref<Ativo | null>(null)
const deleting = ref(false)

// ===== Edição manual (área / criticidade) =====
const editing = ref(false)
const saving = ref(false)
const editForm = ref<{ areas_id: number | null; criticidade_id: number | null }>({ areas_id: null, criticidade_id: null })
const editTarget = ref<Ativo | null>(null)

function canEdit() {
  return authStore.isAdmin || authStore.roles.includes('analyst')
}

function openEdit() {
  if (!selected.value) return
  editTarget.value = selected.value
  editForm.value = {
    areas_id: selected.value.areas_id ?? null,
    criticidade_id: selected.value.criticidade_id ?? null
  }
  editing.value = true
}

function closeEdit() {
  editing.value = false
  editTarget.value = null
}

async function saveEdit() {
  if (!editTarget.value) return
  saving.value = true
  errorMessage.value = null
  try {
    const payload: Partial<Ativo> = {}
    if (editForm.value.areas_id !== editTarget.value.areas_id) payload.areas_id = editForm.value.areas_id ?? null
    if (editForm.value.criticidade_id !== editTarget.value.criticidade_id) payload.criticidade_id = editForm.value.criticidade_id ?? null
    if (Object.keys(payload).length === 0) {
      closeEdit()
      return
    }
    const updated = await ativosService.update(editTarget.value.nome, payload)
    selected.value = updated
    closeEdit()
    await loadPage()
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    saving.value = false
  }
}

const canDelete = computed(() => authStore.isAdmin || authStore.roles.includes('analyst'))

// ===== Exportação XLSX =====
const exporting = ref(false)

async function exportToXlsx() {
  if (exporting.value) return
  exporting.value = true
  errorMessage.value = null
  try {
    let data: Ativo[]
    if (hasActiveFilter.value) {
      data = await ativosService.list(0, 5000, {
        search: search.value.trim() || undefined,
        tipo_id: tipoFilter.value ?? undefined,
        ambiente_id: ambienteFilter.value ?? undefined,
        areas_id: areaFilter.value ?? undefined
      })
    } else {
      data = []
      let skip = 0
      for (;;) {
        const pageData = await ativosService.list(skip, 1000)
        data.push(...pageData)
        if (pageData.length < 1000) break
        skip += 1000
      }
    }

    const rows = data.map(a => ({
      'ID': a.id,
      'Nome': a.nome,
      'Descrição': a.descricao || '',
      'Tipo': tipos.value.get(a.tipo_id) || '',
      'Ambiente': a.ambiente_id ? (ambientes.value.get(a.ambiente_id) || '') : '',
      'Status': a.status_id ? (statuses.value.get(a.status_id) || '') : '',
      'Criticidade': a.criticidade_id ? (criticidades.value.get(a.criticidade_id) || '') : '',
      'Área': a.areas_id ? (areas.value.get(a.areas_id) || '') : '',
      'Criado em': a.created_at ? new Date(a.created_at).toLocaleString('pt-BR') : ''
    }))

    const ws = XLSX.utils.json_to_sheet(rows)
    ws['!cols'] = [
      { wch: 8 }, { wch: 30 }, { wch: 50 }, { wch: 18 },
      { wch: 14 }, { wch: 14 }, { wch: 14 }, { wch: 20 }, { wch: 20 }
    ]
    const wb = XLSX.utils.book_new()
    XLSX.utils.book_append_sheet(wb, ws, 'Ativos')

    const suffix = hasActiveFilter.value ? `filtrado_${new Date().toISOString().slice(0, 10)}` : new Date().toISOString().slice(0, 10)
    XLSX.writeFile(wb, `ativos_${suffix}.xlsx`)
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    exporting.value = false
  }
}

async function loadPage() {
  isLoading.value = true
  errorMessage.value = null
  try {
    const filters = hasActiveFilter.value
      ? {
          search: search.value.trim() || undefined,
          tipo_id: tipoFilter.value ?? undefined,
          ambiente_id: ambienteFilter.value ?? undefined,
          areas_id: areaFilter.value ?? undefined
        }
      : undefined
    const data = await ativosService.list(
      hasActiveFilter.value ? 0 : (page.value - 1) * pageSize.value,
      hasActiveFilter.value ? 5000 : pageSize.value,
      filters
    )
    ativos.value = data
    hasMore.value = !hasActiveFilter.value && data.length >= pageSize.value
  } catch (err) {
    errorMessage.value = String(err)
    ativos.value = []
  } finally {
    isLoading.value = false
  }
}

function clearFilters() {
  searchInput.value = ''
  clearTimeout(searchTimer)
  search.value = ''
  tipoFilter.value = null
  ambienteFilter.value = null
  areaFilter.value = null
  page.value = 1
}

watch([search, tipoFilter, ambienteFilter, areaFilter], () => {
  if (page.value === 1) {
    loadPage()
  } else {
    page.value = 1 // watcher de page dispara o loadPage
  }
})

async function loadReferences() {
  const [t, a, s, c, ar] = await Promise.allSettled([
    referenceService.tiposAtivos(),
    referenceService.ambientes(),
    referenceService.statusAtivos(),
    referenceService.criticidades(),
    referenceService.areas()
  ])
  if (t.status === 'fulfilled') {
    tipos.value = new Map(t.value.map(x => [x.id, x.nome]))
    tipoOptions.value = t.value
  }
  if (a.status === 'fulfilled') {
    ambientes.value = new Map(a.value.map(x => [x.id, x.nome]))
    ambienteOptions.value = a.value
  }
  if (s.status === 'fulfilled') statuses.value = new Map(s.value.map(x => [x.id, x.nome]))
  if (c.status === 'fulfilled') criticidades.value = new Map(c.value.map(x => [x.id, x.nivel]))
  if (ar.status === 'fulfilled') {
    areas.value = new Map(ar.value.map(x => [x.id, x.sigla]))
    areaOptions.value = ar.value
  }
}

watch(page, loadPage)

function fmtDate(iso?: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

// ===== Detalhe =====
async function openDetail(ativo: Ativo) {
  selected.value = ativo
  detailIps.value = []
  detailLogs.value = []
  detailLoading.value = true
  try {
    const [ips, logs] = await Promise.allSettled([
      ipService.list(ativo.id, 0, 100),
      auditService.list({ entidade: 'ativo', entidade_id: ativo.id, limit: 20 })
    ])
    if (ips.status === 'fulfilled') detailIps.value = ips.value
    if (logs.status === 'fulfilled') detailLogs.value = logs.value
  } finally {
    detailLoading.value = false
  }
}

function closeDetail() {
  selected.value = null
}

// ===== Exclusão =====
async function confirmDelete() {
  if (!toDelete.value) return
  deleting.value = true
  try {
    await ativosService.delete(toDelete.value.nome)
    toDelete.value = null
    await loadPage()
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    deleting.value = false
  }
}

const criticidadeBadge: Record<string, string> = {
  critica: 'bg-rose-500/10 text-rose-400 border-rose-500/20',
  alta: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  media: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
  baixa: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
}

function critBadge(nivel?: string | null): string {
  if (!nivel) return 'bg-slate-800 text-slate-400 border-slate-700'
  return criticidadeBadge[nivel.toLowerCase()] || 'bg-slate-800 text-slate-400 border-slate-700'
}

onMounted(async () => {
  await Promise.all([loadPage(), loadReferences()])
})
</script>

<template>
  <div class="space-y-6">
    <!-- Cabeçalho -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 class="text-lg font-bold text-slate-100 flex items-center gap-2">
          <Server class="w-5 h-5 text-emerald-400" />
          Inventário de Ativos
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">
          Cadastrado e mantido por automações via Service Tokens — consulta e gestão de ciclo de vida aqui.
        </p>
      </div>

      <div class="flex items-center gap-2">
        <button
          @click="exportToXlsx"
          :disabled="exporting"
          class="inline-flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs rounded-lg transition-colors disabled:opacity-50"
          :title="hasActiveFilter ? 'Exportar resultado da filtragem em XLSX' : 'Exportar lista completa em XLSX'"
        >
          <Download class="w-3.5 h-3.5" :class="{ 'animate-pulse': exporting }" />
          {{ exporting ? 'Exportando...' : 'Exportar XLSX' }}
        </button>

        <button
          @click="loadPage"
          :disabled="isLoading"
          class="inline-flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
          Atualizar
        </button>
      </div>
    </div>

    <ErrorAlert :error="errorMessage" />

    <!-- Filtros -->
    <div class="flex flex-col sm:flex-row sm:items-end gap-3">
      <div class="relative flex-1 max-w-md">
        <Search class="w-4 h-4 text-slate-500 absolute left-3 top-2.5 pointer-events-none" />
        <input
          v-model="searchInput"
          type="text"
          placeholder="Filtrar por nome ou descrição..."
          class="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-emerald-500 transition-colors"
        />
      </div>

      <select
        v-model="tipoFilter"
        class="px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
      >
        <option :value="null">Tipo: todos</option>
        <option v-for="tipo in tipoOptions" :key="tipo.id" :value="tipo.id">{{ tipo.nome }}</option>
      </select>

      <select
        v-model="ambienteFilter"
        class="px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
      >
        <option :value="null">Ambiente: todos</option>
        <option v-for="amb in ambienteOptions" :key="amb.id" :value="amb.id">{{ amb.nome }}</option>
      </select>

      <select
        v-model="areaFilter"
        class="px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-emerald-500 transition-colors"
      >
        <option :value="null">Área: todas</option>
        <option v-for="area in areaOptions" :key="area.id" :value="area.id">{{ area.sigla }} — {{ area.nome }}</option>
      </select>

      <button
        v-if="hasActiveFilter"
        @click="clearFilters"
        class="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs rounded-lg transition-colors"
      >
        <X class="w-3.5 h-3.5" />
        Limpar filtros
      </button>
    </div>

    <!-- Tabela -->
    <div class="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
      <LoadingState v-if="isLoading" />

      <template v-else>
        <table class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-900/50 text-slate-400 font-semibold uppercase tracking-wider">
              <th class="p-3 pl-4">ID</th>
              <th class="p-3">Nome</th>
              <th class="p-3">Tipo</th>
              <th class="p-3">Ambiente</th>
              <th class="p-3">Status</th>
              <th class="p-3">Criticidade</th>
              <th class="p-3">Área</th>
              <th class="p-3 pr-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="ativos.length === 0">
              <td colspan="8" class="p-8 text-center text-slate-500">
                {{ hasActiveFilter ? 'Nenhum ativo corresponde aos filtros aplicados.' : 'Nenhum ativo cadastrado.' }}
              </td>
            </tr>
            <tr
              v-for="ativo in ativos"
              :key="ativo.id"
              class="hover:bg-slate-900/40 transition-colors"
            >
              <td class="p-3 pl-4 font-mono text-slate-500">{{ ativo.id }}</td>
              <td class="p-3">
                <div class="font-medium text-slate-100">{{ ativo.nome }}</div>
                <div v-if="ativo.descricao" class="text-[10px] text-slate-500 max-w-xs truncate">{{ ativo.descricao }}</div>
              </td>
              <td class="p-3 text-slate-400">{{ tipos.get(ativo.tipo_id) || '—' }}</td>
              <td class="p-3 text-slate-400">{{ ativo.ambiente_id ? ambientes.get(ativo.ambiente_id) || '—' : '—' }}</td>
              <td class="p-3 text-slate-400">{{ ativo.status_id ? statuses.get(ativo.status_id) || '—' : '—' }}</td>
              <td class="p-3">
                <span
                  class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium border capitalize"
                  :class="critBadge(ativo.criticidade_id ? criticidades.get(ativo.criticidade_id) : null)"
                >
                  {{ ativo.criticidade_id ? criticidades.get(ativo.criticidade_id) || '—' : 'não classificado' }}
                </span>
              </td>
              <td class="p-3 font-mono text-slate-400">{{ ativo.areas_id ? areas.get(ativo.areas_id) || '—' : '—' }}</td>
              <td class="p-3 pr-4 text-right">
                <div class="inline-flex items-center gap-1">
                  <button
                    @click="openDetail(ativo)"
                    class="p-1.5 hover:bg-slate-800 rounded text-slate-400 hover:text-emerald-400 transition-colors"
                    title="Detalhar"
                  >
                    <Eye class="w-3.5 h-3.5" />
                  </button>
                  <button
                    v-if="canDelete"
                    @click="toDelete = ativo"
                    class="p-1.5 hover:bg-rose-500/10 rounded text-slate-400 hover:text-rose-400 transition-colors"
                    title="Excluir"
                  >
                    <Trash2 class="w-3.5 h-3.5" />
                  </button>
                </div>
              </td>
            </tr>
          </tbody>
        </table>

        <PaginationBar
          v-if="!hasActiveFilter"
          v-model:page="page"
          :page-size="pageSize"
          :has-more="hasMore"
          :count="ativos.length"
          :disabled="isLoading"
        />
        <div v-else class="px-4 py-3 border-t border-slate-800 bg-slate-950/60 text-[11px] text-slate-500 font-mono">
          Exibindo todos os registros correspondentes aos filtros — {{ ativos.length }} resultado(s)
        </div>
      </template>
    </div>

    <!-- Drawer de detalhe -->
    <div v-if="selected" class="fixed inset-0 z-50 flex">
      <div class="absolute inset-0 bg-slate-950/80 backdrop-blur-sm" @click="closeDetail" />

      <div class="relative ml-auto w-full max-w-2xl h-full bg-slate-900 border-l border-slate-800 shadow-2xl overflow-y-auto">
        <div class="sticky top-0 bg-slate-900/95 backdrop-blur border-b border-slate-800 p-5 flex items-center justify-between z-10">
          <div>
            <h3 class="text-sm font-bold text-slate-100 font-mono">{{ selected.nome }}</h3>
            <p class="text-[11px] text-slate-500 mt-0.5">
              {{ tipos.get(selected.tipo_id) || 'Tipo desconhecido' }} · cadastrado em {{ fmtDate(selected.created_at) }}
            </p>
          </div>
          <button @click="closeDetail" class="p-1.5 hover:bg-slate-800 rounded text-slate-400 hover:text-slate-100 transition-colors">
            <X class="w-4 h-4" />
          </button>
        </div>

        <div class="p-5 space-y-6">
          <!-- Atributos -->
          <section>
            <div class="flex items-center justify-between mb-3">
              <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-400">Atributos</h4>
              <button
                v-if="canEdit()"
                @click="openEdit"
                class="inline-flex items-center gap-1.5 px-2.5 py-1 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-[11px] rounded-lg transition-colors"
                title="Editar área e criticidade"
              >
                <Pencil class="w-3 h-3" />
                Editar
              </button>
            </div>
            <dl class="grid grid-cols-2 gap-3 text-xs">
              <div class="p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                <dt class="text-slate-500 mb-1">Ambiente</dt>
                <dd class="text-slate-200">{{ selected.ambiente_id ? ambientes.get(selected.ambiente_id) || '—' : '—' }}</dd>
              </div>
              <div class="p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                <dt class="text-slate-500 mb-1">Status</dt>
                <dd class="text-slate-200">{{ selected.status_id ? statuses.get(selected.status_id) || '—' : '—' }}</dd>
              </div>
              <div class="p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                <dt class="text-slate-500 mb-1">Criticidade</dt>
                <dd class="text-slate-200 capitalize">{{ selected.criticidade_id ? criticidades.get(selected.criticidade_id) || '—' : '—' }}</dd>
              </div>
              <div class="p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                <dt class="text-slate-500 mb-1">Área</dt>
                <dd class="text-slate-200">{{ selected.areas_id ? areas.get(selected.areas_id) || '—' : '—' }}</dd>
              </div>
              <div class="col-span-2 p-3 bg-slate-950/60 border border-slate-800 rounded-lg">
                <dt class="text-slate-500 mb-1">Descrição</dt>
                <dd class="text-slate-200">{{ selected.descricao || 'Sem descrição registrada.' }}</dd>
              </div>
            </dl>
          </section>

          <!-- Endereços IP -->
          <section>
            <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
              <Globe class="w-3.5 h-3.5 text-sky-400" />
              Endereços IP ({{ detailIps.length }})
            </h4>

            <div v-if="detailLoading" class="text-xs text-slate-500">Carregando...</div>
            <div v-else-if="detailIps.length === 0" class="text-xs text-slate-500">Nenhum endereço registrado.</div>

            <div v-else class="space-y-2">
              <div
                v-for="ip in detailIps"
                :key="ip.id"
                class="flex items-center justify-between p-3 bg-slate-950/60 border border-slate-800 rounded-lg"
              >
                <div class="flex items-center gap-3">
                  <span class="font-mono text-xs text-sky-300">{{ ip.ip }}</span>
                  <span
                    v-if="ip.primario"
                    class="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                  >
                    primário
                  </span>
                </div>
                <div class="flex items-center gap-2 text-[10px] text-slate-500">
                  <span class="font-mono">{{ ip.tipo }}</span>
                  <span v-if="ip.interface" class="font-mono">{{ ip.interface }}</span>
                </div>
              </div>
            </div>
          </section>

          <!-- Histórico -->
          <section>
            <h4 class="text-xs font-semibold uppercase tracking-wider text-slate-400 mb-3 flex items-center gap-2">
              <History class="w-3.5 h-3.5 text-amber-400" />
              Histórico de alterações
            </h4>

            <div v-if="detailLoading" class="text-xs text-slate-500">Carregando...</div>
            <div v-else-if="detailLogs.length === 0" class="text-xs text-slate-500">Nenhum evento de auditoria.</div>

            <div v-else class="space-y-2">
              <div
                v-for="log in detailLogs"
                :key="log.id"
                class="p-3 bg-slate-950/60 border border-slate-800 rounded-lg"
              >
                <div class="flex items-center justify-between gap-2 mb-1">
                  <span
                    class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded"
                    :class="log.acao === 'CREATE' ? 'bg-emerald-500/10 text-emerald-400' : log.acao === 'DELETE' ? 'bg-rose-500/10 text-rose-400' : log.acao === 'UPDATE_MANUAL' ? 'bg-violet-500/10 text-violet-400' : 'bg-sky-500/10 text-sky-400'"
                  >
                    {{ log.acao || '—' }}
                  </span>
                  <span class="text-[10px] text-slate-500 font-mono">{{ fmtDate(log.created_at) }}</span>
                </div>
                <p class="text-[10px] text-slate-500">por {{ log.usuario || 'sistema' }}</p>
                <details v-if="log.depois && Object.keys(log.depois).length > 0" class="mt-2">
                  <summary class="text-[10px] text-slate-400 cursor-pointer hover:text-slate-200">Ver snapshot</summary>
                  <pre class="mt-2 text-[10px] text-slate-500 bg-slate-950 p-2 rounded overflow-x-auto font-mono">{{ JSON.stringify(log.depois, null, 2) }}</pre>
                </details>
              </div>
            </div>
          </section>
        </div>
      </div>
    </div>

    <!-- Modal de edição manual (área / criticidade) -->
    <div v-if="editing && editTarget" class="fixed inset-0 z-[60] flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div class="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl">
        <div class="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
          <div>
            <h3 class="text-sm font-bold text-slate-100 font-mono">{{ editTarget.nome }}</h3>
            <p class="text-[11px] text-slate-500 mt-0.5">Editar classificação — a alteração será registrada na trilha de auditoria.</p>
          </div>
          <button @click="closeEdit" class="text-slate-500 hover:text-slate-300">
            <X class="w-4 h-4" />
          </button>
        </div>

        <form @submit.prevent="saveEdit" class="space-y-4 text-xs">
          <div>
            <label class="block font-medium text-slate-300 mb-1">Área</label>
            <select
              v-model="editForm.areas_id"
              class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option :value="null">— sem área —</option>
              <option v-for="area in areaOptions" :key="area.id" :value="area.id">{{ area.sigla }} — {{ area.nome }}</option>
            </select>
          </div>

          <div>
            <label class="block font-medium text-slate-300 mb-1">Criticidade</label>
            <select
              v-model="editForm.criticidade_id"
              class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option :value="null">— não classificado —</option>
              <option
                v-for="(nivel, id) in criticidades"
                :key="id"
                :value="id"
                class="capitalize"
              >
                {{ nivel }}
              </option>
            </select>
          </div>

          <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              @click="closeEdit"
              class="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              :disabled="saving"
              class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-semibold transition-colors disabled:opacity-50"
            >
              <Loader2 v-if="saving" class="w-3.5 h-3.5 animate-spin" />
              <Check v-else class="w-3.5 h-3.5" />
              Salvar
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Confirmação de exclusão -->
    <ConfirmDialog
      v-if="toDelete"
      title="Excluir ativo"
      :message="`O ativo '${toDelete.nome}' será removido permanentemente, incluindo seus endereços IP. Os endereços podem ter sido provisionados por automação — confirme se deseja prosseguir.`"
      confirm-label="Excluir definitivamente"
      danger
      @confirm="confirmDelete"
      @cancel="toDelete = null"
    />
  </div>
</template>