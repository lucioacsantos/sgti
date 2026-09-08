<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { referenceService } from '@/services/cmdb.services'
import type {
  TipoAtivo, Ambiente, StatusAtivo, Criticidade, SistemaOperacional, Area, TipoRelacionamento
} from '@/services/cmdb'
import ErrorAlert from '@/components/ErrorAlert.vue'
import LoadingState from '@/components/LoadingState.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import {
  Database, Plus, Pencil, Trash2, X, Check, Search, RefreshCw, Loader2
} from 'lucide-vue-next'

type CategoryKey = 'tipos-ativos' | 'ambientes' | 'status' | 'criticidades' | 'areas' | 'sos' | 'tipos-relacionamento'
interface Row {
  id: number
  primary: string
  secondary?: string | null
  tertiary?: string | null
  raw: any
}

const categories: { key: CategoryKey; label: string; description: string }[] = [
  { key: 'tipos-ativos', label: 'Tipos de Ativo', description: 'Categorias de equipamentos e componentes do inventário.' },
  { key: 'ambientes', label: 'Ambientes', description: 'Segregações lógicas: produção, homologação, desenvolvimento...' },
  { key: 'status', label: 'Status de Ativo', description: 'Estados de ciclo de vida dos ativos.' },
  { key: 'criticidades', label: 'Criticidades', description: 'Níveis de criticidade para priorização.' },
  { key: 'areas', label: 'Áreas', description: 'Áreas organizacionais responsáveis.' },
  { key: 'sos', label: 'Sistemas Operacionais', description: 'SOs suportados e ciclo de vida (lifecycle).' },
  { key: 'tipos-relacionamento', label: 'Tipos de Relacionamento', description: 'Tipos de vínculo entre ativos no mapa de TI.' }
]

const activeCategory = ref<CategoryKey>('tipos-ativos')
const rows = ref<Row[]>([])
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)
const search = ref('')

// Modal de edição
const isModalOpen = ref(false)
const isSaving = ref(false)
const editingId = ref<number | null>(null)
const form = ref<{ nome: string; sigla: string; abreviacao: string; descricao: string; lifecycle: string; nivel: string }>({
  nome: '', sigla: '', abreviacao: '', descricao: '', lifecycle: '', nivel: ''
})

// Exclusão
const toDelete = ref<Row | null>(null)
const isDeleting = ref(false)

const currentCategory = computed(() => categories.find(c => c.key === activeCategory.value)!)

const filteredRows = computed(() => {
  const term = search.value.toLowerCase()
  if (!term) return rows.value
  return rows.value.filter(r =>
    r.primary.toLowerCase().includes(term) ||
    (r.secondary || '').toLowerCase().includes(term) ||
    (r.tertiary || '').toLowerCase().includes(term)
  )
})

async function loadRows() {
  isLoading.value = true
  errorMessage.value = null
  search.value = ''
  try {
    let data: Row[] = []
    switch (activeCategory.value) {
      case 'tipos-ativos': {
        const items: TipoAtivo[] = await referenceService.tiposAtivos()
        data = items.map(i => ({ id: i.id, primary: i.nome, secondary: null, tertiary: null, raw: i }))
        break
      }
      case 'ambientes': {
        const items: Ambiente[] = await referenceService.ambientes()
        data = items.map(i => ({ id: i.id, primary: i.nome, secondary: null, tertiary: null, raw: i }))
        break
      }
      case 'status': {
        const items: StatusAtivo[] = await referenceService.statusAtivos()
        data = items.map(i => ({ id: i.id, primary: i.nome, secondary: null, tertiary: null, raw: i }))
        break
      }
      case 'criticidades': {
        const items: Criticidade[] = await referenceService.criticidades()
        data = items.map(i => ({ id: i.id, primary: i.nivel, secondary: null, tertiary: null, raw: i }))
        break
      }
      case 'areas': {
        const items: Area[] = await referenceService.areas()
        data = items.map(i => ({ id: i.id, primary: i.nome, secondary: i.sigla, tertiary: null, raw: i }))
        break
      }
      case 'sos': {
        const items: SistemaOperacional[] = await referenceService.sistemasOperacionais()
        data = items.map(i => ({ id: i.id, primary: i.abreviacao, secondary: i.descricao, tertiary: i.lifecycle, raw: i }))
        break
      }
      case 'tipos-relacionamento': {
        const items: TipoRelacionamento[] = await referenceService.tiposRelacionamento()
        data = items.map(i => ({ id: i.id, primary: i.nome, secondary: i.descricao, tertiary: null, raw: i }))
        break
      }
    }
    rows.value = data
  } catch (err) {
    errorMessage.value = String(err)
    rows.value = []
  } finally {
    isLoading.value = false
  }
}

watch(activeCategory, loadRows)

// ===== Modal =====
function openCreate() {
  editingId.value = null
  form.value = { nome: '', sigla: '', abreviacao: '', descricao: '', lifecycle: '', nivel: '' }
  isModalOpen.value = true
}

function openEdit(row: Row) {
  editingId.value = row.id
  const r = row.raw
  form.value = {
    nome: r.nome ?? '',
    sigla: r.sigla ?? '',
    abreviacao: r.abreviacao ?? '',
    descricao: r.descricao ?? '',
    lifecycle: r.lifecycle ?? '',
    nivel: r.nivel ?? ''
  }
  isModalOpen.value = true
}

async function handleSave() {
  isSaving.value = true
  errorMessage.value = null
  try {
    const id = editingId.value
    switch (activeCategory.value) {
      case 'tipos-ativos': {
        const payload = { nome: form.value.nome }
        if (id) await referenceService.updateTipoAtivo(id, payload)
        else await referenceService.createTipoAtivo(payload)
        break
      }
      case 'ambientes': {
        const payload = { nome: form.value.nome }
        if (id) await referenceService.updateAmbiente(id, payload)
        else await referenceService.createAmbiente(payload)
        break
      }
      case 'status': {
        const payload = { nome: form.value.nome }
        if (id) await referenceService.updateStatus(id, payload)
        else await referenceService.createStatus(payload)
        break
      }
      case 'criticidades': {
        const payload = { nivel: form.value.nivel }
        if (id) await referenceService.updateCriticidade(id, payload)
        else await referenceService.createCriticidade(payload)
        break
      }
      case 'areas': {
        const payload = { nome: form.value.nome, sigla: form.value.sigla }
        if (id) await referenceService.updateArea(id, payload)
        else await referenceService.createArea(payload)
        break
      }
      case 'sos': {
        const payload = { abreviacao: form.value.abreviacao, descricao: form.value.descricao, lifecycle: form.value.lifecycle || undefined }
        if (id) await referenceService.updateSO(id, payload)
        else await referenceService.createSO(payload)
        break
      }
      case 'tipos-relacionamento': {
        const payload = { nome: form.value.nome, descricao: form.value.descricao || undefined }
        if (id) await referenceService.updateTipoRelacionamento(id, payload)
        else await referenceService.createTipoRelacionamento(payload)
        break
      }
    }
    isModalOpen.value = false
    await loadRows()
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    isSaving.value = false
  }
}

async function confirmDelete() {
  if (!toDelete.value) return
  isDeleting.value = true
  try {
    const id = toDelete.value.id
    switch (activeCategory.value) {
      case 'tipos-ativos': await referenceService.deleteTipoAtivo(id); break
      case 'ambientes': await referenceService.deleteAmbiente(id); break
      case 'status': await referenceService.deleteStatus(id); break
      case 'criticidades': await referenceService.deleteCriticidade(id); break
      case 'areas': await referenceService.deleteArea(id); break
      case 'sos': await referenceService.deleteSO(id); break
      case 'tipos-relacionamento': await referenceService.deleteTipoRelacionamento(id); break
    }
    toDelete.value = null
    await loadRows()
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    isDeleting.value = false
  }
}

const hasSigla = computed(() => activeCategory.value === 'areas')
const hasNivel = computed(() => activeCategory.value === 'criticidades')
const hasSO = computed(() => activeCategory.value === 'sos')

const primaryFieldLabel = computed(() => {
  if (hasNivel.value) return 'Nível'
  if (hasSO.value) return 'Abreviação'
  return 'Nome'
})

const primaryFieldPlaceholder = computed(() => {
  if (hasNivel.value) return 'ex: crítica, alta, média, baixa'
  if (hasSO.value) return 'ex: RHEL9, WIN2022'
  return 'ex: Servidor Físico, Produção'
})

onMounted(loadRows)
</script>

<template>
  <div class="space-y-6">
    <!-- Cabeçalho -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 class="text-lg font-bold text-slate-100 flex items-center gap-2">
          <Database class="w-5 h-5 text-indigo-400" />
          Tabelas Auxiliares
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">
          Área administrativa dos dados de referência usados pelas automações na classificação de ativos.
        </p>
      </div>

      <div class="flex items-center gap-2">
        <button
          @click="loadRows"
          :disabled="isLoading"
          class="inline-flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs rounded-lg transition-colors disabled:opacity-50"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
          Atualizar
        </button>
        <button
          @click="openCreate"
          class="inline-flex items-center gap-2 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-semibold text-xs rounded-lg transition-colors shadow-sm"
        >
          <Plus class="w-4 h-4" />
          Novo Registro
        </button>
      </div>
    </div>

    <ErrorAlert :error="errorMessage" />

    <!-- Abas -->
    <div class="flex border-b border-slate-800 overflow-x-auto">
      <button
        v-for="cat in categories"
        :key="cat.key"
        @click="activeCategory = cat.key"
        class="px-4 py-3 text-xs font-semibold whitespace-nowrap border-b-2 transition-colors"
        :class="activeCategory === cat.key
          ? 'border-indigo-500 text-indigo-400 bg-slate-950/40'
          : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'"
      >
        {{ cat.label }}
      </button>
    </div>

    <p class="text-xs text-slate-500">{{ currentCategory.description }}</p>

    <!-- Busca -->
    <div class="relative w-full max-w-sm">
      <Search class="w-4 h-4 text-slate-500 absolute left-3 top-2.5 pointer-events-none" />
      <input
        v-model="search"
        type="text"
        placeholder="Filtrar registros..."
        class="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition-colors"
      />
    </div>

    <!-- Tabela -->
    <div class="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
      <LoadingState v-if="isLoading" />

      <table v-else class="w-full text-left border-collapse text-xs">
        <thead>
          <tr class="border-b border-slate-800 bg-slate-900/50 text-slate-400 font-semibold uppercase tracking-wider">
            <th class="p-3 pl-4">{{ primaryFieldLabel }}</th>
            <th v-if="hasSigla" class="p-3">Sigla</th>
            <th v-if="hasSO || activeCategory === 'tipos-relacionamento'" class="p-3">Descrição</th>
            <th v-if="hasSO" class="p-3">Lifecycle</th>
            <th class="p-3 pr-4 text-right">Ações</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-800/60 text-slate-300">
          <tr v-if="filteredRows.length === 0">
            <td :colspan="5" class="p-8 text-center text-slate-500">
              Nenhum registro nesta tabela auxiliar.
            </td>
          </tr>
          <tr
            v-for="row in filteredRows"
            :key="row.id"
            class="hover:bg-slate-900/40 transition-colors"
          >
            <td class="p-3 pl-4 font-medium text-slate-100 font-mono">{{ row.primary }}</td>
            <td v-if="hasSigla" class="p-3 font-mono text-slate-400">{{ row.secondary || '—' }}</td>
            <td v-if="hasSO || activeCategory === 'tipos-relacionamento'" class="p-3 text-slate-400 max-w-sm truncate">{{ row.secondary || '—' }}</td>
            <td v-if="hasSO" class="p-3 font-mono text-slate-500">
              <span
                v-if="row.tertiary"
                class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700"
              >
                {{ row.tertiary }}
              </span>
              <span v-else>—</span>
            </td>
            <td class="p-3 pr-4 text-right">
              <div class="inline-flex items-center gap-1">
                <button
                  @click="openEdit(row)"
                  class="p-1.5 hover:bg-slate-800 rounded text-slate-400 hover:text-indigo-400 transition-colors"
                  title="Editar"
                >
                  <Pencil class="w-3.5 h-3.5" />
                </button>
                <button
                  @click="toDelete = row"
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
    </div>

    <!-- Modal de edição -->
    <div v-if="isModalOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div class="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl">
        <div class="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
          <h3 class="text-sm font-bold text-slate-100">
            {{ editingId ? 'Editar Registro' : 'Novo Registro' }} — {{ currentCategory.label }}
          </h3>
          <button @click="isModalOpen = false" class="text-slate-500 hover:text-slate-300">
            <X class="w-4 h-4" />
          </button>
        </div>

        <form @submit.prevent="handleSave" class="space-y-4 text-xs">
          <!-- Criticidade usa "nivel" -->
          <div v-if="hasNivel">
            <label class="block font-medium text-slate-300 mb-1">Nível *</label>
            <input
              v-model="form.nivel"
              type="text"
              required
              placeholder="ex: crítica"
              class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <!-- SO usa abreviação + descrição + lifecycle -->
          <template v-if="hasSO">
            <div>
              <label class="block font-medium text-slate-300 mb-1">Abreviação *</label>
              <input
                v-model="form.abreviacao"
                type="text"
                required
                placeholder="ex: RHEL9"
                class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label class="block font-medium text-slate-300 mb-1">Descrição *</label>
              <input
                v-model="form.descricao"
                type="text"
                required
                placeholder="ex: Red Hat Enterprise Linux 9"
                class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>
            <div>
              <label class="block font-medium text-slate-300 mb-1">Lifecycle</label>
              <input
                v-model="form.lifecycle"
                type="text"
                placeholder="ex: LTS, EOL, mainstream"
                class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500"
              />
            </div>
          </template>

          <!-- Demais categorias usam "nome" -->
          <div v-if="!hasNivel && !hasSO">
            <label class="block font-medium text-slate-300 mb-1">{{ primaryFieldLabel }} *</label>
            <input
              v-model="form.nome"
              type="text"
              required
              :placeholder="primaryFieldPlaceholder"
              class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div v-if="hasSigla">
            <label class="block font-medium text-slate-300 mb-1">Sigla *</label>
            <input
              v-model="form.sigla"
              type="text"
              required
              placeholder="ex: DTI, GSI"
              class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div v-if="activeCategory === 'tipos-relacionamento'">
            <label class="block font-medium text-slate-300 mb-1">Descrição</label>
            <textarea
              v-model="form.descricao"
              rows="2"
              placeholder="Semântica deste tipo de vínculo..."
              class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500"
            ></textarea>
          </div>

          <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              @click="isModalOpen = false"
              class="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              :disabled="isSaving"
              class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-slate-100 font-semibold transition-colors disabled:opacity-50"
            >
              <Loader2 v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
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
      title="Excluir registro"
      :message="`O registro '${toDelete.primary}' será removido da tabela auxiliar. Ativos que o referenciam podem ficar sem classificação.`"
      confirm-label="Excluir"
      danger
      @confirm="confirmDelete"
      @cancel="toDelete = null"
    />
  </div>
</template>