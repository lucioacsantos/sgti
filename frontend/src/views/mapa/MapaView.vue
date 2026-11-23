<!-- Objetivo: Mapa de TI — visualização em grafo dos relacionamentos entre ativos do CMDB, com filtros interativos. -->
<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { Network } from 'vis-network/standalone'
import { DataSet } from 'vis-data/standalone'
import {
  RotateCcw, RefreshCw, ZoomIn, ZoomOut, Maximize2, Play, Pause, Tag, Download,
  X, Network as NetworkIcon, Filter, SlidersHorizontal, MousePointerClick
} from 'lucide-vue-next'
import {
  grafoService, type GrafoAresta, type GrafoFiltros, type GrafoMeta, type GrafoNo, type GrafoOpcoes
} from '@/services/graph.service'
import ErrorAlert from '@/components/ErrorAlert.vue'

/* ---------- estado dos filtros ---------- */
function filtrosPadrao(): GrafoFiltros {
  return {
    ambiente_id: null,
    tipo_ativo_id: null,
    criticidade_id: null,
    status_id: null,
    tipo_relacionamento_id: null,
    q: '',
    grau_minimo: 0,
    incluir_isolados: false,
    limite: 500
  }
}

const filtros = reactive<GrafoFiltros>(filtrosPadrao())
const opcoes = ref<GrafoOpcoes | null>(null)
const meta = ref<GrafoMeta | null>(null)
const nos = ref<GrafoNo[]>([])
const arestas = ref<GrafoAresta[]>([])
const carregando = ref(false)
const erro = ref<string | null>(null)
const selecionado = ref<GrafoNo | null>(null)
const vizinhos = ref<{ no: GrafoNo; aresta: GrafoAresta }[]>([])

/* ---------- paletas (tema escuro) ---------- */
const PALETA_TIPO: Record<string, { cor: string; shape: string }> = {
  'Servidor Físico': { cor: '#34d399', shape: 'diamond' },
  'Servidor Virtual': { cor: '#38bdf8', shape: 'dot' },
  'Container': { cor: '#a78bfa', shape: 'hexagon' },
  'Equipamento de Rede': { cor: '#fbbf24', shape: 'square' },
  'Estação de Trabalho': { cor: '#94a3b8', shape: 'ellipse' }
}
const NEUTRO = { cor: '#64748b', shape: 'ellipse' }

const PALETA_REL: Record<string, { cor: string; estilo: string }> = {
  'Depende de': { cor: '#f472b6', estilo: 'dashed' },
  'Contém': { cor: '#22d3ee', estilo: 'solid' },
  'Conecta-se a': { cor: '#475569', estilo: 'dotted' }
}
const REL_PADRAO = { cor: '#94a3b8', estilo: 'solid' }

function estiloTipo(tipo: string | null) {
  return PALETA_TIPO[tipo ?? ''] ?? NEUTRO
}
function estiloRel(nome: string | null) {
  return PALETA_REL[nome ?? ''] ?? REL_PADRAO
}

const tiposLegenda = computed(() => {
  const usados = new Set<string>()
  for (const no of nos.value) usados.add(no.tipo ?? 'Outros')
  const conhecidos = Object.keys(PALETA_TIPO).filter(t => usados.has(t))
  if (usados.has('Outros')) conhecidos.push('Outros')
  return conhecidos
})

/* ---------- rede vis-network ---------- */
const container = ref<HTMLDivElement | null>(null)
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let network: any = null
// eslint-disable-next-line @typescript-eslint/no-explicit-any
let dataEdges: any = null
let resizeObserver: ResizeObserver | null = null
const fisicaAtiva = ref(true)
const rotulosArestas = ref(true)

function tooltipNo(no: GrafoNo): string {
  const linha = (titulo: string, valor: string | null | undefined) =>
    valor ? `<b>${titulo}:</b> ${valor}` : ''
  return [
    `<span style="font-size:14px;font-weight:700">${no.nome}</span>`,
    linha('Tipo', no.tipo),
    linha('Ambiente', no.ambiente),
    linha('Status', no.status),
    linha('Criticidade', no.criticidade),
    linha('FQDN', no.fqdn),
    linha('Descrição', no.descricao),
    `<b>Conexões:</b> ${no.grau}`
  ].filter(Boolean).join('<br>')
}

function construirOpcoes() {
  return {
    autoResize: true,
    locale: 'pt-br',
    background: { color: '#0b1220' },
    interaction: {
      hover: true,
      tooltipDelay: 120,
      navigationButtons: false,
      keyboard: false,
      selectConnectedEdges: true
    },
    physics: {
      enabled: fisicaAtiva.value,
      solver: 'barnesHut',
      barnesHut: {
        gravitationalConstant: -9000,
        centralGravity: 0.28,
        springLength: 130,
        springConstant: 0.045,
        damping: 0.5,
        avoidOverlap: 0.6
      },
      stabilization: { enabled: true, iterations: 250, fit: true }
    },
    nodes: {
      shadow: { enabled: true, color: 'rgba(0,0,0,0.5)', size: 8, x: 0, y: 3 },
      font: { color: '#cbd5e1', face: 'ui-sans-serif, system-ui', size: 12 },
      chosen: { label: true, node: true }
    },
    edges: {
      smooth: { enabled: true, type: 'continuous', roundness: 0.35 }
    }
  }
}

function montarGrafo() {
  if (!container.value) return

  const nosVis = nos.value.map(no => {
    const estilo = estiloTipo(no.tipo)
    const critica = (no.criticidade ?? '') === 'Crítica'
    return {
      id: no.id,
      label: no.nome,
      title: tooltipNo(no),
      shape: estilo.shape,
      color: {
        background: estilo.cor,
        border: critica ? '#fb7185' : estilo.cor,
        highlight: { background: estilo.cor, border: '#f8fafc' },
        hover: { background: estilo.cor, border: '#f8fafc' }
      },
      font: selecionado.value?.id === no.id
        ? { color: '#f8fafc', face: 'ui-sans-serif, system-ui', size: 13 }
        : { color: '#cbd5e1', face: 'ui-sans-serif, system-ui', size: 12 },
      size: 12 + Math.min(no.grau * 1.4, 18),
      borderWidth: critica ? 3 : 1.5,
      borderWidthSelected: 3,
      mass: 1 + Math.min(no.grau, 20) * 0.35
    }
  })

  const arestasVis = arestas.value.map(aresta => {
    const estilo = estiloRel(aresta.tipo_nome)
    return {
      id: aresta.id,
      from: aresta.origem_id,
      to: aresta.destino_id,
      label: rotulosArestas.value ? (aresta.tipo_nome ?? '') : undefined,
      title: aresta.descricao ?? aresta.tipo_nome ?? undefined,
      color: { color: estilo.cor, highlight: '#f8fafc', hover: estilo.cor, opacity: 0.65 },
      dashes: estilo.estilo === 'dashed' || estilo.estilo === 'dotted',
      width: aresta.tipo_nome === 'Depende de' ? 2 : 1.5,
      arrows: 'to',
      font: { size: 9, color: '#818cf8', strokeWidth: 0, align: 'top' }
    }
  })

  dataEdges = new DataSet(arestasVis as any)

  if (network) network.destroy()
  network = new Network(
    container.value,
    { nodes: new DataSet(nosVis as any), edges: dataEdges } as any,
    construirOpcoes() as any
  )

  network.on('selectNode', (params: { nodes: number[] }) => {
    if (params.nodes.length) selecionarNo(params.nodes[0])
  })
  network.on('deselectNode', () => limparSelecao())
  network.on('click', (params: { nodes: number[] }) => {
    if (!params.nodes.length && selecionado.value) limparSelecao()
  })
  network.on('stabilizationIterationsDone', () => {
    if (!fisicaAtiva.value) network.stopSimulation()
  })
}

function limparSelecao() {
  selecionado.value = null
  vizinhos.value = []
}

/* ---------- seleção / destaque ---------- */
function selecionarNo(id: number) {
  const mapa = new Map(nos.value.map(no => [no.id, no]))
  const no = mapa.get(id)
  if (!no) return
  selecionado.value = no
  const lista: { no: GrafoNo; aresta: GrafoAresta }[] = []
  for (const aresta of arestas.value) {
    if (aresta.origem_id === id || aresta.destino_id === id) {
      const outro = mapa.get(aresta.origem_id === id ? aresta.destino_id : aresta.origem_id)
      if (outro) lista.push({ no: outro, aresta })
    }
  }
  lista.sort((a, b) => b.no.grau - a.no.grau)
  vizinhos.value = lista
}

function irPara(id: number) {
  network?.focus(id, { scale: 1.4, animation: { duration: 300, easingFunction: 'easeInOutQuad' } })
  selecionarNo(id)
}

/* ---------- carregar ---------- */
let timerCarregar: ReturnType<typeof setTimeout> | null = null

async function executarCarga() {
  carregando.value = true
  erro.value = null
  try {
    const resposta = await grafoService.carregar(filtros)
    nos.value = resposta.nodes
    arestas.value = resposta.edges
    opcoes.value = resposta.meta.opcoes
    meta.value = resposta.meta
    limparSelecao()
    montarGrafo()
  } catch (e: unknown) {
    erro.value = e instanceof Error ? e.message : 'Falha ao carregar o grafo de relacionamentos'
    nos.value = []
    arestas.value = []
    meta.value = null
  } finally {
    carregando.value = false
  }
}

function carregar(imediato = false) {
  if (timerCarregar) clearTimeout(timerCarregar)
  if (imediato) {
    void executarCarga()
    return
  }
  timerCarregar = setTimeout(() => void executarCarga(), 400)
}

watch(filtros, () => carregar(false), { deep: true })

function limparFiltros() {
  Object.assign(filtros, filtrosPadrao(), { q: '' })
}

/* ---------- controles do canvas ---------- */
function ajustar() {
  network?.fit({ animation: { duration: 350, easingFunction: 'easeInOutQuad' } })
}
function zoom(fator: number) {
  network?.moveTo({ scale: network.getScale() * fator, animation: { duration: 200, easingFunction: 'easeInOutQuad' } })
}
function alternarFisica() {
  fisicaAtiva.value = !fisicaAtiva.value
  network?.setOptions({ physics: { enabled: fisicaAtiva.value } })
  if (!fisicaAtiva.value) network?.stopSimulation()
  else network?.stabilize(120)
}
function alternarRotulos() {
  rotulosArestas.value = !rotulosArestas.value
  if (!dataEdges) return
  const atualizacoes = [] as { id: number; label?: string }[]
  for (const aresta of arestas.value) {
    atualizacoes.push({
      id: aresta.id,
      label: rotulosArestas.value ? (aresta.tipo_nome ?? '') : undefined
    })
  }
  dataEdges.update(atualizacoes)
}
function baixarPng() {
  if (!network) return
  const canvas = (network as unknown as { canvas: { frame: { canvas: HTMLCanvasElement } } }).canvas.frame.canvas
  const url = canvas.toDataURL('image/png')
  const a = document.createElement('a')
  a.href = url
  a.download = 'mapa-de-ti.png'
  a.click()
}

/* ---------- ciclo de vida ---------- */
onMounted(() => {
  resizeObserver = new ResizeObserver(() => network?.resize())
  if (container.value) resizeObserver.observe(container.value)
  carregar(true)
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  network?.destroy()
  network = null
})

/* ---------- auxiliares de template ---------- */
const temFiltro = computed(() => {
  const padrao = filtrosPadrao()
  return (Object.keys(padrao) as (keyof GrafoFiltros)[]).some(chave => filtros[chave] !== padrao[chave])
})
</script>

<template>
  <div class="h-screen w-screen flex flex-col bg-slate-950 text-slate-200 overflow-hidden">
    <!-- ---------- Cabeçalho ---------- -->
    <header class="shrink-0 flex items-center gap-4 px-4 py-3 border-b border-slate-800 bg-slate-900/70">
      <div class="flex items-center gap-2 text-emerald-400">
        <NetworkIcon class="w-5 h-5" />
      </div>
      <div class="flex-1 min-w-0">
        <h1 class="text-sm font-semibold text-slate-100 truncate">Mapa — Grafo de Relacionamentos</h1>
        <p class="text-[11px] text-slate-500 truncate">
          Ativos, vínculos e dependências do CMDB
          <template v-if="meta">
            · <span class="text-emerald-400 font-medium">{{ meta.total_nos }}</span> nós
            · <span class="text-emerald-400 font-medium">{{ meta.total_arestas }}</span> arestas
          </template>
        </p>
      </div>
      <span
        v-if="meta?.nos_truncados"
        class="hidden md:inline-flex items-center gap-1 px-2 py-1 rounded-md bg-amber-500/10 border border-amber-500/20 text-amber-400 text-[10px]"
      >
        Grafo truncado no limite de nós
      </span>
      <button
        class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs text-slate-200 transition disabled:opacity-50"
        :disabled="carregando"
        title="Recarregar grafo"
        @click="carregar(true)"
      >
        <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': carregando }" />
        Recarregar
      </button>
    </header>

    <div class="flex-1 flex min-h-0">
      <!-- ---------- Painel de filtros ---------- -->
      <aside class="hidden lg:flex flex-col w-72 shrink-0 border-r border-slate-800 bg-slate-900/50 overflow-y-auto">
        <div class="flex items-center gap-2 px-4 py-3 border-b border-slate-800">
          <SlidersHorizontal class="w-4 h-4 text-emerald-400" />
          <h2 class="text-xs font-semibold tracking-wide text-slate-300 uppercase">Filtros</h2>
          <span
            v-if="temFiltro"
            class="ml-auto px-1.5 py-0.5 rounded bg-emerald-500/15 text-emerald-400 text-[10px] font-medium"
          >ativos</span>
        </div>

        <div class="p-4 space-y-4">
          <!-- Busca -->
          <div>
            <label class="block text-[10px] font-medium uppercase tracking-wide text-slate-500 mb-1">Buscar ativo</label>
            <input
              v-model="filtros.q"
              type="search"
              placeholder="nome, fqdn ou descrição…"
              class="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-emerald-500/50 focus:ring-1 focus:ring-emerald-500/30"
            />
          </div>

          <!-- Ambiente -->
          <div>
            <label class="block text-[10px] font-medium uppercase tracking-wide text-slate-500 mb-1">Ambiente</label>
            <select
              v-model="filtros.ambiente_id"
              class="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-xs text-slate-200 focus:outline-none focus:border-emerald-500/50"
            >
              <option :value="null">Todos</option>
              <option v-for="o in opcoes?.ambientes" :key="o.id" :value="o.id">{{ o.nome }}</option>
            </select>
          </div>

          <!-- Tipo de ativo -->
          <div>
            <label class="block text-[10px] font-medium uppercase tracking-wide text-slate-500 mb-1">Tipo de ativo</label>
            <select
              v-model="filtros.tipo_ativo_id"
              class="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-xs text-slate-200 focus:outline-none focus:border-emerald-500/50"
            >
              <option :value="null">Todos</option>
              <option v-for="o in opcoes?.tipos_ativo" :key="o.id" :value="o.id">{{ o.nome }}</option>
            </select>
          </div>

          <!-- Criticidade -->
          <div>
            <label class="block text-[10px] font-medium uppercase tracking-wide text-slate-500 mb-1">Criticidade</label>
            <select
              v-model="filtros.criticidade_id"
              class="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-xs text-slate-200 focus:outline-none focus:border-emerald-500/50"
            >
              <option :value="null">Todas</option>
              <option v-for="o in opcoes?.criticidades" :key="o.id" :value="o.id">{{ o.nome }}</option>
            </select>
          </div>

          <!-- Status -->
          <div>
            <label class="block text-[10px] font-medium uppercase tracking-wide text-slate-500 mb-1">Status</label>
            <select
              v-model="filtros.status_id"
              class="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-xs text-slate-200 focus:outline-none focus:border-emerald-500/50"
            >
              <option :value="null">Todos</option>
              <option v-for="o in opcoes?.status" :key="o.id" :value="o.id">{{ o.nome }}</option>
            </select>
          </div>

          <!-- Tipo de relacionamento -->
          <div>
            <label class="block text-[10px] font-medium uppercase tracking-wide text-slate-500 mb-1">Tipo de vínculo</label>
            <select
              v-model="filtros.tipo_relacionamento_id"
              class="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-xs text-slate-200 focus:outline-none focus:border-emerald-500/50"
            >
              <option :value="null">Todos</option>
              <option v-for="o in opcoes?.tipos_relacionamento" :key="o.id" :value="o.id">{{ o.nome }}</option>
            </select>
          </div>

          <!-- Grau mínimo -->
          <div>
            <label class="flex items-center justify-between text-[10px] font-medium uppercase tracking-wide text-slate-500 mb-1">
              <span>Conexões mínimas</span>
              <span class="text-emerald-400 font-semibold">{{ filtros.grau_minimo }}</span>
            </label>
            <input
              v-model.number="filtros.grau_minimo"
              type="range"
              min="0"
              max="10"
              class="w-full accent-emerald-500"
            />
          </div>

          <!-- Limite -->
          <div>
            <label class="block text-[10px] font-medium uppercase tracking-wide text-slate-500 mb-1">Limite de nós</label>
            <input
              v-model.number="filtros.limite"
              type="number"
              min="10"
              max="5000"
              step="10"
              class="w-full px-3 py-2 rounded-lg bg-slate-800/80 border border-slate-700 text-xs text-slate-200 focus:outline-none focus:border-emerald-500/50"
            />
          </div>

          <!-- Isolados -->
          <label class="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
            <input
              v-model="filtros.incluir_isolados"
              type="checkbox"
              class="w-4 h-4 rounded accent-emerald-500"
            />
            Incluir ativos sem vínculos
          </label>

          <button
            class="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-xs font-medium transition disabled:opacity-50"
            :disabled="carregando"
            @click="carregar(true)"
          >
            <Filter class="w-3.5 h-3.5" />
            Aplicar filtros
          </button>
          <button
            class="w-full inline-flex items-center justify-center gap-1.5 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs text-slate-300 transition"
            @click="limparFiltros"
          >
            <RotateCcw class="w-3.5 h-3.5" />
            Limpar filtros
          </button>
        </div>

        <!-- Legenda -->
        <div class="mt-auto border-t border-slate-800 p-4 space-y-3 text-[11px]">
          <div>
            <p class="text-[10px] font-medium uppercase tracking-wide text-slate-500 mb-1.5">Tipos de ativo</p>
            <ul class="space-y-1">
              <li v-for="t in tiposLegenda" :key="t" class="flex items-center gap-2 text-slate-400">
                <span
                  class="w-3 h-3 rounded-sm shrink-0"
                  :style="{ background: estiloTipo(t === 'Outros' ? null : t).cor }"
                />
                {{ t }}
              </li>
            </ul>
          </div>
          <div>
            <p class="text-[10px] font-medium uppercase tracking-wide text-slate-500 mb-1.5">Vínculos</p>
            <ul class="space-y-1">
              <li
                v-for="(estiloRelItem, nomeRel) in { 'Depende de': PALETA_REL['Depende de'], 'Contém': PALETA_REL['Contém'], 'Conecta-se a': PALETA_REL['Conecta-se a'] }"
                :key="nomeRel"
                class="flex items-center gap-2 text-slate-400"
              >
                <svg class="w-5 h-2 shrink-0">
                  <line
                    x1="0" y1="4" x2="20" y2="4"
                    :stroke="estiloRelItem.cor"
                    :stroke-dasharray="estiloRelItem.estilo === 'dashed' ? '5 3' : estiloRelItem.estilo === 'dotted' ? '2 3' : undefined"
                    stroke-width="2.5"
                  />
                </svg>
                {{ nomeRel }}
              </li>
            </ul>
          </div>
        </div>
      </aside>

      <!-- ---------- Canvas ---------- -->
      <main class="flex-1 relative min-w-0">
        <div ref="container" class="absolute inset-0" />

        <div
          v-if="carregando"
          class="absolute top-4 left-1/2 -translate-x-1/2 inline-flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-900/90 border border-slate-700 text-xs text-slate-300 shadow-lg"
        >
          <RefreshCw class="w-3.5 h-3.5 animate-spin text-emerald-400" />
          Carregando grafo…
        </div>

        <div v-if="erro" class="absolute top-4 left-4 right-4 max-w-lg">
          <ErrorAlert :error="erro" />
        </div>

        <!-- Painel de detalhes -->
        <section
          v-if="selecionado"
          class="absolute top-4 right-4 w-72 max-h-[80%] overflow-y-auto rounded-xl bg-slate-900/95 border border-slate-700 shadow-xl backdrop-blur"
        >
          <header class="flex items-start gap-2 p-3 border-b border-slate-800">
            <MousePointerClick class="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
            <div class="min-w-0 flex-1">
              <p class="text-sm font-semibold text-slate-100 truncate">{{ selecionado.nome }}</p>
              <p class="text-[11px] text-slate-500">{{ selecionado.tipo ?? '—' }} · {{ selecionado.ambiente ?? '—' }}</p>
            </div>
            <button
              class="p-1 rounded hover:bg-slate-800 text-slate-500 hover:text-slate-300"
              title="Fechar"
              @click="limparSelecao"
            >
              <X class="w-4 h-4" />
            </button>
          </header>
          <dl class="p-3 space-y-1.5 text-[11px]">
            <div class="flex justify-between gap-2">
              <dt class="text-slate-500">Status</dt>
              <dd class="text-slate-300 truncate">{{ selecionado.status ?? '—' }}</dd>
            </div>
            <div class="flex justify-between gap-2">
              <dt class="text-slate-500">Criticidade</dt>
              <dd class="truncate" :class="selecionado.criticidade === 'Crítica' ? 'text-rose-400 font-semibold' : 'text-slate-300'">
                {{ selecionado.criticidade ?? '—' }}
              </dd>
            </div>
            <div class="flex justify-between gap-2">
              <dt class="text-slate-500">FQDN</dt>
              <dd class="text-slate-300 truncate" :title="selecionado.fqdn ?? ''">{{ selecionado.fqdn ?? '—' }}</dd>
            </div>
            <div class="flex justify-between gap-2">
              <dt class="text-slate-500">Conexões</dt>
              <dd class="text-emerald-400 font-semibold">{{ selecionado.grau }}</dd>
            </div>
            <div v-if="selecionado.descricao" class="pt-1.5 text-slate-400 leading-relaxed">
              {{ selecionado.descricao }}
            </div>
          </dl>
          <div class="border-t border-slate-800 p-3">
            <p class="text-[10px] font-medium uppercase tracking-wide text-slate-500 mb-1.5">
              Conexões ({{ vizinhos.length }})
            </p>
            <ul class="space-y-1 max-h-56 overflow-y-auto">
              <li v-for="(v, i) in vizinhos" :key="i">
                <button
                  class="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg hover:bg-slate-800/70 text-left"
                  @click="irPara(v.no.id)"
                >
                  <span class="w-2 h-2 rounded-full shrink-0" :style="{ background: estiloTipo(v.no.tipo).cor }" />
                  <span class="min-w-0 flex-1">
                    <span class="block text-[11px] text-slate-200 truncate">{{ v.no.nome }}</span>
                    <span class="block text-[10px] text-slate-500 truncate">
                      {{ v.aresta.tipo_nome ?? 'vínculo' }}
                      {{ v.aresta.origem_id === selecionado.id ? '→' : '←' }}
                    </span>
                  </span>
                </button>
              </li>
            </ul>
          </div>
        </section>

        <!-- Controles do canvas -->
        <div class="absolute bottom-4 left-4 flex flex-wrap items-center gap-1.5">
          <button class="p-2 rounded-lg bg-slate-900/90 border border-slate-700 text-slate-300 hover:text-emerald-400 hover:border-emerald-500/40 transition" title="Aproximar" @click="zoom(1.25)">
            <ZoomIn class="w-4 h-4" />
          </button>
          <button class="p-2 rounded-lg bg-slate-900/90 border border-slate-700 text-slate-300 hover:text-emerald-400 hover:border-emerald-500/40 transition" title="Afastar" @click="zoom(0.8)">
            <ZoomOut class="w-4 h-4" />
          </button>
          <button class="p-2 rounded-lg bg-slate-900/90 border border-slate-700 text-slate-300 hover:text-emerald-400 hover:border-emerald-500/40 transition" title="Centralizar" @click="ajustar">
            <Maximize2 class="w-4 h-4" />
          </button>
          <button
            class="p-2 rounded-lg border transition"
            :class="fisicaAtiva
              ? 'bg-emerald-600/20 border-emerald-500/40 text-emerald-400'
              : 'bg-slate-900/90 border-slate-700 text-slate-300 hover:text-emerald-400'"
            :title="fisicaAtiva ? 'Pausar simulação física' : 'Retomar simulação física'"
            @click="alternarFisica"
          >
            <Play v-if="!fisicaAtiva" class="w-4 h-4" />
            <Pause v-else class="w-4 h-4" />
          </button>
          <button
            class="p-2 rounded-lg border transition"
            :class="rotulosArestas
              ? 'bg-emerald-600/20 border-emerald-500/40 text-emerald-400'
              : 'bg-slate-900/90 border-slate-700 text-slate-300 hover:text-emerald-400'"
            title="Mostrar/ocultar rótulos dos vínculos"
            @click="alternarRotulos"
          >
            <Tag class="w-4 h-4" />
          </button>
          <button class="p-2 rounded-lg bg-slate-900/90 border border-slate-700 text-slate-300 hover:text-emerald-400 hover:border-emerald-500/40 transition" title="Exportar PNG" @click="baixarPng">
            <Download class="w-4 h-4" />
          </button>
        </div>
      </main>
    </div>
  </div>
</template>
