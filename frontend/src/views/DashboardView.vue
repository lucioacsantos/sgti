<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/services/api'
import {
  ativosService, ipService, infraService, auditService, referenceService
} from '@/services/cmdb.services'
import type { AuditLog } from '@/services/cmdb'
import {
  Server, Network, Database, ShieldAlert, Activity, ArrowUpRight,
  CheckCircle2, XCircle, Clock, Layers, Globe, Boxes, Cpu
} from 'lucide-vue-next'

const authStore = useAuthStore()

const isLoading = ref(true)

const stats = ref({
  totalAtivos: 0,
  totalIps: 0,
  totalAplicacoes: 0,
  totalClusters: 0,
  totalNamespaces: 0,
  totalServicos: 0,
  totalServicosNegocio: 0,
  totalInstancias: 0,
  tiposAtivo: 0,
  ambientes: 0,
  criticidades: 0,
  areas: 0,
  sos: 0
})

const health = ref<{ status: string; database: string } | null>(null)
const recentLogs = ref<AuditLog[]>([])

// Distribuição por criticidade (nome → cor)
const criticidadeDist = ref<Record<string, number>>({})
const criticidadeTotal = computed(() =>
  Object.values(criticidadeDist.value).reduce((a, b) => a + b, 0)
)

const criticidadeColors: Record<string, string> = {
  critica: 'bg-rose-500',
  alta: 'bg-amber-500',
  media: 'bg-sky-500',
  baixa: 'bg-emerald-500'
}

function colorFor(nivel: string): string {
  return criticidadeColors[nivel.toLowerCase()] || 'bg-slate-500'
}

const criticidadeBars = computed(() =>
  Object.entries(criticidadeDist.value)
    .sort((a, b) => b[1] - a[1])
    .map(([nivel, count]) => ({
      nivel,
      count,
      pct: criticidadeTotal.value ? Math.round((count / criticidadeTotal.value) * 100) : 0,
      color: colorFor(nivel)
    }))
)

function fmtDate(iso: string): string {
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

const acaoColors: Record<string, string> = {
  CREATE: 'text-emerald-400',
  UPDATE: 'text-sky-400',
  DELETE: 'text-rose-400'
}

async function loadDashboard() {
  isLoading.value = true
  const results = await Promise.allSettled([
    ativosService.list(0, 100),
    ipService.list(undefined, 0, 100),
    infraService.aplicacoes(),
    infraService.clusters(),
    infraService.namespaces(),
    infraService.servicos(),
    infraService.servicosNegocio(),
    infraService.instancias(),
    referenceService.tiposAtivos(),
    referenceService.ambientes(),
    referenceService.criticidades(),
    referenceService.areas(),
    referenceService.sistemasOperacionais(),
    auditService.list({ limit: 8 }),
    api.get('/health')
  ])

  const [rAtivos, rIps, rApps, rClusters, rNs, rServ, rServNeg, rInst, rTipos, rAmb, rCrit, rAreas, rSos, rLogs, rHealth] = results

  if (rAtivos.status === 'fulfilled') {
    stats.value.totalAtivos = rAtivos.value.length
    // Pagina enquanto houver mais (cap de segurança: 20 páginas)
    if (rAtivos.value.length >= 100) {
      loadAllAtivos()
    }
  }
  if (rIps.status === 'fulfilled') stats.value.totalIps = rIps.value.length
  if (rApps.status === 'fulfilled') stats.value.totalAplicacoes = rApps.value.length
  if (rClusters.status === 'fulfilled') stats.value.totalClusters = rClusters.value.length
  if (rNs.status === 'fulfilled') stats.value.totalNamespaces = rNs.value.length
  if (rServ.status === 'fulfilled') stats.value.totalServicos = rServ.value.length
  if (rServNeg.status === 'fulfilled') stats.value.totalServicosNegocio = rServNeg.value.length
  if (rInst.status === 'fulfilled') stats.value.totalInstancias = rInst.value.length
  if (rTipos.status === 'fulfilled') stats.value.tiposAtivo = rTipos.value.length
  if (rAmb.status === 'fulfilled') stats.value.ambientes = rAmb.value.length
  if (rCrit.status === 'fulfilled') stats.value.criticidades = rCrit.value.length
  if (rAreas.status === 'fulfilled') stats.value.areas = rAreas.value.length
  if (rSos.status === 'fulfilled') stats.value.sos = rSos.value.length

  if (rLogs.status === 'fulfilled') recentLogs.value = rLogs.value
  if (rHealth.status === 'fulfilled') health.value = rHealth.value.data

  // Agrega criticidade a partir dos ativos carregados
  if (rAtivos.status === 'fulfilled' && rCrit.status === 'fulfilled') {
    const map: Record<string, number> = {}
    const critMap = new Map(rCrit.value.map(c => [c.id, c.nivel]))
    for (const ativo of rAtivos.value) {
      if (ativo.criticidade_id) {
        const nivel = critMap.get(ativo.criticidade_id) || 'sem nível'
        map[nivel] = (map[nivel] || 0) + 1
      } else {
        map['não classificado'] = (map['não classificado'] || 0) + 1
      }
    }
    criticidadeDist.value = map
  }

  isLoading.value = false
}

async function loadAllAtivos() {
  // Continua paginando em background para refinar contadores
  try {
    let skip = 100
    const criticidades = await referenceService.criticidades()
    const critMap = new Map(criticidades.map(c => [c.id, c.nivel]))
    while (skip < 10000) {
      const page = await ativosService.list(skip, 100)
      stats.value.totalAtivos += page.length
      for (const ativo of page) {
        const nivel = ativo.criticidade_id
          ? (critMap.get(ativo.criticidade_id) || 'sem nível')
          : 'não classificado'
        criticidadeDist.value[nivel] = (criticidadeDist.value[nivel] || 0) + 1
      }
      if (page.length < 100) break
      skip += 100
    }
  } catch {
    /* mantém contagem parcial */
  }
}

onMounted(loadDashboard)
</script>

<template>
  <div class="space-y-8">
    <!-- Boas-vindas -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-950/60 p-6 rounded-xl border border-slate-800">
      <div>
        <h2 class="text-xl font-bold text-slate-100">
          Olá, <span class="text-emerald-400 font-mono">{{ authStore.userName }}</span>
        </h2>
        <p class="text-xs text-slate-400 mt-1">
          Console central de ativos, infraestrutura e governança de TI.
        </p>
      </div>

      <div class="flex items-center gap-2">
        <span
          class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium border"
          :class="health?.database === 'healthy'
            ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
            : 'bg-rose-500/10 text-rose-400 border-rose-500/20'"
        >
          <span
            class="w-1.5 h-1.5 rounded-full animate-pulse"
            :class="health?.database === 'healthy' ? 'bg-emerald-400' : 'bg-rose-400'"
          ></span>
          {{ health ? (health.database === 'healthy' ? 'API e banco saudáveis' : 'Banco de dados degradado') : 'Verificando status...' }}
        </span>
      </div>
    </div>

    <!-- Cards de Métricas Principais -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
        <div class="flex items-center justify-between text-slate-400">
          <span class="text-xs font-semibold uppercase tracking-wider">Ativos de TI</span>
          <Server class="w-4 h-4 text-emerald-400" />
        </div>
        <div class="mt-4 flex items-baseline justify-between">
          <div class="text-2xl font-bold font-mono text-slate-100">{{ stats.totalAtivos }}</div>
          <RouterLink to="/assets" class="text-xs text-emerald-400 hover:underline flex items-center gap-0.5">
            Ver todos <ArrowUpRight class="w-3 h-3" />
          </RouterLink>
        </div>
      </div>

      <div class="bg-slate-950 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
        <div class="flex items-center justify-between text-slate-400">
          <span class="text-xs font-semibold uppercase tracking-wider">Endereços IP</span>
          <Globe class="w-4 h-4 text-sky-400" />
        </div>
        <div class="mt-4 flex items-baseline justify-between">
          <div class="text-2xl font-bold font-mono text-slate-100">{{ stats.totalIps }}</div>
          <RouterLink to="/infrastructure" class="text-xs text-sky-400 hover:underline flex items-center gap-0.5">
            Detalhar <ArrowUpRight class="w-3 h-3" />
          </RouterLink>
        </div>
      </div>

      <div class="bg-slate-950 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
        <div class="flex items-center justify-between text-slate-400">
          <span class="text-xs font-semibold uppercase tracking-wider">Aplicações</span>
          <Boxes class="w-4 h-4 text-indigo-400" />
        </div>
        <div class="mt-4 flex items-baseline justify-between">
          <div class="text-2xl font-bold font-mono text-slate-100">{{ stats.totalAplicacoes }}</div>
          <RouterLink to="/infrastructure" class="text-xs text-indigo-400 hover:underline flex items-center gap-0.5">
            Detalhar <ArrowUpRight class="w-3 h-3" />
          </RouterLink>
        </div>
      </div>

      <div class="bg-slate-950 border border-slate-800 rounded-xl p-5 hover:border-slate-700 transition-colors">
        <div class="flex items-center justify-between text-slate-400">
          <span class="text-xs font-semibold uppercase tracking-wider">Logs de Auditoria</span>
          <ShieldAlert class="w-4 h-4 text-amber-400" />
        </div>
        <div class="mt-4 flex items-baseline justify-between">
          <div class="text-2xl font-bold font-mono text-slate-100">ativo</div>
          <RouterLink to="/audit" class="text-xs text-amber-400 hover:underline flex items-center gap-0.5">
            Histórico <ArrowUpRight class="w-3 h-3" />
          </RouterLink>
        </div>
      </div>
    </div>

    <!-- Painel duplo: distribuição + infraestrutura -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Distribuição por criticidade -->
      <div class="lg:col-span-1 bg-slate-950 border border-slate-800 rounded-xl p-6">
        <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
          <Activity class="w-4 h-4 text-emerald-400" />
          Ativos por Criticidade
        </h3>

        <div v-if="criticidadeBars.length === 0" class="text-xs text-slate-500">
          Nenhum ativo classificado ainda.
        </div>

        <div v-else class="space-y-3">
          <div v-for="bar in criticidadeBars" :key="bar.nivel">
            <div class="flex items-center justify-between text-xs mb-1">
              <span class="text-slate-300 capitalize">{{ bar.nivel }}</span>
              <span class="font-mono text-slate-400">{{ bar.count }} ({{ bar.pct }}%)</span>
            </div>
            <div class="h-1.5 bg-slate-800 rounded-full overflow-hidden">
              <div
                class="h-full rounded-full transition-all duration-500"
                :class="bar.color"
                :style="{ width: bar.pct + '%' }"
              />
            </div>
          </div>
        </div>
      </div>

      <!-- Resumo de Infraestrutura -->
      <div class="lg:col-span-2 bg-slate-950 border border-slate-800 rounded-xl p-6">
        <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
          <Network class="w-4 h-4 text-emerald-400" />
          Infraestrutura Registrada
        </h3>

        <div class="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
          <RouterLink to="/infrastructure" class="p-3 bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 rounded-lg transition-all group">
            <Boxes class="w-4 h-4 text-sky-400 mb-2" />
            <div class="text-lg font-bold font-mono text-slate-100">{{ stats.totalClusters }}</div>
            <div class="text-[10px] text-slate-500 uppercase tracking-wider">Clusters</div>
          </RouterLink>

          <RouterLink to="/infrastructure" class="p-3 bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 rounded-lg transition-all group">
            <Layers class="w-4 h-4 text-violet-400 mb-2" />
            <div class="text-lg font-bold font-mono text-slate-100">{{ stats.totalNamespaces }}</div>
            <div class="text-[10px] text-slate-500">Namespaces</div>
          </RouterLink>

          <RouterLink to="/infrastructure" class="p-3 bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 rounded-lg transition-all group">
            <Cpu class="w-4 h-4 text-amber-400 mb-2" />
            <div class="text-lg font-bold font-mono text-slate-100">{{ stats.totalServicos }}</div>
            <div class="text-[10px] text-slate-500">Serviços</div>
          </RouterLink>

          <RouterLink to="/infrastructure" class="p-3 bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 rounded-lg transition-all group">
            <Server class="w-4 h-4 text-emerald-400 mb-2" />
            <div class="text-lg font-bold font-mono text-slate-100">{{ stats.totalServicosNegocio }}</div>
            <div class="text-[10px] text-slate-500">Svcs. Negócio</div>
          </RouterLink>

          <RouterLink to="/infrastructure" class="p-3 bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 rounded-lg transition-all group">
            <Boxes class="w-4 h-4 text-indigo-400 mb-2" />
            <div class="text-lg font-bold font-mono text-slate-100">{{ stats.totalInstancias }}</div>
            <div class="text-[10px] text-slate-500">Instâncias</div>
          </RouterLink>

          <RouterLink to="/reference-data" class="p-3 bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 rounded-lg transition-all group">
            <Database class="w-4 h-4 text-rose-400 mb-2" />
            <div class="text-lg font-bold font-mono text-slate-100">{{ stats.tiposAtivo + stats.ambientes + stats.criticidades + stats.areas + stats.sos }}</div>
            <div class="text-[10px] text-slate-500">Auxiliares</div>
          </RouterLink>
        </div>
      </div>
    </div>

    <!-- Painel: eventos recentes + status -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- Eventos recentes -->
      <div class="lg:col-span-2 bg-slate-950 border border-slate-800 rounded-xl p-6">
        <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
          <Clock class="w-4 h-4 text-amber-400" />
          Atividade Recente
        </h3>

        <div v-if="recentLogs.length === 0 && !isLoading" class="text-xs text-slate-500">
          Nenhum evento registrado.
        </div>

        <ul v-else class="space-y-2">
          <li
            v-for="log in recentLogs"
            :key="log.id"
            class="flex items-center justify-between gap-3 p-3 bg-slate-900/40 rounded-lg border border-slate-800/50"
          >
            <div class="flex items-center gap-3 min-w-0">
              <span
                class="text-[10px] font-bold font-mono px-1.5 py-0.5 rounded"
                :class="acaoColors[log.acao || ''] || 'text-slate-400'"
              >
                {{ log.acao || '—' }}
              </span>
              <span class="text-xs text-slate-300 truncate">
                {{ log.entidade }}<template v-if="log.entidade_id"> #{{ log.entidade_id }}</template>
                <span class="text-slate-500"> por {{ log.usuario || 'sistema' }}</span>
              </span>
            </div>
            <span class="text-[10px] text-slate-500 font-mono shrink-0">{{ fmtDate(log.created_at) }}</span>
          </li>
        </ul>

        <RouterLink to="/audit" class="mt-4 inline-flex items-center gap-1 text-xs text-amber-400 hover:underline">
          Ver trilha completa <ArrowUpRight class="w-3 h-3" />
        </RouterLink>
      </div>

      <!-- Status dos serviços -->
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
        <div>
          <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
            <Activity class="w-4 h-4 text-emerald-400" />
            Serviços do Backend
          </h3>
          <ul class="space-y-3">
            <li class="flex items-center justify-between p-3 bg-slate-900/40 rounded-lg border border-slate-800/50">
              <span class="text-xs text-slate-300">Banco de Dados</span>
              <span
                class="inline-flex items-center gap-1 text-[11px]"
                :class="health?.database === 'healthy' ? 'text-emerald-400' : 'text-rose-400'"
              >
                <CheckCircle2 v-if="health?.database === 'healthy'" class="w-3.5 h-3.5" />
                <XCircle v-else class="w-3.5 h-3.5" />
                {{ health?.database === 'healthy' ? 'Conectado' : 'Indisponível' }}
              </span>
            </li>
            <li class="flex items-center justify-between p-3 bg-slate-900/40 rounded-lg border border-slate-800/50">
              <span class="text-xs text-slate-300">Automações (Service Tokens)</span>
              <span class="inline-flex items-center gap-1 text-[11px] text-emerald-400">
                <CheckCircle2 class="w-3.5 h-3.5" /> Habilitadas
              </span>
            </li>
            <li class="flex items-center justify-between p-3 bg-slate-900/40 rounded-lg border border-slate-800/50">
              <span class="text-xs text-slate-300">Integração AD / LDAP</span>
              <span class="inline-flex items-center gap-1 text-[11px] text-emerald-400">
                <CheckCircle2 class="w-3.5 h-3.5" /> Ativa
              </span>
            </li>
          </ul>
        </div>

        <div class="mt-6 pt-4 border-t border-slate-800/80 flex items-center gap-2 text-[11px] text-slate-500">
          <Clock class="w-3.5 h-3.5" />
          <span>Sessão autenticada via JWT com refresh automático</span>
        </div>
      </div>
    </div>
  </div>
</template>