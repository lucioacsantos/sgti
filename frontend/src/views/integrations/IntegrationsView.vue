<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { healthService } from '@/services/cmdb.services'
import type { ApiInfo } from '@/services/cmdb'
import ErrorAlert from '@/components/ErrorAlert.vue'
import {
  Layers, Bot, Bell, CheckCircle2, XCircle, Server, KeyRound, RefreshCw
} from 'lucide-vue-next'

const apiInfo = ref<ApiInfo | null>(null)
const health = ref<{ status: string; database: string } | null>(null)
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)

async function loadStatus() {
  isLoading.value = true
  errorMessage.value = null
  try {
    const [info, h] = await Promise.allSettled([
      healthService.root(),
      healthService.health()
    ])
    if (info.status === 'fulfilled') apiInfo.value = info.value
    if (h.status === 'fulfilled') health.value = h.value
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    isLoading.value = false
  }
}

onMounted(loadStatus)
</script>

<template>
  <div class="space-y-6">
    <!-- Cabeçalho -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 class="text-lg font-bold text-slate-100 flex items-center gap-2">
          <Layers class="w-5 h-5 text-amber-400" />
          Integrações & Automações
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">
          O CMDB é abastecido majoritariamente por automações via Service Tokens — sem formulários manuais.
        </p>
      </div>

      <button
        @click="loadStatus"
        :disabled="isLoading"
        class="inline-flex items-center gap-2 px-3.5 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-semibold text-xs rounded-lg transition-colors disabled:opacity-50"
      >
        <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
        Verificar status
      </button>
    </div>

    <ErrorAlert :error="errorMessage" />

    <!-- Cards de integração -->
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-6">
      <!-- API Core -->
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-6">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-semibold text-slate-100 flex items-center gap-2">
            <Server class="w-4 h-4 text-emerald-400" />
            API CMDB
          </h3>
          <span
            class="inline-flex items-center gap-1 text-[11px]"
            :class="health?.database === 'healthy' ? 'text-emerald-400' : 'text-rose-400'"
          >
            <CheckCircle2 v-if="health?.database === 'healthy'" class="w-3.5 h-3.5" />
            <XCircle v-else class="w-3.5 h-3.5" />
            {{ health?.database === 'healthy' ? 'saudável' : 'indisponível' }}
          </span>
        </div>

        <dl class="space-y-2 text-xs">
          <div class="flex justify-between p-2.5 bg-slate-900/40 rounded border border-slate-800/50">
            <dt class="text-slate-500">Versão</dt>
            <dd class="font-mono text-slate-200">{{ apiInfo?.version || '—' }}</dd>
          </div>
          <div class="flex justify-between p-2.5 bg-slate-900/40 rounded border border-slate-800/50">
            <dt class="text-slate-500">Status geral</dt>
            <dd class="font-mono" :class="health?.status === 'healthy' ? 'text-emerald-400' : 'text-amber-400'">
              {{ health?.status || '—' }}
            </dd>
          </div>
          <div class="flex justify-between p-2.5 bg-slate-900/40 rounded border border-slate-800/50">
            <dt class="text-slate-500">Documentação OpenAPI</dt>
            <dd>
              <a :href="apiInfo?.docs || '/docs'" target="_blank" class="font-mono text-sky-400 hover:underline">/docs</a>
            </dd>
          </div>
        </dl>
      </div>

      <!-- Ollama -->
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-6">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-semibold text-slate-100 flex items-center gap-2">
            <Bot class="w-4 h-4 text-sky-400" />
            Ollama (IA Generativa)
          </h3>
          <span class="inline-flex items-center gap-1 text-[11px] text-slate-500">
            <KeyRound class="w-3 h-3" /> X-Service-Token
          </span>
        </div>

        <p class="text-xs text-slate-400 leading-relaxed">
          Consultas de análise via <code class="text-[10px] bg-slate-900 px-1.5 py-0.5 rounded font-mono">POST /ollama/</code>
          — usado por automações para enriquecer diagnósticos.
        </p>

        <div class="mt-4 p-3 bg-slate-900/40 rounded border border-slate-800/50">
          <p class="text-[10px] text-slate-500 font-mono leading-relaxed">
            { "question": "...", "model": "llama3" }<br />
            → { "response": "..." }
          </p>
        </div>
      </div>

      <!-- Zabbix -->
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-6">
        <div class="flex items-center justify-between mb-4">
          <h3 class="text-sm font-semibold text-slate-100 flex items-center gap-2">
            <Bell class="w-4 h-4 text-rose-400" />
            Zabbix (Monitoramento)
          </h3>
          <span class="inline-flex items-center gap-1 text-[11px] text-slate-500">
            <KeyRound class="w-3 h-3" /> X-Service-Token
          </span>
        </div>

        <p class="text-xs text-slate-400 leading-relaxed">
          Registro de observações geradas por IA em alarmes abertos via
          <code class="text-[10px] bg-slate-900 px-1.5 py-0.5 rounded font-mono">POST /zabbix/alarmes/observacao-ollama/</code>.
        </p>

        <div class="mt-4 p-3 bg-slate-900/40 rounded border border-slate-800/50">
          <p class="text-[10px] text-slate-500 font-mono leading-relaxed">
            { "event_id": "...", "question": "..." }<br />
            → { event_id, problem_name, ollama_response, zabbix_result }
          </p>
        </div>
      </div>
    </div>

    <!-- Nota sobre automações -->
    <div class="bg-slate-950/60 border border-slate-800 rounded-xl p-6">
      <h3 class="text-sm font-semibold uppercase tracking-wider text-slate-300 mb-3 flex items-center gap-2">
        <Bot class="w-4 h-4 text-emerald-400" />
        Como as automações alimentam o CMDB
      </h3>
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 text-xs text-slate-400 leading-relaxed">
        <div class="p-4 bg-slate-900/40 rounded-lg border border-slate-800/50">
          <p class="text-slate-200 font-medium mb-1">Inventário</p>
          Automações criam/atualizam ativos via <span class="font-mono text-[10px] text-emerald-400">PUT /ativos/{nome}</span> (upsert) e registram IPs via <span class="font-mono text-[10px] text-emerald-400">POST /enderecos-ip/</span>.
        </div>
        <div class="p-4 bg-slate-900/40 rounded-lg border border-slate-800/50">
          <p class="text-slate-200 font-medium mb-1">Topologia</p>
          Clusters, namespaces, serviços e instâncias são provisionados por pipelines — consultáveis nas abas de Infraestrutura.
        </div>
        <div class="p-4 bg-slate-900/40 rounded-lg border border-slate-800/50">
          <p class="text-slate-200 font-medium mb-1">Auditoria</p>
          Toda escrita via API gera registro automático na trilha de auditoria, visível em <RouterLink to="/audit" class="text-amber-400 hover:underline">Auditoria</RouterLink>.
        </div>
      </div>
    </div>
  </div>
</template>