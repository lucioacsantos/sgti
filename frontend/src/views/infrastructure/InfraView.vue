<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import {
  infraService, ipService, ativosService
} from '@/services/cmdb.services'
import type {
  Aplicacao, Cluster, Namespace, Servico, ServicoNegocio,
  InstanciaAplicacao, Relacionamento, EnderecoIp, Ativo
} from '@/services/cmdb'
import PaginationBar from '@/components/PaginationBar.vue'
import ErrorAlert from '@/components/ErrorAlert.vue'
import LoadingState from '@/components/LoadingState.vue'
import {
  Network, Search, RefreshCw, Boxes, Layers, Cpu, Server, Globe, GitBranch, Package, AppWindow
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
const search = ref('')

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

// IPs paginados server-side
const ipPage = ref(1)
const ipHasMore = ref(false)

// Mapa de ativos para exibir nomes
const ativoNames = ref<Map<number, string>>(new Map())

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

async function loadTab(tab: TabKey) {
  isLoading.value = true
  errorMessage.value = null
  search.value = ''
  displayPage.value = 1

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
        relacionamentos.value = await infraService.relacionamentos({ skip: 0, limit: 100 })
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
watch(activeTab, (tab) => loadTab(tab))

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
  return displayPage.value * clientPageSize < total
})

const pagedCount = computed(() => {
  if (activeTab.value === 'ips') return ips.value.length
  if (activeTab.value === 'aplicacoes') return Math.min(paginate(filteredAplicacoes.value).length, clientPageSize)
  return Math.min(paginate(currentList.value).length, clientPageSize)
})

const currentList = computed<any[]>(() => {
  switch (activeTab.value) {
    case 'clusters': return clusters.value
    case 'namespaces': return namespaces.value
    case 'servicos': return servicos.value
    case 'servicos-negocio': return servicosNegocio.value
    case 'instancias': return instancias.value
    case 'relacionamentos': return relacionamentos.value
    default: return []
  }
})

// v-model de página unificado (server-side p/ IPs, client-side p/ demais)
const pageModel = computed({
  get: () => activeTab.value === 'ips' ? ipPage.value : displayPage.value,
  set: (v: number) => {
    if (activeTab.value === 'ips') ipPage.value = v
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

function fmtDate(iso?: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

function ativoName(id?: number | null): string {
  if (!id) return '—'
  return ativoNames.value.get(id) || `#${id}`
}

onMounted(async () => {
  await Promise.all([loadTab('aplicacoes'), loadAtivosMap()])
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
              <td class="p-3 text-slate-400">{{ n.cluster_id ? `#${n.cluster_id}` : '—' }}</td>
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
              <th class="p-3 pr-4">Ativo Associado</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="filteredCurrent.length === 0">
              <td colspan="4" class="p-8 text-center text-slate-500">Nenhum serviço registrado.</td>
            </tr>
            <tr v-for="s in paginate(filteredCurrent)" :key="s.id" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4 font-mono text-slate-500">{{ s.id }}</td>
              <td class="p-3 font-medium text-slate-100 font-mono">{{ s.nome }}</td>
              <td class="p-3 text-slate-400">{{ s.tipo || '—' }}</td>
              <td class="p-3 pr-4 text-slate-400">{{ ativoName(s.ativo_id) }}</td>
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
              <th class="p-3 pr-4">Ativo Associado</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="filteredCurrent.length === 0">
              <td colspan="4" class="p-8 text-center text-slate-500">Nenhum serviço de negócio registrado.</td>
            </tr>
            <tr v-for="s in paginate(filteredCurrent)" :key="s.id" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4 font-mono text-slate-500">{{ s.id }}</td>
              <td class="p-3 font-medium text-slate-100 font-mono">{{ s.nome }}</td>
              <td class="p-3 text-slate-400 max-w-xs truncate">{{ s.descricao || '—' }}</td>
              <td class="p-3 pr-4 text-slate-400">{{ ativoName(s.ativo_id) }}</td>
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
              <th class="p-3 pr-4">Comando</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="filteredCurrent.length === 0">
              <td colspan="5" class="p-8 text-center text-slate-500">Nenhuma instância registrada.</td>
            </tr>
            <tr v-for="i in paginate(filteredCurrent)" :key="i.id" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4 font-mono text-slate-500">{{ i.id }}</td>
              <td class="p-3 font-mono text-slate-200">{{ i.aplicacao_id }}</td>
              <td class="p-3 text-slate-400">{{ ativoName(i.ativo_id) }}</td>
              <td class="p-3 font-mono text-slate-400">{{ i.porta || '—' }}</td>
              <td class="p-3 pr-4 font-mono text-slate-500 max-w-xs truncate">{{ i.comando_execucao || '—' }}</td>
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
              <th class="p-3 pr-4">Criado em</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="filteredCurrent.length === 0">
              <td colspan="5" class="p-8 text-center text-slate-500">Nenhum relacionamento registrado.</td>
            </tr>
            <tr v-for="r in paginate(filteredCurrent)" :key="r.id" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4 font-mono text-slate-500">{{ r.id }}</td>
              <td class="p-3 text-slate-200">{{ ativoName(r.origem_id) }}</td>
              <td class="p-3 text-slate-200">
                <span class="text-slate-600 mx-1">→</span>
                {{ ativoName(r.destino_id) }}
              </td>
              <td class="p-3 font-mono text-slate-400">tipo #{{ r.tipo_id }}</td>
              <td class="p-3 pr-4 text-slate-500 font-mono">{{ fmtDate(r.created_at) }}</td>
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
            <tr v-if="ips.length === 0">
              <td colspan="6" class="p-8 text-center text-slate-500">Nenhum endereço IP registrado.</td>
            </tr>
            <tr v-for="ip in ips" :key="ip.id" class="hover:bg-slate-900/40 transition-colors">
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
  </div>
</template>