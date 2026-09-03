<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { RouterLink } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { api } from '@/services/api'
import { 
  Server, 
  Network, 
  Database, 
  ShieldAlert, 
  Activity, 
  ArrowUpRight,
  CheckCircle2,
  Clock,
  Layers
} from 'lucide-vue-next'

const authStore = useAuthStore()

// Estados para contadores e status rápidos
const stats = ref({
  totalAssets: 0,
  totalSubnets: 0,
  referenceDataCount: 0,
  recentAuditLogs: 0
})

/* const servicesStatus = ref({
  apiStatus: 'online',
  zabbixIntegration: 'active',
  adSync: 'active'
}) */

const recentEvents = ref<Array<{ id: number; action: string; user: string; timestamp: string }>>([])
const isLoading = ref(true)

async function loadDashboardSummary() {
  isLoading.value = true
  try {
    // Exemplo de chamadas paralelas para alimentar os indicadores
    // Caso alguma rota falhe em ambiente inicial, tratamos graciosamente
    const [assetsRes, auditRes] = await Promise.allSettled([
      api.get('/assets/?limit=1'),
      api.get('/audit/?limit=5')
    ])

    if (assetsRes.status === 'fulfilled' && assetsRes.value.data) {
      stats.value.totalAssets = assetsRes.value.data.total || assetsRes.value.data.length || 0
    }

    if (auditRes.status === 'fulfilled' && auditRes.value.data) {
      recentEvents.value = Array.isArray(auditRes.value.data) 
        ? auditRes.value.data.slice(0, 5) 
        : []
    }
  } catch (err) {
    console.error('Erro ao carregar resumo do dashboard:', err)
  } finally {
    isLoading.value = false
  }
}

onMounted(() => {
  loadDashboardSummary()
})
</script>

<template>
  <div class="space-y-8">
    <!-- Boas-vindas -->
    <div class="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-950/60 p-6 rounded-xl border border-slate-800">
      <div>
        <h2 class="text-xl font-bold text-slate-100">
          Olá, <span class="text-emerald-400 font-mono">{{ authStore.user?.display_name }}</span>
        </h2>
        <p class="text-xs text-slate-400 mt-1">
          Bem-vindo ao console central de infraestrutura, ativos e governança de rede.
        </p>
      </div>

      <div class="flex items-center gap-2">
        <span class="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
          <span class="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse"></span>
          Sistemas Operacionais
        </span>
      </div>
    </div>

    <!-- Cards de Métricas Principais -->
    <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
      <!-- Card: Ativos -->
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-colors">
        <div class="flex items-center justify-between text-slate-400">
          <span class="text-xs font-semibold uppercase tracking-wider">Ativos de TI</span>
          <Server class="w-4 h-4 text-emerald-400" />
        </div>
        <div class="mt-4 flex items-baseline justify-between">
          <div class="text-2xl font-bold font-mono text-slate-100">
            {{ stats.totalAssets }}
          </div>
          <RouterLink to="/assets" class="text-xs text-emerald-400 hover:underline flex items-center gap-0.5">
            Ver todos <ArrowUpRight class="w-3 h-3" />
          </RouterLink>
        </div>
      </div>

      <!-- Card: Infra / Redes -->
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-colors">
        <div class="flex items-center justify-between text-slate-400">
          <span class="text-xs font-semibold uppercase tracking-wider">Infraestrutura & IP</span>
          <Network class="w-4 h-4 text-sky-400" />
        </div>
        <div class="mt-4 flex items-baseline justify-between">
          <div class="text-2xl font-bold font-mono text-slate-100">
            --
          </div>
          <RouterLink to="/infrastructure" class="text-xs text-sky-400 hover:underline flex items-center gap-0.5">
            Gerenciar <ArrowUpRight class="w-3 h-3" />
          </RouterLink>
        </div>
      </div>

      <!-- Card: Dados Mestres -->
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-colors">
        <div class="flex items-center justify-between text-slate-400">
          <span class="text-xs font-semibold uppercase tracking-wider">Tabelas de Apoio</span>
          <Database class="w-4 h-4 text-indigo-400" />
        </div>
        <div class="mt-4 flex items-baseline justify-between">
          <div class="text-2xl font-bold font-mono text-slate-100">
            Ativo
          </div>
          <RouterLink to="/reference-data" class="text-xs text-indigo-400 hover:underline flex items-center gap-0.5">
            Configurar <ArrowUpRight class="w-3 h-3" />
          </RouterLink>
        </div>
      </div>

      <!-- Card: Auditoria -->
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-5 flex flex-col justify-between hover:border-slate-700 transition-colors">
        <div class="flex items-center justify-between text-slate-400">
          <span class="text-xs font-semibold uppercase tracking-wider">Trilha de Auditoria</span>
          <ShieldAlert class="w-4 h-4 text-amber-400" />
        </div>
        <div class="mt-4 flex items-baseline justify-between">
          <div class="text-2xl font-bold font-mono text-slate-100">
            Log ativo
          </div>
          <RouterLink to="/audit" class="text-xs text-amber-400 hover:underline flex items-center gap-0.5">
            Histórico <ArrowUpRight class="w-3 h-3" />
          </RouterLink>
        </div>
      </div>
    </div>

    <!-- Painel Duplo: Acesso Rápido / Status de Serviços -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      
      <!-- Ações Rápidas -->
      <div class="lg:col-span-2 bg-slate-950 border border-slate-800 rounded-xl p-6">
        <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
          <Layers class="w-4 h-4 text-emerald-400" />
          Ações Administrativas Frequentes
        </h3>
        <div class="grid grid-cols-1 sm:grid-cols-2 gap-3">
          <RouterLink 
            to="/assets" 
            class="p-4 bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 hover:border-emerald-500/30 rounded-lg transition-all flex items-start gap-3 group"
          >
            <div class="p-2.5 bg-emerald-500/10 rounded-md text-emerald-400 group-hover:scale-105 transition-transform">
              <Server class="w-5 h-5" />
            </div>
            <div>
              <h4 class="text-sm font-medium text-slate-200">Inventário de Ativos</h4>
              <p class="text-xs text-slate-500 mt-0.5">Listar, buscar e gerenciar servidores e equipamentos.</p>
            </div>
          </RouterLink>

          <RouterLink 
            to="/reference-data" 
            class="p-4 bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 hover:border-indigo-500/30 rounded-lg transition-all flex items-start gap-3 group"
          >
            <div class="p-2.5 bg-indigo-500/10 rounded-md text-indigo-400 group-hover:scale-105 transition-transform">
              <Database class="w-5 h-5" />
            </div>
            <div>
              <h4 class="text-sm font-medium text-slate-200">Dados Mestres (Reference Data)</h4>
              <p class="text-xs text-slate-500 mt-0.5">Parametrizar tipos de ativos, locais e status operacionais.</p>
            </div>
          </RouterLink>

          <RouterLink 
            to="/infrastructure" 
            class="p-4 bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 hover:border-sky-500/30 rounded-lg transition-all flex items-start gap-3 group"
          >
            <div class="p-2.5 bg-sky-500/10 rounded-md text-sky-400 group-hover:scale-105 transition-transform">
              <Network class="w-5 h-5" />
            </div>
            <div>
              <h4 class="text-sm font-medium text-slate-200">Segmentação e Endereçamento</h4>
              <p class="text-xs text-slate-500 mt-0.5">Controlar alocações de IP, sub-redes e interfaces[cite: 1].</p>
            </div>
          </RouterLink>

          <RouterLink 
            to="/integrations" 
            class="p-4 bg-slate-900/60 hover:bg-slate-900 border border-slate-800/80 hover:border-amber-500/30 rounded-lg transition-all flex items-start gap-3 group"
          >
            <div class="p-2.5 bg-amber-500/10 rounded-md text-amber-400 group-hover:scale-105 transition-transform">
              <Activity class="w-5 h-5" />
            </div>
            <div>
              <h4 class="text-sm font-medium text-slate-200">Monitoramento & Integrações</h4>
              <p class="text-xs text-slate-500 mt-0.5">Consultar comunicação com Zabbix e conectores externos[cite: 1].</p>
            </div>
          </RouterLink>
        </div>
      </div>

      <!-- Status de Conexões e Provedores -->
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-6 flex flex-col justify-between">
        <div>
          <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-4 flex items-center gap-2">
            <Activity class="w-4 h-4 text-emerald-400" />
            Serviços do Backend
          </h3>
          <ul class="space-y-3">
            <li class="flex items-center justify-between p-3 bg-slate-900/40 rounded-lg border border-slate-800/50">
              <span class="text-xs text-slate-300">FastAPI REST Core</span>
              <span class="inline-flex items-center gap-1 text-[11px] text-emerald-400">
                <CheckCircle2 class="w-3.5 h-3.5" /> Conectado
              </span>
            </li>
            <li class="flex items-center justify-between p-3 bg-slate-900/40 rounded-lg border border-slate-800/50">
              <span class="text-xs text-slate-300">Active Directory / LDAP</span>
              <span class="inline-flex items-center gap-1 text-[11px] text-emerald-400">
                <CheckCircle2 class="w-3.5 h-3.5" /> Habilitado[cite: 1]
              </span>
            </li>
            <li class="flex items-center justify-between p-3 bg-slate-900/40 rounded-lg border border-slate-800/50">
              <span class="text-xs text-slate-300">Zabbix Sync Engine</span>
              <span class="inline-flex items-center gap-1 text-[11px] text-emerald-400">
                <CheckCircle2 class="w-3.5 h-3.5" /> Pronto[cite: 1]
              </span>
            </li>
          </ul>
        </div>

        <div class="mt-6 pt-4 border-t border-slate-800/80 flex items-center gap-2 text-[11px] text-slate-500">
          <Clock class="w-3.5 h-3.5" />
          <span>Sessão autenticada via token JWT</span>
        </div>
      </div>

    </div>
  </div>
</template>