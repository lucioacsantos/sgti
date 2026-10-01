<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { reconciliacaoService } from '@/services/cmdb.services'
import { useAuthStore } from '@/stores/auth'
import type {
  Reconciliacao, ItemReconciliacao, ParecerTipo, ItemDecisao,
  ReconciliacaoFonte, ItemReconciliacaoStatus
} from '@/services/cmdb'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import ErrorAlert from '@/components/ErrorAlert.vue'
import LoadingState from '@/components/LoadingState.vue'
import {
  GitCompareArrows, RefreshCw, Plus, ChevronDown, ChevronRight, CheckCircle2,
  Ban, ShieldQuestion, Users, CircleDot, Gavel, XCircle, ScanEye, Clock
} from 'lucide-vue-next'

const authStore = useAuthStore()

const execucoes = ref<Reconciliacao[]>([])
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)
const successMessage = ref<string | null>(null)

const selected = ref<Reconciliacao | null>(null)
const itens = ref<ItemReconciliacao[]>([])
const itensLoading = ref(false)
const statusFilter = ref<ItemReconciliacaoStatus | ''>('')
const expanded = ref<Set<number>>(new Set())

const novaModal = ref(false)
const novaNome = ref('')
const novaFonte = ref<ReconciliacaoFonte>('manual')
const novaAuto = ref(true)
const novaLoading = ref(false)
const paraCancelar = ref<Reconciliacao | null>(null)

const parecerModal = ref<ItemReconciliacao | null>(null)
const parecerTipo = ref<ParecerTipo>('retificar')
const parecerComentario = ref('')
const parecerLoading = ref(false)

const decisaoModal = ref<ItemReconciliacao | null>(null)
const decisaoTipo = ref<ItemDecisao>('retificado')
const decisaoLoading = ref(false)

const isAdmin = computed(() => authStore.isAdmin)

const FONTE_LABEL: Record<ReconciliacaoFonte, string> = {
  dump_pgadmin: 'Dump pgAdmin',
  zabbix: 'Zabbix',
  manual: 'Verificação manual',
  ia: 'Inferência IA'
}

const STATUS_LABEL: Record<string, string> = {
  aberta: 'Aberta',
  em_verificacao: 'Em verificação',
  concluida: 'Concluída',
  cancelada: 'Cancelada',
  pendente: 'Pendente',
  retificado: 'Retificado',
  ratificado: 'Ratificado',
  ignorado: 'Ignorado'
}

async function loadExecucoes() {
  isLoading.value = true
  errorMessage.value = null
  try {
    execucoes.value = await reconciliacaoService.list()
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    isLoading.value = false
  }
}

async function abrirExecucao(recon: Reconciliacao) {
  if (selected.value?.id === recon.id) {
    selected.value = null
    return
  }
  selected.value = recon
  await loadItens()
}

async function loadItens() {
  if (!selected.value) return
  itensLoading.value = true
  errorMessage.value = null
  try {
    itens.value = await reconciliacaoService.itens(
      selected.value.id, statusFilter.value || undefined)
    expanded.value.clear()
    if (selected.value) {
      const atual = execucoes.value.find(e => e.id === selected.value!.id)
      if (atual) selected.value = atual
    }
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    itensLoading.value = false
  }
}

function toggleExpand(itemId: number) {
  if (expanded.value.has(itemId)) expanded.value.delete(itemId)
  else expanded.value.add(itemId)
}

async function criarExecucao() {
  if (!novaNome.value.trim()) return
  novaLoading.value = true
  errorMessage.value = null
  try {
    const criada = await reconciliacaoService.create(
      { nome: novaNome.value.trim(), fonte: novaFonte.value }, novaAuto.value)
    novaModal.value = false
    novaNome.value = ''
    successMessage.value = `Execução #${criada.id} criada com ${criada.total_itens} discrepância(s) pendente(s).`
    await loadExecucoes()
    await abrirExecucao(criada)
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    novaLoading.value = false
  }
}

async function salvarParecer() {
  const item = parecerModal.value
  if (!item || !selected.value) return
  parecerLoading.value = true
  errorMessage.value = null
  try {
    await reconciliacaoService.registrarParecer(
      selected.value.id, item.id, parecerTipo.value,
      parecerComentario.value.trim() || undefined)
    parecerModal.value = null
    parecerComentario.value = ''
    await loadItens()
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    parecerLoading.value = false
  }
}

async function salvarDecisao() {
  const item = decisaoModal.value
  if (!item || !selected.value) return
  decisaoLoading.value = true
  errorMessage.value = null
  try {
    await reconciliacaoService.decidirItem(
      selected.value.id, item.id, decisaoTipo.value)
    decisaoModal.value = null
    await loadItens()
  } catch (err) {
    errorMessage.value = String(err)
    decisaoModal.value = null
  } finally {
    decisaoLoading.value = false
  }
}

async function concluirExecucao() {
  if (!selected.value) return
  try {
    const concluida = await reconciliacaoService.concluir(selected.value.id)
    successMessage.value = `Execução #${concluida.id} concluída.`
    await loadExecucoes()
    selected.value = concluida
  } catch (err) {
    errorMessage.value = String(err)
  }
}

async function confirmarCancelamento() {
  if (!paraCancelar.value) return
  try {
    await reconciliacaoService.cancelar(paraCancelar.value.id)
    if (selected.value?.id === paraCancelar.value.id) selected.value = null
    await loadExecucoes()
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    paraCancelar.value = null
  }
}

function abrirParecer(item: ItemReconciliacao, tipo: ParecerTipo = 'retificar') {
  parecerModal.value = item
  parecerTipo.value = tipo
  parecerComentario.value = ''
}

function abrirDecisao(item: ItemReconciliacao, tipo: ItemDecisao = 'retificado') {
  decisaoModal.value = item
  decisaoTipo.value = tipo
}

function euJaDeiParecer(item: ItemReconciliacao): boolean {
  const atual = nomeAnalistaCorrente().trim().toLowerCase()
  return item.analistas.some(a => a.trim().toLowerCase() === atual)
}

function nomeAnalistaCorrente(): string {
  return authStore.userName || authStore.user?.username || ''
}

function statusClass(status: string): string {
  switch (status) {
    case 'aberta': case 'pendente':
      return 'bg-amber-500/10 text-amber-400 border-amber-500/20'
    case 'em_verificacao':
      return 'bg-sky-500/10 text-sky-400 border-sky-500/20'
    case 'retificado':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    case 'ratificado':
      return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    case 'ignorado': case 'cancelada':
      return 'bg-slate-800 text-slate-400 border-slate-700'
    case 'concluida':
      return 'bg-emerald-600/10 text-emerald-300 border-emerald-600/30'
    default:
      return 'bg-slate-800 text-slate-400 border-slate-700'
  }
}

function confiancaLabel(confianca?: number | null): string {
  if (confianca == null) return ''
  return `${Math.round(confianca * 100)}% confiança IA`
}

function confiancaClass(confianca?: number | null): string {
  if (confianca == null) return ''
  if (confianca < 0.7) return 'bg-rose-500/10 text-rose-400 border-rose-500/20'
  if (confianca < 0.9) return 'bg-amber-500/10 text-amber-400 border-amber-500/20'
  return 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
}

function fmtDate(iso?: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

const pendentesCount = computed(() =>
  itens.value.filter(i => i.status === 'pendente' || i.status === 'em_verificacao').length)

const podeConcluir = computed(() =>
  selected.value && isAdmin.value && pendentesCount.value === 0 &&
  selected.value.status !== 'concluida' && selected.value.status !== 'cancelada')

onMounted(loadExecucoes)
</script>

<template>
  <div class="space-y-6">
    <!-- Cabeçalho -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 class="text-lg font-bold text-slate-100 flex items-center gap-2">
          <GitCompareArrows class="w-5 h-5 text-violet-400" />
          Reconciliações
        </h2>
        <p class="text-xs text-slate-500 mt-1">
          Discrepâncias entre o CMDB e as fontes externas. Verificação manual exige
          <strong class="text-slate-300">no mínimo 2 analistas</strong> com parecer registrado
          (workflow de quatro olhos) antes de retificar ou ratificar.
        </p>
      </div>
      <div class="flex gap-2">
        <button
          @click="loadExecucoes"
          class="flex items-center gap-2 px-3 py-2 text-xs rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 transition-colors"
        >
          <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
          Atualizar
        </button>
        <button
          @click="novaModal = true"
          class="flex items-center gap-2 px-3 py-2 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 transition-colors font-medium"
        >
          <Plus class="w-3.5 h-3.5" />
          Nova reconciliação
        </button>
      </div>
    </div>

    <ErrorAlert v-if="errorMessage" :error="errorMessage" />
    <div
      v-if="successMessage"
      class="flex items-center gap-2 px-4 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs"
    >
      <CheckCircle2 class="w-4 h-4" />
      {{ successMessage }}
      <button class="ml-auto text-emerald-400/60 hover:text-emerald-300" @click="successMessage = null">
        <XCircle class="w-3.5 h-3.5" />
      </button>
    </div>

    <LoadingState v-if="isLoading" label="Carregando reconciliações..." />

    <!-- Lista de execuções -->
    <div v-else-if="execucoes.length" class="space-y-3">
      <div
        v-for="recon in execucoes"
        :key="recon.id"
        class="rounded-xl border bg-slate-950/50 transition-colors"
        :class="selected?.id === recon.id ? 'border-violet-500/40' : 'border-slate-800'"
      >
        <button
          class="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-900/50 rounded-xl"
          @click="abrirExecucao(recon)"
        >
          <component
            :is="selected?.id === recon.id ? ChevronDown : ChevronRight"
            class="w-4 h-4 text-slate-500 shrink-0"
          />
          <div class="flex-1 min-w-0">
            <div class="flex items-center gap-2 flex-wrap">
              <span class="text-sm font-semibold text-slate-100">{{ recon.nome }}</span>
              <span class="text-[10px] uppercase tracking-wider px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 font-mono">
                #{{ recon.id }}
              </span>
              <span class="text-[10px] px-1.5 py-0.5 rounded border" :class="statusClass(recon.status)">
                {{ STATUS_LABEL[recon.status] }}
              </span>
              <span class="text-[10px] text-slate-500">fonte: {{ FONTE_LABEL[recon.fonte] }}</span>
            </div>
            <div class="text-[11px] text-slate-500 mt-0.5">
              criada por {{ recon.criado_por || '—' }} em {{ fmtDate(recon.criado_em) }}
            </div>
          </div>
          <div class="flex items-center gap-2 text-[10px] shrink-0">
            <span class="px-2 py-1 rounded bg-slate-800 text-slate-300">{{ recon.total_itens }} itens</span>
            <span
              v-if="recon.pendentes"
              class="px-2 py-1 rounded bg-amber-500/10 text-amber-400 border border-amber-500/20"
            >
              {{ recon.pendentes }} pendente(s)
            </span>
            <span v-if="recon.retificados" class="px-2 py-1 rounded bg-emerald-500/10 text-emerald-400">
              {{ recon.retificados }} retif.
            </span>
            <span v-if="recon.ratificados" class="px-2 py-1 rounded bg-sky-500/10 text-sky-400">
              {{ recon.ratificados }} ratif.
            </span>
          </div>
        </button>

        <!-- Painel expandido -->
        <div v-if="selected?.id === recon.id" class="border-t border-slate-800 p-4 space-y-4">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <div class="flex items-center gap-2">
              <select
                v-model="statusFilter"
                @change="loadItens"
                class="bg-slate-900 border border-slate-700 rounded-lg text-xs text-slate-300 px-2 py-1.5"
              >
                <option value="">Todos os status</option>
                <option value="pendente">Pendentes</option>
                <option value="em_verificacao">Em verificação</option>
                <option value="retificado">Retificados</option>
                <option value="ratificado">Ratificados</option>
                <option value="ignorado">Ignorados</option>
              </select>
              <span class="text-[11px] text-slate-500 flex items-center gap-1">
                <Users class="w-3.5 h-3.5" />
                {{ pendentesCount }} aguardando verificação (2+ analistas)
              </span>
            </div>
            <div class="flex gap-2">
              <button
                v-if="podeConcluir"
                @click="concluirExecucao"
                class="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 font-medium"
              >
                <CheckCircle2 class="w-3.5 h-3.5" />
                Concluir reconciliação
              </button>
              <span
                v-else-if="selected.status === 'aberta' || selected.status === 'em_verificacao'"
                class="text-[10px] text-slate-500 flex items-center gap-1 px-2"
              >
                <Clock class="w-3 h-3" />
                {{ isAdmin ? 'resolva todos os itens para concluir' : 'somente admin conclui' }}
              </span>
              <button
                v-if="isAdmin && selected.status !== 'cancelada' && selected.status !== 'concluida'"
                @click="paraCancelar = selected"
                class="flex items-center gap-1.5 px-3 py-1.5 text-xs rounded-lg border border-rose-500/30 text-rose-400 hover:bg-rose-500/10"
              >
                <Ban class="w-3.5 h-3.5" />
                Cancelar
              </button>
            </div>
          </div>

          <LoadingState v-if="itensLoading" label="Carregando itens..." />

          <div v-else-if="itens.length === 0" class="text-xs text-slate-500 py-6 text-center">
            Nenhuma discrepância registrada para este filtro.
          </div>

          <!-- Itens de discrepância -->
          <div v-else class="space-y-2">
            <div
              v-for="item in itens"
              :key="item.id"
              class="rounded-lg border border-slate-800 bg-slate-900/40 overflow-hidden"
            >
              <div class="flex items-center gap-3 px-3 py-2.5">
                <button @click="toggleExpand(item.id)" class="shrink-0">
                  <component
                    :is="expanded.has(item.id) ? ChevronDown : ChevronRight"
                    class="w-3.5 h-3.5 text-slate-500"
                  />
                </button>
                <CircleDot class="w-3.5 h-3.5 text-violet-400 shrink-0" />
                <div class="flex-1 min-w-0">
                  <div class="flex items-center gap-2 flex-wrap text-xs">
                    <span class="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-violet-300 uppercase">
                      {{ item.entidade }}
                    </span>
                    <span v-if="item.entidade_id" class="text-slate-500 font-mono text-[10px]">
                      id={{ item.entidade_id }}
                    </span>
                    <span v-if="item.campo" class="text-slate-500 text-[10px]">
                      campo: {{ item.campo }}
                    </span>
                    <span class="text-[10px] px-1.5 py-0.5 rounded border" :class="statusClass(item.status)">
                      {{ STATUS_LABEL[item.status] }}
                    </span>
                    <span
                      v-if="item.confianca != null"
                      class="text-[10px] px-1.5 py-0.5 rounded border font-mono"
                      :class="confiancaClass(item.confianca)"
                      :title="'Confiabilidade reportada pela inferência IA'"
                    >
                      IA {{ confiancaLabel(item.confianca).replace(' confiança IA', '') }}
                    </span>
                  </div>
                  <p class="text-xs text-slate-400 mt-1 truncate">{{ item.detalhe || '—' }}</p>
                  <p v-if="item.confianca != null" class="text-[10px] text-slate-500 mt-0.5">
                    Confiabilidade da inferência: {{ confiancaLabel(item.confianca) }}
                  </p>
                </div>
                <div class="flex items-center gap-1.5 shrink-0">
                  <span
                    class="text-[10px] flex items-center gap-1 px-1.5 py-0.5 rounded bg-slate-800"
                    :class="item.analistas.length >= 2 ? 'text-emerald-400' : 'text-slate-400'"
                  >
                    <Users class="w-3 h-3" />
                    {{ item.analistas.length }}/2+
                  </span>
                  <button
                    v-if="(item.status === 'pendente' || item.status === 'em_verificacao') && !euJaDeiParecer(item)"
                    @click="abrirParecer(item)"
                    class="flex items-center gap-1 px-2 py-1 text-[10px] rounded border border-sky-500/30 text-sky-400 hover:bg-sky-500/10"
                  >
                    <ScanEye class="w-3 h-3" />
                    Dar parecer
                  </button>
                  <span
                    v-else-if="euJaDeiParecer(item) && (item.status === 'pendente' || item.status === 'em_verificacao')"
                    class="text-[10px] text-slate-500 flex items-center gap-1"
                  >
                    <CheckCircle2 class="w-3 h-3 text-emerald-500" />
                    meu parecer registrado
                  </span>
                  <button
                    v-if="isAdmin && (item.status === 'pendente' || item.status === 'em_verificacao')"
                    @click="abrirDecisao(item)"
                    class="flex items-center gap-1 px-2 py-1 text-[10px] rounded bg-slate-800 text-slate-300 hover:bg-slate-700 border border-slate-700"
                  >
                    <Gavel class="w-3 h-3" />
                    Decidir
                  </button>
                </div>
              </div>

              <!-- Detalhes expandidos -->
              <div v-if="expanded.has(item.id)" class="border-t border-slate-800 px-4 py-3 grid grid-cols-1 lg:grid-cols-2 gap-3 text-xs">
                <div class="space-y-2">
                  <div>
                    <span class="text-[10px] uppercase tracking-wider text-slate-500">Valor no CMDB</span>
                    <p class="text-slate-300 font-mono text-[11px] mt-0.5 break-all bg-slate-950 rounded px-2 py-1.5">
                      {{ item.valor_cmdb || '—' }}
                    </p>
                  </div>
                  <div>
                    <span class="text-[10px] uppercase tracking-wider text-slate-500">Valor na fonte externa</span>
                    <p class="text-slate-300 font-mono text-[11px] mt-0.5 break-all bg-slate-950 rounded px-2 py-1.5">
                      {{ item.valor_fonte || '—' }}
                    </p>
                  </div>
                </div>
                <div class="space-y-2">
                  <span class="text-[10px] uppercase tracking-wider text-slate-500 flex items-center gap-1">
                    <ShieldQuestion class="w-3 h-3" />
                    Pareces registrados ({{ item.pareceres.length }})
                  </span>
                  <div v-if="item.pareceres.length" class="space-y-1.5">
                    <div
                      v-for="p in item.pareceres"
                      :key="p.id"
                      class="flex items-start gap-2 bg-slate-950 rounded px-2 py-1.5"
                    >
                      <Users class="w-3 h-3 text-slate-500 mt-0.5 shrink-0" />
                      <div class="min-w-0">
                        <span class="text-[11px] text-slate-300 font-medium">{{ p.analista }}</span>
                        <span
                          class="ml-1.5 text-[9px] px-1 py-0.5 rounded border"
                          :class="statusClass(p.parecer === 'retificar' ? 'retificado' : p.parecer === 'ratificar' ? 'ratificado' : 'ignorado')"
                        >
                          {{ p.parecer }}
                        </span>
                        <p v-if="p.comentario" class="text-[10px] text-slate-500 mt-0.5">{{ p.comentario }}</p>
                      </div>
                    </div>
                  </div>
                  <p v-else class="text-[11px] text-slate-500 italic">
                    Nenhum parecer ainda — selecione pelo menos 2 analistas para verificar manualmente.
                  </p>
                  <div v-if="item.resolvido_por" class="text-[10px] text-slate-500">
                    Resolvido por <span class="text-slate-300">{{ item.resolvido_por }}</span>
                    em {{ fmtDate(item.resolvido_em) }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-else class="rounded-xl border border-dashed border-slate-800 py-12 text-center">
      <GitCompareArrows class="w-8 h-8 text-slate-600 mx-auto mb-3" />
      <p class="text-sm text-slate-400">Nenhuma reconciliação executada ainda</p>
      <p class="text-xs text-slate-500 mt-1">Crie uma execução para detectar discrepâncias no CMDB.</p>
    </div>

    <!-- Modal: nova reconciliação -->
    <div v-if="novaModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="novaModal = false">
      <div class="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-md p-6 space-y-4">
        <h3 class="text-sm font-bold text-slate-100 flex items-center gap-2">
          <Plus class="w-4 h-4 text-emerald-400" />
          Nova reconciliação
        </h3>
        <div class="space-y-3">
          <div>
            <label class="text-[11px] uppercase tracking-wider text-slate-500">Nome</label>
            <input
              v-model="novaNome"
              type="text"
              placeholder="ex.: Reconciliação mensal do inventário"
              class="w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 px-3 py-2 focus:outline-none focus:border-emerald-500"
            />
          </div>
          <div>
            <label class="text-[11px] uppercase tracking-wider text-slate-500">Fonte externa</label>
            <select
              v-model="novaFonte"
              class="w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 px-3 py-2 focus:outline-none focus:border-emerald-500"
            >
              <option value="manual">Verificação manual</option>
              <option value="dump_pgadmin">Dump pgAdmin</option>
              <option value="zabbix">Zabbix</option>
              <option value="ia">Inferência IA</option>
            </select>
          </div>
          <label class="flex items-center gap-2 text-xs text-slate-300">
            <input v-model="novaAuto" type="checkbox" class="accent-emerald-500" />
            Detectar discrepâncias automaticamente
          </label>
        </div>
        <div class="flex justify-end gap-2 pt-2">
          <button @click="novaModal = false" class="px-3 py-1.5 text-xs rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800">
            Cancelar
          </button>
          <button
            @click="criarExecucao"
            :disabled="novaLoading || !novaNome.trim()"
            class="px-3 py-1.5 text-xs rounded-lg bg-emerald-600 text-white hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed font-medium"
          >
            {{ novaLoading ? 'Criando...' : 'Criar' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Modal: parecer do analista -->
    <div v-if="parecerModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="parecerModal = null">
      <div class="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-lg p-6 space-y-4">
        <h3 class="text-sm font-bold text-slate-100 flex items-center gap-2">
          <ScanEye class="w-4 h-4 text-sky-400" />
          Verificação manual — parecer
        </h3>
        <div class="bg-slate-950 rounded-lg px-3 py-2 text-xs text-slate-300 space-y-1">
          <p><span class="text-slate-500 font-mono text-[10px] uppercase">{{ parecerModal.entidade }}</span> {{ parecerModal.detalhe }}</p>
          <p class="text-[11px] text-slate-500">
            CMDB: <span class="font-mono">{{ parecerModal.valor_cmdb || '—' }}</span>
            · Fonte: <span class="font-mono">{{ parecerModal.valor_fonte || '—' }}</span>
          </p>
          <p v-if="parecerModal.confianca != null" class="text-[10px] text-violet-400/90">
            Confiabilidade da inferência IA: {{ confiancaLabel(parecerModal.confianca) }}
          </p>
          <p class="text-[10px] text-amber-400/80 flex items-center gap-1">
            <Users class="w-3 h-3" />
            Analistas que já pareceram: {{ parecerModal.analistas.join(', ') || 'nenhum' }} — exigidos no mínimo 2
          </p>
        </div>
        <div class="grid grid-cols-2 gap-2">
          <button
            v-for="opt in (['retificar', 'ratificar', 'ignorar', 'inconcluso'] as ParecerTipo[])"
            :key="opt"
            @click="parecerTipo = opt"
            class="px-3 py-2 text-xs rounded-lg border transition-colors capitalize"
            :class="parecerTipo === opt
              ? 'bg-sky-600/20 border-sky-500/40 text-sky-300'
              : 'border-slate-700 text-slate-400 hover:bg-slate-800'"
          >
            {{ opt }}
          </button>
        </div>
        <div>
          <label class="text-[11px] uppercase tracking-wider text-slate-500">Comentário (opcional)</label>
          <textarea
            v-model="parecerComentario"
            rows="3"
            placeholder="Evidência da verificação manual..."
            class="w-full mt-1 bg-slate-950 border border-slate-700 rounded-lg text-xs text-slate-200 px-3 py-2 focus:outline-none focus:border-sky-500"
          ></textarea>
        </div>
        <div class="flex justify-end gap-2 pt-1">
          <button @click="parecerModal = null" class="px-3 py-1.5 text-xs rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800">
            Cancelar
          </button>
          <button
            @click="salvarParecer"
            :disabled="parecerLoading"
            class="px-3 py-1.5 text-xs rounded-lg bg-sky-600 text-white hover:bg-sky-500 disabled:opacity-50 font-medium"
          >
            {{ parecerLoading ? 'Registrando...' : 'Registrar parecer' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Modal: decisão final (admin, 2+ analistas) -->
    <div v-if="decisaoModal" class="fixed inset-0 z-50 flex items-center justify-center bg-black/60" @click.self="decisaoModal = null">
      <div class="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-lg p-6 space-y-4">
        <h3 class="text-sm font-bold text-slate-100 flex items-center gap-2">
          <Gavel class="w-4 h-4 text-amber-400" />
          Decisão final do item
        </h3>
        <div class="bg-slate-950 rounded-lg px-3 py-2 text-xs text-slate-300 space-y-1">
          <p>{{ decisaoModal.detalhe }}</p>
          <p class="text-[10px]" :class="decisaoModal.analistas.length >= 2 ? 'text-emerald-400' : 'text-rose-400'">
            <Users class="w-3 h-3 inline" />
            {{ decisaoModal.analistas.length }} analista(s) com parecer: {{ decisaoModal.analistas.join(', ') || 'nenhum' }}
            <template v-if="decisaoModal.analistas.length < 2"> — mínimo de 2 exigido</template>
          </p>
        </div>
        <div class="grid grid-cols-3 gap-2">
          <button
            v-for="opt in (['retificado', 'ratificado', 'ignorado'] as ItemDecisao[])"
            :key="opt"
            @click="decisaoTipo = opt"
            class="px-3 py-2 text-xs rounded-lg border transition-colors capitalize"
            :class="decisaoTipo === opt
              ? 'bg-amber-600/20 border-amber-500/40 text-amber-300'
              : 'border-slate-700 text-slate-400 hover:bg-slate-800'"
          >
            {{ opt }}
          </button>
        </div>
        <div class="flex justify-end gap-2 pt-1">
          <button @click="decisaoModal = null" class="px-3 py-1.5 text-xs rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800">
            Cancelar
          </button>
          <button
            @click="salvarDecisao"
            :disabled="decisaoLoading"
            class="px-3 py-1.5 text-xs rounded-lg bg-amber-600 text-white hover:bg-amber-500 disabled:opacity-50 font-medium"
          >
            {{ decisaoLoading ? 'Gravando...' : 'Gravar decisão' }}
          </button>
        </div>
      </div>
    </div>

    <!-- Confirm: cancelar execução -->
    <ConfirmDialog
      v-if="paraCancelar"
      :title="`Cancelar reconciliação #${paraCancelar.id}?`"
      :message="`A execução '${paraCancelar.nome}' será marcada como cancelada. Itens já resolvidos são mantidos no histórico.`"
      confirm-label="Cancelar execução"
      @confirm="confirmarCancelamento"
      @cancel="paraCancelar = null"
    />
  </div>
</template>