<script setup lang="ts">
import { ref, nextTick, onMounted } from 'vue'
import { aiService } from '@/services/cmdb.services'
import type { TrechoCitado, OllamaModelo } from '@/services/cmdb'
import ErrorAlert from '@/components/ErrorAlert.vue'
import {
  Bot, Send, Trash2, FileText, ChevronDown, ChevronUp, Sparkles, User
} from 'lucide-vue-next'

interface Mensagem {
  papel: 'usuario' | 'ia'
  texto: string
  trechos?: TrechoCitado[]
  erro?: boolean
}

const mensagens = ref<Mensagem[]>([])
const perguntaInput = ref('')
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)
const chatContainer = ref<HTMLElement | null>(null)
const modelos = ref<OllamaModelo[]>([])
const chatModel = ref<string>('')

// Modelos de embedding não servem para chat (ex.: nomic-embed-text, mxbai-embed, bge, all-minilm, snowflake-arctic-embed)
const EMBED_MODEL_RE = /embed|minilm|bge-|e5-|arctic-embed/i

const sugestoes = [
  'Qual o procedimento para disco cheio em servidor Linux?',
  'Como escalar um incidente crítico?',
  'O que fazer quando um serviço está down no Zabbix?',
  'Qual o passo a passo para alta utilização de CPU?'
]

async function enviar(texto?: string) {
  const pergunta = (texto ?? perguntaInput.value).trim()
  if (!pergunta || isLoading.value) return

  perguntaInput.value = ''
  mensagens.value.push({ papel: 'usuario', texto: pergunta })
  await rolarParaFim()

  isLoading.value = true
  errorMessage.value = null
  const indiceIA = mensagens.value.push({
    papel: 'ia',
    texto: '',
    trechos: undefined
  }) - 1
  try {
    await aiService.perguntarStream(
      {
        pergunta,
        chat_model: chatModel.value || undefined
      },
      {
        onStart: (trechos) => {
          mensagens.value[indiceIA].trechos = trechos
        },
        onChunk: (texto) => {
          mensagens.value[indiceIA].texto += texto
          rolarParaFim()
        },
        onError: (detail) => {
          mensagens.value[indiceIA].texto = detail
          mensagens.value[indiceIA].erro = true
        }
      }
    )
    if (!mensagens.value[indiceIA].texto && !mensagens.value[indiceIA].erro) {
      mensagens.value[indiceIA].texto = 'O assistente não retornou conteúdo.'
      mensagens.value[indiceIA].erro = true
    }
  } catch (err) {
    mensagens.value[indiceIA].texto = typeof err === 'string' ? err : (err as Error)?.message || 'Falha ao consultar o assistente de IA.'
    mensagens.value[indiceIA].erro = true
  } finally {
    isLoading.value = false
    await rolarParaFim()
  }
}

async function rolarParaFim() {
  await nextTick()
  if (chatContainer.value) {
    chatContainer.value.scrollTop = chatContainer.value.scrollHeight
  }
}

function limpar() {
  mensagens.value = []
  errorMessage.value = null
}

const trechoAberto = ref<Record<string, boolean>>({})

function toggleTrecho(key: string) {
  trechoAberto.value[key] = !trechoAberto.value[key]
}

async function loadModelos() {
  try {
    const todos = await aiService.modelos()
    modelos.value = todos.filter((m) => !EMBED_MODEL_RE.test(m.name))
    if (modelos.value.length > 0 && !chatModel.value) {
      chatModel.value = modelos.value[0].name
    }
  } catch {
    // modelos são opcionais: usa o default do backend
  }
}

onMounted(loadModelos)
</script>

<template>
  <div class="flex flex-col h-full max-h-full gap-4">
    <!-- Cabeçalho -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
      <div>
        <h2 class="text-lg font-bold text-slate-100 flex items-center gap-2">
          <Bot class="w-5 h-5 text-sky-400" />
          Assistente IA (Ollama)
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">
          Pergunte em linguagem natural — as respostas são baseadas nos procedimentos da base de conhecimento indexada.
        </p>
      </div>
      <div class="flex items-center gap-2">
        <select
          v-model="chatModel"
          class="px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-sky-500 transition-colors"
          title="Modelo de chat do Ollama"
        >
          <option v-if="modelos.length === 0" value="">Modelo padrão</option>
          <option v-for="m in modelos" :key="m.name" :value="m.name">{{ m.name }}</option>
        </select>
        <span v-if="modelos.length === 0" class="text-[10px] text-slate-500" title="Somente modelos de embedding disponíveis">só embeddings</span>
        <button
          @click="limpar"
          :disabled="mensagens.length === 0 || isLoading"
          class="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold text-xs rounded-lg transition-colors disabled:opacity-50"
        >
          <Trash2 class="w-3.5 h-3.5" />
          Limpar
        </button>
      </div>
    </div>

    <ErrorAlert :error="errorMessage" />

    <!-- Área do chat -->
    <div
      ref="chatContainer"
      class="flex-1 min-h-0 overflow-y-auto bg-slate-950 border border-slate-800 rounded-xl p-5 space-y-4"
    >
      <!-- Estado vazio -->
      <div v-if="mensagens.length === 0 && !isLoading" class="h-full flex flex-col items-center justify-center text-center gap-4 py-10">
        <div class="p-4 rounded-2xl bg-sky-500/10 border border-sky-500/20">
          <Sparkles class="w-8 h-8 text-sky-400" />
        </div>
        <div>
          <p class="text-sm font-semibold text-slate-200">Assistente de Procedimentos SGTI</p>
          <p class="text-xs text-slate-500 mt-1 max-w-md">
            Faça uma pergunta sobre os procedimentos operacionais documentados. O assistente busca os trechos
            relevantes e responde em linguagem natural, citando os documentos usados.
          </p>
        </div>
        <div class="flex flex-wrap justify-center gap-2 max-w-xl">
          <button
            v-for="s in sugestoes"
            :key="s"
            @click="enviar(s)"
            class="px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-sky-500/40 text-[11px] text-slate-300 hover:text-sky-300 rounded-full transition-colors"
          >
            {{ s }}
          </button>
        </div>
      </div>

      <!-- Mensagens -->
      <template v-for="(msg, i) in mensagens" :key="i">
        <!-- Usuário -->
        <div v-if="msg.papel === 'usuario'" class="flex justify-end">
          <div class="flex items-start gap-2.5 max-w-[85%]">
            <div class="px-4 py-2.5 bg-emerald-600/20 border border-emerald-500/30 rounded-xl rounded-tr-sm text-xs text-slate-100 leading-relaxed whitespace-pre-wrap">
              {{ msg.texto }}
            </div>
            <div class="p-1.5 rounded-lg bg-slate-800 shrink-0">
              <User class="w-3.5 h-3.5 text-slate-400" />
            </div>
          </div>
        </div>

        <!-- IA -->
        <div v-else class="flex justify-start">
          <div class="flex items-start gap-2.5 max-w-[85%]">
            <div class="p-1.5 rounded-lg bg-sky-500/10 border border-sky-500/20 shrink-0">
              <Bot class="w-3.5 h-3.5 text-sky-400" />
            </div>
            <div class="space-y-2 min-w-0">
              <div
                class="px-4 py-2.5 rounded-xl rounded-tl-sm text-xs leading-relaxed whitespace-pre-wrap border"
                :class="msg.erro ? 'bg-rose-500/10 border-rose-500/30 text-rose-300' : 'bg-slate-900/70 border-slate-800 text-slate-200'"
              >
                {{ msg.texto }}
              </div>

              <!-- Fontes citadas -->
              <div v-if="msg.trechos && msg.trechos.length > 0" class="space-y-1.5">
                <p class="text-[10px] uppercase tracking-wider text-slate-500 font-semibold">
                  Fontes ({{ msg.trechos.length }})
                </p>
                <div
                  v-for="(trecho, j) in msg.trechos"
                  :key="j"
                  class="bg-slate-900/50 border border-slate-800 rounded-lg overflow-hidden"
                >
                  <button
                    @click="toggleTrecho(`${i}-${j}`)"
                    class="w-full flex items-center justify-between gap-2 px-3 py-2 hover:bg-slate-900 transition-colors text-left"
                  >
                    <span class="flex items-center gap-2 min-w-0">
                      <FileText class="w-3 h-3 text-amber-400 shrink-0" />
                      <span class="text-[11px] text-slate-300 truncate">{{ trecho.documento }}</span>
                      <span v-if="trecho.titulo_secao" class="text-[10px] text-slate-500 truncate">· {{ trecho.titulo_secao }}</span>
                    </span>
                    <span class="flex items-center gap-2 shrink-0">
                      <span class="text-[10px] font-mono text-slate-500">{{ (trecho.score * 100).toFixed(0) }}%</span>
                      <ChevronUp v-if="trechoAberto[`${i}-${j}`]" class="w-3 h-3 text-slate-500" />
                      <ChevronDown v-else class="w-3 h-3 text-slate-500" />
                    </span>
                  </button>
                  <pre
                    v-if="trechoAberto[`${i}-${j}`]"
                    class="px-3 py-2.5 text-[10px] text-slate-400 bg-slate-950 border-t border-slate-800 overflow-x-auto whitespace-pre-wrap font-mono max-h-64 overflow-y-auto"
                  >{{ trecho.conteudo }}</pre>
                </div>
              </div>
            </div>
          </div>
        </div>
      </template>

      <!-- Indicador de digitação -->
      <div v-if="isLoading" class="flex justify-start">
        <div class="flex items-center gap-2.5">
          <div class="p-1.5 rounded-lg bg-sky-500/10 border border-sky-500/20">
            <Bot class="w-3.5 h-3.5 text-sky-400 animate-pulse" />
          </div>
          <div class="px-4 py-3 bg-slate-900/70 border border-slate-800 rounded-xl rounded-tl-sm flex items-center gap-1.5">
            <span class="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style="animation-delay: 0ms" />
            <span class="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style="animation-delay: 150ms" />
            <span class="w-1.5 h-1.5 bg-slate-500 rounded-full animate-bounce" style="animation-delay: 300ms" />
            <span class="text-[10px] text-slate-500 ml-1">consultando procedimentos...</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Entrada -->
    <form @submit.prevent="enviar()" class="flex items-end gap-2">
      <textarea
        v-model="perguntaInput"
        rows="2"
        placeholder="Digite sua pergunta sobre procedimentos... (Enter para enviar)"
        class="flex-1 px-4 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-sky-500 transition-colors resize-none"
        @keydown.enter.exact.prevent="enviar()"
      />
      <button
        type="submit"
        :disabled="!perguntaInput.trim() || isLoading"
        class="inline-flex items-center gap-2 px-4 py-2.5 bg-sky-600 hover:bg-sky-500 text-white font-semibold text-xs rounded-lg transition-colors disabled:opacity-40 disabled:pointer-events-none shrink-0"
      >
        <Send class="w-4 h-4" />
        Perguntar
      </button>
    </form>
    <p class="text-[10px] text-slate-600 text-center -mt-2">
      As respostas são geradas por IA a partir da base de conhecimento indexada. Sempre confira o procedimento original antes de agir.
    </p>
  </div>
</template>