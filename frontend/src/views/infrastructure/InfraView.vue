<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  infraService, ipService, ativosService
} from '@/services/cmdb.services'
import type {
  Aplicacao, Cluster, Namespace, Servico, ServicoNegocio,
  InstanciaAplicacao, Relacionamento, EnderecoIp, Ativo
} from '@/services/cmdb'
import { useAuthStore } from '@/stores/auth'
import PaginationBar from '@/components/PaginationBar.vue'
import ErrorAlert from '@/components/ErrorAlert.vue'
import LoadingState from '@/components/LoadingState.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import {
  Network, Search, RefreshCw, Boxes, Layers, Cpu, Server, Globe, GitBranch, Package, AppWindow,
  Pencil, Trash2, Loader2
} from 'lucide-vue-next'

type TabKey = 'aplicacoes' | 'clusters' | 'namespaces' | 'servicos' | 'servicos-negocio' | 'instancias' | 'relacionamentos' | 'ips'

const tabs: { key: TabKey; label: string; icon: any }[] = [
  { key: 'aplicacoes', label: 'Aplicações', icon: AppWindow },
  { key: 'clusters', label: 'Clusters', icon: Boxes },
  { key: 'namespaces', label: 'Namespaces', icon: Layers },
  { key: 'servicos', label: 'Serviços', icon: Cpu },
  { key: 'servicos-negocio', label: 'Serviços de Negócio', icon: Server },
  { key: 'instancias', label: 'Instâncias', icon: Package },
  { key: 'relacionamentos', label: 'Relacionamentos', icon: GitBranch },
  { key: 'ips', label: 'Endereços IP', icon: Globe }
]

const activeTab = ref<TabKey>('aplicacoes')
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)
const successMessage = ref<string | null>(null)
const search = ref('')

// ===== Edição manual (perfil admin) =====
const authStore = useAuthStore()
const canAdmin = computed(() => authStore.isAdmin)

type EditField = { key: string; label: string; type?: 'text' | 'number' | 'select'; options?: { value: number | null; label: string }[]; required?: boolean; placeholder?: string }

type EditContext = {
  titulo: string
  endpoint: 'servico' | 'servico-negocio' | 'instancia' | 'relacionamento'
  item: any
  fields: EditField[]
}

const editando = ref<EditContext | null>(null)
const editForm = ref<Record<string, any>>({})
const isSaving = ref(false)
const paraExcluir = ref<{ endpoint: EditContext['endpoint']; item: any; label: string } | null>(null)
const isDeleting = ref(false)

// Dados por aba (listas sem paginação no backend, exceto IPs e relacionamentos)
const aplicacoes = ref<Aplicacao[]>([])
const clusters = ref<Cluster[]>([])
const namespaces = ref<Namespace[]>([])
const servicos = ref<Servico[]>([])
const servicosNegocio = ref<ServicoNegocio[]>([])
const instancias = ref<InstanciaAplicacao[]>([])
const relacionamentos = ref<Relacionamento[]>([])
const ips = ref<EnderecoIp[]>([])

// Paginação client-side para listas sem paginação server-side (aplicações, clusters...)
const displayPage = ref(1)
const clientPageSize = 25

// Relacionamentos e IPs paginados server-side
const relPage = ref(1)
const relHasMore = ref(false)
const relPageSize = 50

// IPs paginados server-side
const ipPage = ref(1)
const ipHasMore = ref(false)

// Mapas de nomes para exibição legível de FKs
const ativoNames = ref<Map<number, string>>(new Map())
const appNames = ref<Map<number, string>>(new Map())
const clusterNames = ref<Map<number, string>>(new Map())
const relTipoNames = ref<Map<number, string>>(new Map())

async function loadAtivosMap() {
  try {
    const ativos: Ativo[] = await ativosService.list(0, 100)
    ativoNames.value = new Map(ativos.map(a => [a.id, a.nome]))
    if (ativos.length >= 100) {
      // pagina em background até 2000 registros (suficiente para exibição)
      let skip = 100
      while (skip < 2000) {
        const page = await ativosService.list(skip, 100)
        for (const a of page) ativoNames.value.set(a.id, a.nome)
        if (page.length < 100) break
        skip += 100
      }
    }
  } catch {
    /* nomes ficam como IDs */
  }
}

async function loadAuxMaps() {
  try {
    const [apps, cls, tipos] = await Promise.all([
      infraService.aplicacoes(),
      infraService.clusters(),
      infraService.tiposRelacionamento()
    ])
    // apps retornam objeto sem id? schema AplicacaoResponse inclui id (PK)
    appNames.value = new Map((apps as any[]).map(a => [a.id, a.sistema]))
    clusterNames.value = new Map(cls.map(c => [c.id, c.nome]))
    relTipoNames.value = new Map(tipos.map(t => [t.id, t.nome]))
  } catch {
    /* nomes ficam como IDs */
  }
}

async function loadTab(tab: TabKey) {
  isLoading.value = true
  errorMessage.value = null
  search.value = ''
  displayPage.value = 1
  relPage.value = 1
  ipPage.value = 1

  try {
    switch (tab) {
      case 'aplicacoes':
        aplicacoes.value = await infraService.aplicacoes()
        break
      case 'clusters':
        clusters.value = await infraService.clusters()
        break
      case 'namespaces':
        namespaces.value = await infraService.namespaces()
        break
      case 'servicos':
        servicos.value = await infraService.servicos()
        break
      case 'servicos-negocio':
        servicosNegocio.value = await infraService.servicosNegocio()
        break
      case 'instancias':
        instancias.value = await infraService.instancias()
        break
      case 'relacionamentos':
        await loadRelPage()
        break
      case 'ips':
        await loadIpPage()
        break
    }
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    isLoading.value = false
  }
}

async function loadRelPage() {
  errorMessage.value = null
  try {
    const data = await infraService.relacionamentos({ skip: (relPage.value - 1) * relPageSize, limit: relPageSize })
    relacionamentos.value = data
    relHasMore.value = data.length >= relPageSize
  } catch (err) {
    errorMessage.value = String(err)
    relacionamentos.value = []
  }
}

async function loadIpPage() {
  errorMessage.value = null
  try {
    const data = await ipService.list(undefined, (ipPage.value - 1) * 50, 50)
    ips.value = data
    ipHasMore.value = data.length >= 50
  } catch (err) {
    errorMessage.value = String(err)
    ips.value = []
  }
}

watch(ipPage, loadIpPage)
watch(relPage, loadRelPage)
watch(activeTab, (tab) => loadTab(tab))

// Busca reseta a paginação client-side para a página 1
watch(search, () => {
  displayPage.value = 1
})

// Filtragem client-side da página atual
const filteredAplicacoes = computed(() => {
  const term = search.value.toLowerCase()
  if (!term) return aplicacoes.value
  return aplicacoes.value.filter(a =>
    a.sistema.toLowerCase().includes(term) ||
    (a.descricao || '').toLowerCase().includes(term) ||
    (a.area_negocio || '').toLowerCase().includes(term)
  )
})

function paginate<T>(list: T[]): T[] {
  const start = (displayPage.value - 1) * clientPageSize
  return list.slice(start, start + clientPageSize)
}

const hasMoreFiltered = computed(() => {
  const map: Record<string, number> = {
    aplicacoes: filteredAplicacoes.value.length,
    clusters: clusters.value.length,
    namespaces: namespaces.value.length,
    servicos: servicos.value.length,
    'servicos-negocio': servicosNegocio.value.length,
    instancias: instancias.value.length,
    relacionamentos: relacionamentos.value.length,
    ips: ips.value.length
  }
  const total = map[activeTab.value] ?? 0
  if (activeTab.value === 'ips') return ipHasMore.value
  if (activeTab.value === 'relacionamentos') return relHasMore.value
  return displayPage.value * clientPageSize < total
})

const pagedCount = computed(() => {
  if (activeTab.value === 'ips') return ips.value.length
  if (activeTab.value === 'relacionamentos') return relacionamentos.value.length
  if (activeTab.value === 'aplicacoes') return Math.min(paginate(filteredAplicacoes.value).length, clientPageSize)
  return Math.min(paginate(filteredCurrent.value).length, clientPageSize)
})

const currentList = computed<any[]>(() => {
  switch (activeTab.value) {
    case 'clusters': return clusters.value
    case 'namespaces': return namespaces.value
    case 'servicos': return servicos.value
    case 'servicos-negocio': return servicosNegocio.value
    case 'instancias': return instancias.value
    default: return []
  }
})

// v-model de página unificado (server-side p/ IPs e relacionamentos, client-side p/ demais)
const pageModel = computed({
  get: () => activeTab.value === 'ips' ? ipPage.value : activeTab.value === 'relacionamentos' ? relPage.value : displayPage.value,
  set: (v: number) => {
    if (activeTab.value === 'ips') ipPage.value = v
    else if (activeTab.value === 'relacionamentos') relPage.value = v
    else displayPage.value = v
  }
})

const filteredCurrent = computed(() => {
  const term = search.value.toLowerCase()
  const list = currentList.value
  if (!term) return list
  return list.filter((item: any) => {
    const nome = (item.nome || item.sistema || '').toLowerCase()
    return nome.includes(term) || (item.descricao || '').toLowerCase().includes(term)
  })
})

// IPs agora também filtram client-side
const filteredIps = computed(() => {
  const term = search.value.toLowerCase()
  if (!term) return ips.value
  return ips.value.filter((ip: EnderecoIp) =>
    ip.ip.includes(term) ||
    (ip.interface || '').toLowerCase().includes(term) ||
    (ip.descricao || '').toLowerCase().includes(term) ||
    ativoName(ip.ativo_id).toLowerCase().includes(term)
  )
})

function fmtDate(iso?: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function ativoName(id?: number | null): string {
  if (!id) return '—'
  return ativoNames.value.get(id) || `#${id}`
}

function appName(id?: number | null): string {
  if (!id) return '—'
  return appNames.value.get(id) || `#${id}`
}

function clusterName(id?: number | null): string {
  if (!id) return '—'
  return clusterNames.value.get(id) || `#${id}`
}

function relTipoName(id?: number | null): string {
  if (!id) return '—'
  return relTipoNames.value.get(id) || `tipo #${id}`
}

// ===== CRUD manual =====
const ativoOptions = computed(() => {
  const opts: { value: number | null; label: string }[] = [{ value: null, label: '— nenhum —' }]
  for (const [id, nome] of ativoNames.value) opts.push({ value: id, label: nome })
  return opts.sort((a, b) => String(a.label).localeCompare(String(b.label)))
})

const appOptions = computed(() => {
  const opts: { value: number | null; label: string }[] = [{ value: null, label: '— nenhuma —' }]
  for (const [id, nome] of appNames.value) opts.push({ value: id, label: nome })
  return opts.sort((a, b) => String(a.label).localeCompare(String(b.label)))
})

const relTipoOptions = computed(() => {
  const opts: { value: number | null; label: string }[] = [{ value: null, label: '— nenhum —' }]
  for (const [id, nome] of relTipoNames.value) opts.push({ value: id, label: nome })
  return opts
})

function openEdit(row: any) {
  errorMessage.value = null
  const tab = activeTab.value
  if (tab === 'servicos') {
    editando.value = {
      titulo: `Editar serviço: ${row.nome}`,
      endpoint: 'servico',
      item: row,
      fields: [
        { key: 'nome', label: 'Nome', required: true },
        { key: 'tipo', label: 'Tipo (ex.: database, integration, erp)' }
      ]
    }
  } else if (tab === 'servicos-negocio') {
    editando.value = {
      titulo: `Editar serviço de negócio: ${row.nome}`,
      endpoint: 'servico-negocio',
      item: row,
      fields: [
        { key: 'nome', label: 'Nome', required: true },
        { key: 'descricao', label: 'Descrição' }
      ]
    }
  } else if (tab === 'instancias') {
    editando.value = {
      titulo: `Editar instância de ${appName(row.aplicacao_id)}`,
      endpoint: 'instancia',
      item: row,
      fields: [
        { key: 'aplicacao_id', label: 'Aplicação', type: 'select', options: appOptions.value, required: true },
        { key: 'ativo_id', label: 'Ativo (Host)', type: 'select', options: ativoOptions.value },
        { key: 'porta', label: 'Porta', type: 'number' },
        { key: 'path_execucao', label: 'Path de execução' },
        { key: 'comando_execucao', label: 'Comando de execução' }
      ]
    }
  } else if (tab === 'relacionamentos') {
    editando.value = {
      titulo: `Editar relacionamento #${row.id}`,
      endpoint: 'relacionamento',
      item: row,
      fields: [
        { key: 'origem_id', label: 'Ativo de origem', type: 'select', options: ativoOptions.value, required: true },
        { key: 'destino_id', label: 'Ativo de destino', type: 'select', options: ativoOptions.value, required: true },
        { key: 'tipo_id', label: 'Tipo', type: 'select', options: relTipoOptions.value, required: true },
        { key: 'descricao', label: 'Descrição' }
      ]
    }
  } else {
    return
  }
  editForm.value = {
    nome: row.nome ?? '',
    tipo: row.tipo ?? '',
    descricao: row.descricao ?? '',
    aplicacao_id: row.aplicacao_id ?? null,
    ativo_id: row.ativo_id ?? null,
    porta: row.porta ?? null,
    path_execucao: row.path_execucao ?? '',
    comando_execucao: row.comando_execucao ?? '',
    origem_id: row.origem_id ?? null,
    destino_id: row.destino_id ?? null,
    tipo_id: row.tipo_id ?? null
  }
}

async function saveEdit() {
  if (!editando.value) return
  const { endpoint, item, fields } = editando.value
  for (const f of fields) {
    if (f.required && (editForm.value[f.key] === null || editForm.value[f.key] === undefined || editForm.value[f.key] === '')) {
      errorMessage.value = `Campo obrigatório: ${f.label}`
      return
    }
  }
  isSaving.value = true
  errorMessage.value = null
  try {
    if (endpoint === 'servico') {
      await infraService.updateServico(item.id, {
        nome: editForm.value.nome,
        tipo: editForm.value.tipo || null,
        ativo_id: item.ativo_id
      })
    } else if (endpoint === 'servico-negocio') {
      await infraService.updateServicoNegocio(item.id, {
        nome: editForm.value.nome,
        descricao: editForm.value.descricao || null,
        ativo_id: item.ativo_id
      })
    } else if (endpoint === 'instancia') {
      await infraService.updateInstancia(item.id, {
        aplicacao_id: Number(editForm.value.aplicacao_id),
        ativo_id: editForm.value.ativo_id ? Number(editForm.value.ativo_id) : null,
        porta: editForm.value.porta ? Number(editForm.value.porta) : null,
        path_execucao: editForm.value.path_execucao || null,
        comando_execucao: editForm.value.comando_execucao || null
      })
    } else {
      await infraService.updateRelacionamento(item.id, {
        origem_id: Number(editForm.value.origem_id),
        destino_id: Number(editForm.value.destino_id),
        tipo_id: Number(editForm.value.tipo_id),
        descricao: editForm.value.descricao || null
      })
    }
    successMessage.value = 'Registro atualizado.'
    editando.value = null
    await refreshCurrentTab()
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    isSaving.value = false
  }
}

function askDelete(row: any) {
  const tab = activeTab.value
  if (tab === 'servicos') paraExcluir.value = { endpoint: 'servico', item: row, label: `serviço ${row.nome}` }
  else if (tab === 'servicos-negocio') paraExcluir.value = { endpoint: 'servico-negocio', item: row, label: `serviço de negócio ${row.nome}` }
  else if (tab === 'instancias') paraExcluir.value = { endpoint: 'instancia', item: row, label: `instância de ${appName(row.aplicacao_id)}` }
  else if (tab === 'relacionamentos') paraExcluir.value = { endpoint: 'relacionamento', item: row, label: `relacionamento ${ativoName(row.origem_id)} → ${ativoName(row.destino_id)}` }
}

async function confirmDelete() {
  if (!paraExcluir.value) return
  const { endpoint, item } = paraExcluir.value
  isDeleting.value = true
  errorMessage.value = null
  try {
    if (endpoint === 'servico') await infraService.deleteServico(item.id)
    else if (endpoint === 'servico-negocio') await infraService.deleteServicoNegocio(item.id)
    else if (endpoint === 'instancia') await infraService.deleteInstancia(item.id)
    else await infraService.deleteRelacionamento(item.id)
    successMessage.value = 'Registro excluído.'
    paraExcluir.value = null
    await refreshCurrentTab()
  } catch (err) {
    errorMessage.value = String(err)
    paraExcluir.value = null
  } finally {
    isDeleting.value = false
  }
}

async function refreshCurrentTab() {
  if (activeTab.value === 'relacionamentos') {
    relPage.value = 1
    await loadRelPage()
  } else if (activeTab.value === 'ips') {
    await loadIpPage()
  } else {
    await loadTab(activeTab.value)
  }
  // recarrega mapas (nomes de apps/ativos podem mudar de id)
  await loadAuxMaps()
}

onMounted(async () => {
  await Promise.all([loadTab('aplicacoes'), loadAtivosMap(), loadAuxMaps()])
})
</script>

<template>
  <div class="space-y-6">
    <!-- Cabeçalho -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 class="text-lg font-bold text-slate-100 flex items-center gap-2">
          <Network class="w-5 h-5 text-sky-400" />
          Infraestrutura & Mapa de TI
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">
          Aplicações, clusters, namespaces, serviços e endereçamento — provisionados por automações, consulta somente leitura.
        </p>
      </div>

      <button
        @click="loadTab(activeTab)"
        :disabled="isLoading"
        class="inline-flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs rounded-lg transition-colors disabled:opacity-50"
      >
        <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
        Atualizar
      </button>
    </div>

    <ErrorAlert :error="errorMessage" />

    <div
      v-if="successMessage"
      class="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg text-xs text-emerald-400"
    >
      {{ successMessage }}
    </div>

    <!-- Abas -->
    <div class="flex border-b border-slate-800 overflow-x-auto">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        @click="activeTab = tab.key"
        class="px-4 py-3 text-xs font-semibold whitespace-nowrap border-b-2 transition-colors flex items-center gap-2"
        :class="activeTab === tab.key
          ? 'border-sky-500 text-sky-400 bg-slate-950/40'
          : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'"
      >
        <component :is="tab.icon" class="w-3.5 h-3.5" />
        {{ tab.label }}
      </button>
    </div>

    <!-- Busca -->
    <div class="relative w-full max-w-sm">
      <Search class="w-4 h-4 text-slate-500 absolute left-3 top-2.5 pointer-events-none" />
      <input
        v-model="search"
        type="text"
        placeholder="Filtrar registros exibidos..."
        class="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500 transition-colors"
      />
    </div>

    <!-- Conteúdo -->
    <div class="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
      <LoadingState v-if="isLoading" />

      <template v-else>
        <!-- APLICAÇÕES -->
        <table v-if="activeTab === 'aplicacoes'" class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-900/50 text-slate-400 font-semibold uppercase tracking-wider">
              <th class="p-3 pl-4">Sistema</th>
              <th class="p-3">Descrição</th>
              <th class="p-3">Área de Negócio</th>
              <th class="p-3">Linguagens</th>
              <th class="p-3 pr-4">Registrado em</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="filteredAplicacoes.length === 0">
              <td colspan="5" class="p-8 text-center text-slate-500">Nenhuma aplicação registrada.</td>
            </tr>
            <tr v-for="app in paginate(filteredAplicacoes)" :key="app.sistema" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4 font-medium text-slate-100 font-mono">{{ app.sistema }}</td>
              <td class="p-3 text-slate-400 max-w-xs truncate">{{ app.descricao || '—' }}</td>
              <td class="p-3 text-slate-400">{{ app.area_negocio || '—' }}</td>
              <td class="p-3 font-mono text-slate-500">{{ app.linguagens || '—' }}</td>
              <td class="p-3 pr-4 text-slate-500 font-mono">{{ fmtDate(app.created_at) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- CLUSTERS -->
        <table v-else-if="activeTab === 'clusters'" class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-900/50 text-slate-400 font-semibold uppercase tracking-wider">
              <th class="p-3 pl-4">ID</th>
              <th class="p-3">Nome</th>
              <th class="p-3">Descrição</th>
              <th class="p-3 pr-4">Ativo Associado</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="filteredCurrent.length === 0">
              <td colspan="4" class="p-8 text-center text-slate-500">Nenhum cluster registrado.</td>
            </tr>
            <tr v-for="c in paginate(filteredCurrent)" :key="c.id" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4 font-mono text-slate-500">{{ c.id }}</td>
              <td class="p-3 font-medium text-slate-100 font-mono">{{ c.nome }}</td>
              <td class="p-3 text-slate-400 max-w-sm truncate">{{ c.descricao || '—' }}</td>
              <td class="p-3 pr-4 text-slate-400">{{ ativoName(c.ativo_id) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- NAMESPACES -->
        <table v-else-if="activeTab === 'namespaces'" class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-900/50 text-slate-400 font-semibold uppercase tracking-wider">
              <th class="p-3 pl-4">ID</th>
              <th class="p-3">Nome</th>
              <th class="p-3">Cluster</th>
              <th class="p-3 pr-4">Ativo Associado</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="filteredCurrent.length === 0">
              <td colspan="4" class="p-8 text-center text-slate-500">Nenhum namespace registrado.</td>
            </tr>
            <tr v-for="n in paginate(filteredCurrent)" :key="n.id" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4 font-mono text-slate-500">{{ n.id }}</td>
              <td class="p-3 font-medium text-slate-100 font-mono">{{ n.nome }}</td>
              <td class="p-3 text-slate-400">{{ clusterName(n.cluster_id) }}</td>
              <td class="p-3 pr-4 text-slate-400">{{ ativoName(n.ativo_id) }}</td>
            </tr>
          </tbody>
        </table>

        <!-- SERVIÇOS -->
        <table v-else-if="activeTab === 'servicos'" class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-900/50 text-slate-400 font-semibold uppercase tracking-wider">
              <th class="p-3 pl-4">ID</th>
              <th class="p-3">Nome</th>
              <th class="p-3">Tipo</th>
              <th class="p-3">Ativo Associado</th>
              <th class="p-3 pr-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="filteredCurrent.length === 0">
              <td colspan="5" class="p-8 text-center text-slate-500">Nenhum serviço registrado.</td>
            </tr>
            <tr v-for="s in paginate(filteredCurrent)" :key="s.id" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4 font-mono text-slate-500">{{ s.id }}</td>
              <td class="p-3 font-medium text-slate-100 font-mono">{{ s.nome }}</td>
              <td class="p-3 text-slate-400">{{ s.tipo || '—' }}</td>
              <td class="p-3 text-slate-400">{{ ativoName(s.ativo_id) }}</td>
              <td v-if="canAdmin" class="p-3 pr-4 text-right">
                <div class="inline-flex gap-1">
                  <button @click="openEdit(s)" class="p-1.5 rounded text-slate-400 hover:text-sky-400 hover:bg-sky-500/10 transition-colors" title="Editar">
                    <Pencil class="w-3.5 h-3.5" />
                  </button>
                  <button @click="askDelete(s)" class="p-1.5 rounded text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors" title="Excluir">
                    <Trash2 class="w-3.5 h-3.5" />
                  </button>
                </div>
              </td>
              <td v-else class="p-3 pr-4"></td>
            </tr>
          </tbody>
        </table>

        <!-- SERVIÇOS DE NEGÓCIO -->
        <table v-else-if="activeTab === 'servicos-negocio'" class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-900/50 text-slate-400 font-semibold uppercase tracking-wider">
              <th class="p-3 pl-4">ID</th>
              <th class="p-3">Nome</th>
              <th class="p-3">Descrição</th>
              <th class="p-3">Ativo Associado</th>
              <th class="p-3 pr-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="filteredCurrent.length === 0">
              <td colspan="5" class="p-8 text-center text-slate-500">Nenhum serviço de negócio registrado.</td>
            </tr>
            <tr v-for="s in paginate(filteredCurrent)" :key="s.id" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4 font-mono text-slate-500">{{ s.id }}</td>
              <td class="p-3 font-medium text-slate-100 font-mono">{{ s.nome }}</td>
              <td class="p-3 text-slate-400 max-w-xs truncate">{{ s.descricao || '—' }}</td>
              <td class="p-3 text-slate-400">{{ ativoName(s.ativo_id) }}</td>
              <td v-if="canAdmin" class="p-3 pr-4 text-right">
                <div class="inline-flex gap-1">
                  <button @click="openEdit(s)" class="p-1.5 rounded text-slate-400 hover:text-sky-400 hover:bg-sky-500/10 transition-colors" title="Editar">
                    <Pencil class="w-3.5 h-3.5" />
                  </button>
                  <button @click="askDelete(s)" class="p-1.5 rounded text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors" title="Excluir">
                    <Trash2 class="w-3.5 h-3.5" />
                  </button>
                </div>
              </td>
              <td v-else class="p-3 pr-4"></td>
            </tr>
          </tbody>
        </table>

        <!-- INSTÂNCIAS -->
        <table v-else-if="activeTab === 'instancias'" class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-900/50 text-slate-400 font-semibold uppercase tracking-wider">
              <th class="p-3 pl-4">ID</th>
              <th class="p-3">Aplicação</th>
              <th class="p-3">Ativo (Host)</th>
              <th class="p-3">Porta</th>
              <th class="p-3">Path</th>
              <th class="p-3">Comando</th>
              <th class="p-3 pr-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="filteredCurrent.length === 0">
              <td colspan="7" class="p-8 text-center text-slate-500">Nenhuma instância registrada.</td>
            </tr>
            <tr v-for="i in paginate(filteredCurrent)" :key="i.id" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4 font-mono text-slate-500">{{ i.id }}</td>
              <td class="p-3 font-medium text-slate-100 font-mono">{{ appName(i.aplicacao_id) }}</td>
              <td class="p-3 text-slate-400">{{ ativoName(i.ativo_id) }}</td>
              <td class="p-3 font-mono text-slate-400">{{ i.porta || '—' }}</td>
              <td class="p-3 font-mono text-slate-500 max-w-xs truncate" :title="i.path_execucao || ''">{{ i.path_execucao || '—' }}</td>
              <td class="p-3 font-mono text-slate-500 max-w-xs truncate" :title="i.comando_execucao || ''">{{ i.comando_execucao || '—' }}</td>
              <td v-if="canAdmin" class="p-3 pr-4 text-right">
                <div class="inline-flex gap-1">
                  <button @click="openEdit(i)" class="p-1.5 rounded text-slate-400 hover:text-sky-400 hover:bg-sky-500/10 transition-colors" title="Editar">
                    <Pencil class="w-3.5 h-3.5" />
                  </button>
                  <button @click="askDelete(i)" class="p-1.5 rounded text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors" title="Excluir">
                    <Trash2 class="w-3.5 h-3.5" />
                  </button>
                </div>
              </td>
              <td v-else class="p-3 pr-4"></td>
            </tr>
          </tbody>
        </table>

        <!-- RELACIONAMENTOS -->
        <table v-else-if="activeTab === 'relacionamentos'" class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-900/50 text-slate-400 font-semibold uppercase tracking-wider">
              <th class="p-3 pl-4">ID</th>
              <th class="p-3">Origem</th>
              <th class="p-3">Destino</th>
              <th class="p-3">Tipo</th>
              <th class="p-3">Criado em</th>
              <th class="p-3 pr-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="relacionamentos.length === 0">
              <td colspan="6" class="p-8 text-center text-slate-500">Nenhum relacionamento registrado.</td>
            </tr>
            <tr v-for="r in relacionamentos" :key="r.id" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4 font-mono text-slate-500">{{ r.id }}</td>
              <td class="p-3 text-slate-200">{{ ativoName(r.origem_id) }}</td>
              <td class="p-3 text-slate-200">
                <span class="text-slate-600 mx-1">→</span>
                {{ ativoName(r.destino_id) }}
              </td>
              <td class="p-3 font-mono text-slate-400">
                {{ relTipoName(r.tipo_id) }}
                <span v-if="r.descricao" class="block text-[10px] text-slate-500 max-w-xs truncate" :title="r.descricao">{{ r.descricao }}</span>
              </td>
              <td class="p-3 text-slate-500 font-mono">{{ fmtDate(r.created_at) }}</td>
              <td v-if="canAdmin" class="p-3 pr-4 text-right">
                <div class="inline-flex gap-1">
                  <button @click="openEdit(r)" class="p-1.5 rounded text-slate-400 hover:text-sky-400 hover:bg-sky-500/10 transition-colors" title="Editar">
                    <Pencil class="w-3.5 h-3.5" />
                  </button>
                  <button @click="askDelete(r)" class="p-1.5 rounded text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors" title="Excluir">
                    <Trash2 class="w-3.5 h-3.5" />
                  </button>
                </div>
              </td>
              <td v-else class="p-3 pr-4"></td>
            </tr>
          </tbody>
        </table>

        <!-- IPs -->
        <table v-else-if="activeTab === 'ips'" class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b border-slate-800 bg-slate-900/50 text-slate-400 font-semibold uppercase tracking-wider">
              <th class="p-3 pl-4">Endereço</th>
              <th class="p-3">Tipo</th>
              <th class="p-3">Interface</th>
              <th class="p-3">Ativo</th>
              <th class="p-3 text-center">Primário</th>
              <th class="p-3 pr-4">Criado em</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="filteredIps.length === 0">
              <td colspan="6" class="p-8 text-center text-slate-500">Nenhum endereço IP registrado.</td>
            </tr>
            <tr v-for="ip in filteredIps" :key="ip.id" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4 font-mono text-sky-300">{{ ip.ip }}</td>
              <td class="p-3 font-mono text-slate-400">{{ ip.tipo || '—' }}</td>
              <td class="p-3 font-mono text-slate-400">{{ ip.interface || '—' }}</td>
              <td class="p-3 text-slate-300">{{ ativoName(ip.ativo_id) }}</td>
              <td class="p-3 text-center">
                <span
                  v-if="ip.primario"
                  class="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
                >
                  sim
                </span>
                <span v-else class="text-slate-600 text-[10px]">—</span>
              </td>
              <td class="p-3 pr-4 text-slate-500 font-mono">{{ fmtDate(ip.created_at) }}</td>
            </tr>
          </tbody>
        </table>

        <PaginationBar
          v-model:page="pageModel"
          :page-size="activeTab === 'ips' ? 50 : clientPageSize"
          :has-more="hasMoreFiltered"
          :count="pagedCount"
          :disabled="isLoading"
        />
      </template>
    </div>

    <!-- Modal: edição manual (admin) -->
    <div v-if="editando" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div class="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl max-h-[90vh] overflow-y-auto">
        <h3 class="text-sm font-bold text-slate-100">{{ editando.titulo }}</h3>
        <p class="text-[10px] text-slate-500 mt-1">Correção manual — a ação é registrada na auditoria.</p>

        <form @submit.prevent="saveEdit" class="space-y-3 mt-4 text-xs">
          <div v-for="f in editando.fields" :key="f.key">
            <label class="block font-medium text-slate-300 mb-1">
              {{ f.label }}<span v-if="f.required" class="text-rose-400"> *</span>
            </label>
            <select
              v-if="f.type === 'select'"
              v-model="editForm[f.key]"
              class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-sky-500"
            >
              <option v-for="opt in f.options" :key="String(opt.value)" :value="opt.value ?? undefined">{{ opt.label }}</option>
            </select>
            <input
              v-else
              v-model="editForm[f.key]"
              :type="f.type === 'number' ? 'number' : 'text'"
              class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-sky-500"
            />
          </div>

          <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              @click="editando = null"
              class="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              :disabled="isSaving"
              class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-sky-600 hover:bg-sky-500 text-white font-semibold transition-colors disabled:opacity-50"
            >
              <Loader2 v-if="isSaving" class="w-3.5 h-3.5 animate-spin" />
              Salvar
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Confirmação: exclusão manual (admin) -->
    <ConfirmDialog
      v-if="paraExcluir"
      title="Excluir registro"
      :message="`O item '${paraExcluir.label}' será excluído permanentemente do CMDB. A ação é registrada na auditoria e não pode ser desfeita.`"
      confirm-label="Excluir"
      danger
      @confirm="confirmDelete"
      @cancel="paraExcluir = null"
    />
  </div>
</template>