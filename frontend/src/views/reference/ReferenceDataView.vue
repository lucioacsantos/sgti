<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { 
  referenceDataService, 
  type ReferenceItem, 
  type ReferenceCategory 
} from '@/services/referenceData.service'
import { 
  Plus, 
  Search, 
  Pencil, 
  Trash2, 
  Loader2, 
  Database, 
  Check, 
  X, 
  AlertCircle 
} from 'lucide-vue-next'

const categories = [
  { key: 'asset-types' as ReferenceCategory, label: 'Tipos de Ativos' },
  { key: 'environments' as ReferenceCategory, label: 'Ambientes' },
  { key: 'locations' as ReferenceCategory, label: 'Localizações / Datacenters' },
  { key: 'operational-status' as ReferenceCategory, label: 'Status Operacional' },
  { key: 'manufacturers' as ReferenceCategory, label: 'Fabricantes' }
]

const activeCategory = ref<ReferenceCategory>('asset-types')
const items = ref<ReferenceItem[]>([])
const search = ref('')
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)

// Controle do Modal
const isModalOpen = ref(false)
const isSaving = ref(false)
const editingId = ref<number | null>(null)
const formData = ref<Partial<ReferenceItem>>({
  name: '',
  code: '',
  description: '',
  is_active: true
})

const filteredItems = computed(() => {
  if (!search.value) return items.value
  const term = search.value.toLowerCase()
  return items.value.filter(item => 
    item.name.toLowerCase().includes(term) || 
    (item.code && item.code.toLowerCase().includes(term)) ||
    (item.description && item.description.toLowerCase().includes(term))
  )
})

async function fetchItems() {
  isLoading.value = true
  errorMessage.value = null
  try {
    items.value = await referenceDataService.getAll(activeCategory.value)
  } catch (err: any) {
    errorMessage.value = 'Erro ao carregar dados da categoria selecionada.'
    items.value = []
  } finally {
    isLoading.value = false
  }
}

watch(activeCategory, () => {
  search.value = ''
  fetchItems()
})

function openCreateModal() {
  editingId.value = null
  formData.value = { name: '', code: '', description: '', is_active: true }
  isModalOpen.value = true
}

function openEditModal(item: ReferenceItem) {
  editingId.value = item.id || null
  formData.value = { ...item }
  isModalOpen.value = true
}

async function handleSave() {
  if (!formData.value.name) return
  isSaving.value = true
  try {
    if (editingId.value) {
      await referenceDataService.update(activeCategory.value, editingId.value, formData.value)
    } else {
      await referenceDataService.create(activeCategory.value, formData.value)
    }
    isModalOpen.value = false
    await fetchItems()
  } catch (err: any) {
    alert(err.response?.data?.detail || 'Erro ao persistir registro.')
  } finally {
    isSaving.value = false
  }
}

async function handleDelete(item: ReferenceItem) {
  if (!item.id) return
  if (!confirm(`Deseja remover "${item.name}"?`)) return

  try {
    await referenceDataService.delete(activeCategory.value, item.id)
    await fetchItems()
  } catch (err: any) {
    alert(err.response?.data?.detail || 'Não foi possível excluir o registro.')
  }
}

onMounted(() => {
  fetchItems()
})
</script>

<template>
  <div class="space-y-6">
    <!-- Cabeçalho -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 class="text-lg font-bold text-slate-100 flex items-center gap-2">
          <Database class="w-5 h-5 text-indigo-400" />
          Dados Mestres (Reference Data)
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">
          Parâmetros operacionais e categorias base para o inventário de TI.
        </p>
      </div>

      <button
        @click="openCreateModal"
        class="inline-flex items-center gap-2 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-semibold text-xs rounded-lg transition-colors shadow-sm"
      >
        <Plus class="w-4 h-4" />
        Novo Registro
      </button>
    </div>

    <!-- Navegação por Abas de Categoria -->
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

    <!-- Filtro de Busca -->
    <div class="flex items-center justify-between gap-4">
      <div class="relative w-full max-w-sm">
        <Search class="w-4 h-4 text-slate-500 absolute left-3 top-2.5 pointer-events-none" />
        <input
          v-model="search"
          type="text"
          placeholder="Filtrar por nome, código ou descrição..."
          class="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-indigo-500 transition-colors"
        />
      </div>
    </div>

    <!-- Feedback de Erro -->
    <div v-if="errorMessage" class="p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-center gap-2 text-rose-400 text-xs">
      <AlertCircle class="w-4 h-4 shrink-0" />
      <span>{{ errorMessage }}</span>
    </div>

    <!-- Tabela de Registros -->
    <div class="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
      <div v-if="isLoading" class="p-12 flex flex-col items-center justify-center text-slate-500">
        <Loader2 class="w-6 h-6 animate-spin mb-2 text-indigo-400" />
        <span class="text-xs">Consultando base de dados...</span>
      </div>

      <table v-else class="w-full text-left border-collapse text-xs">
        <thead>
          <tr class="border-b border-slate-800 bg-slate-900/50 text-slate-400 font-semibold uppercase tracking-wider">
            <th class="p-3 pl-4">Código / Tag</th>
            <th class="p-3">Nome</th>
            <th class="p-3">Descrição</th>
            <th class="p-3 text-center">Status</th>
            <th class="p-3 pr-4 text-right">Ações</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-slate-800/60 text-slate-300">
          <tr v-if="filteredItems.length === 0">
            <td colspan="5" class="p-8 text-center text-slate-500">
              Nenhum registro localizado para esta categoria.
            </td>
          </tr>
          <tr 
            v-for="item in filteredItems" 
            :key="item.id" 
            class="hover:bg-slate-900/40 transition-colors"
          >
            <td class="p-3 pl-4 font-mono text-slate-400">{{ item.code || '--' }}</td>
            <td class="p-3 font-medium text-slate-100">{{ item.name }}</td>
            <td class="p-3 text-slate-400 max-w-xs truncate">{{ item.description || '--' }}</td>
            <td class="p-3 text-center">
              <span 
                class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium"
                :class="item.is_active !== false ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-slate-800 text-slate-400'"
              >
                {{ item.is_active !== false ? 'Ativo' : 'Inativo' }}
              </span>
            </td>
            <td class="p-3 pr-4 text-right space-x-2">
              <button 
                @click="openEditModal(item)" 
                class="p-1.5 hover:bg-slate-800 rounded text-slate-400 hover:text-indigo-400 transition-colors"
                title="Editar"
              >
                <Pencil class="w-3.5 h-3.5" />
              </button>
              <button 
                @click="handleDelete(item)" 
                class="p-1.5 hover:bg-rose-500/10 rounded text-slate-400 hover:text-rose-400 transition-colors"
                title="Excluir"
              >
                <Trash2 class="w-3.5 h-3.5" />
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal Form (Criar / Editar) -->
    <div v-if="isModalOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div class="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl">
        <div class="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
          <h3 class="text-sm font-bold text-slate-100">
            {{ editingId ? 'Editar Registro' : 'Novo Registro' }}
          </h3>
          <button @click="isModalOpen = false" class="text-slate-500 hover:text-slate-300">
            <X class="w-4 h-4" />
          </button>
        </div>

        <form @submit.prevent="handleSave" class="space-y-4 text-xs">
          <div>
            <label class="block font-medium text-slate-300 mb-1">Nome *</label>
            <input
              v-model="formData.name"
              type="text"
              required
              placeholder="ex: Servidor Físico, Produção, Datacenter 01"
              class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label class="block font-medium text-slate-300 mb-1">Código / Mnemônico</label>
            <input
              v-model="formData.code"
              type="text"
              placeholder="ex: PRD, SRV-PHY, DC-SP"
              class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-indigo-500"
            />
          </div>

          <div>
            <label class="block font-medium text-slate-300 mb-1">Descrição</label>
            <textarea
              v-model="formData.description"
              rows="2"
              placeholder="Informações adicionais sobre este parâmetro..."
              class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-indigo-500"
            ></textarea>
          </div>

          <div class="flex items-center gap-2 pt-1">
            <input
              id="is_active"
              v-model="formData.is_active"
              type="checkbox"
              class="rounded bg-slate-950 border-slate-800 text-indigo-500 focus:ring-0 focus:ring-offset-0"
            />
            <label for="is_active" class="font-medium text-slate-300">Registro ativo</label>
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
  </div>
</template>