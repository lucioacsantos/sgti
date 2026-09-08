<template>
  <div class="assets-view">
    <header class="header">
      <h1>Assets</h1>
      <button class="btn btn-primary" @click="abrirModalCriacao">
        + Novo Ativo
      </button>
    </header>

    <!-- Feedback de Erro -->
    <div v-if="mensagemErro" class="alert alert-error">
      {{ mensagemErro }}
    </div>

    <!-- Tabela de Ativos -->
    <div class="table-container">
      <div v-if="carregando" class="loading">Carregando ativos...</div>

      <table v-else class="table">
        <thead>
          <tr>
            <th>ID</th>
            <th>Nome</th>
            <th class="text-right">Ações</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="ativo in ativos" :key="ativo.id">
            <td>{{ ativo.id }}</td>
            <td><strong>{{ ativo.nome }}</strong></td>
            <td class="actions text-right">
              <button class="btn btn-sm btn-secondary" @click="abrirModalEdicao(ativo)">
                Editar
              </button>
              <button class="btn btn-sm btn-danger" @click="removerAtivo(ativo.nome)">
                Excluir
              </button>
            </td>
          </tr>
          <tr v-if="ativos.length === 0">
            <td colspan="3" class="empty">Nenhum ativo cadastrado.</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Modal Form (Criar / Editar) -->
    <div v-if="modalAberto" class="modal-backdrop">
      <div class="modal">
        <h3>{{ emEdicao ? 'Editar Ativo' : 'Novo Ativo' }}</h3>

        <form @submit.prevent="salvarAtivo">
          <div class="form-group">
            <label for="nome">Nome do Ativo</label>
            <input
              id="nome"
              v-model="form.nome"
              type="text"
              class="form-control"
              required
              placeholder="Ex: Servidor-DB-01"
            />
          </div>

          <div class="modal-actions">
            <button type="button" class="btn btn-secondary" @click="fecharModal">
              Cancelar
            </button>
            <button type="submit" class="btn btn-primary" :disabled="salvando">
              {{ salvando ? 'Salvando...' : 'Salvar' }}
            </button>
          </div>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import axios from 'axios'

const API_BASE = '/ativos'

const ativos = ref([])
const carregando = ref(false)
const salvando = ref(false)
const mensagemErro = ref('')

const modalAberto = ref(false)
const emEdicao = ref(false)
const nomeOriginal = ref('')

const form = ref({
  nome: ''
})

async function carregarAtivos() {
  carregando.value = true
  mensagemErro.value = ''
  try {
    const { data } = await axios.get(API_BASE, { params: { limit: 100 } })
    ativos.value = data
  } catch (err) {
    mensagemErro.value = err.response?.data?.detail || 'Erro ao carregar lista de ativos.'
  } finally {
    carregando.value = false
  }
}

function abrirModalCriacao() {
  emEdicao.value = false
  nomeOriginal.value = ''
  form.value = { nome: '' }
  modalAberto.value = true
}

function abrirModalEdicao(ativo) {
  emEdicao.value = true
  nomeOriginal.value = ativo.nome
  form.value = { ...ativo }
  modalAberto.value = true
}

function fecharModal() {
  modalAberto.value = false
  form.value = { nome: '' }
}

async function salvarAtivo() {
  salvando.value = true
  mensagemErro.value = ''
  try {
    if (emEdicao.value) {
      await axios.put(`${API_BASE}/${encodeURIComponent(nomeOriginal.value)}`, form.value)
    } else {
      await axios.post(API_BASE, form.value)
    }
    fecharModal()
    await carregarAtivos()
  } catch (err) {
    mensagemErro.value = err.response?.data?.detail || 'Erro ao salvar o ativo.'
  } finally {
    salvando.value = false
  }
}

async function removerAtivo(nome) {
  if (!confirm(`Deseja realmente remover o ativo "${nome}"?`)) return

  try {
    await axios.delete(`${API_BASE}/${encodeURIComponent(nome)}`)
    await carregarAtivos()
  } catch (err) {
    mensagemErro.value = err.response?.data?.detail || 'Erro ao excluir o ativo.'
  }
}

onMounted(() => {
  carregarAtivos()
})
</script>

<style scoped>

/* Regras pontuais de posicionamento da tela */
.header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1.5rem;
}

.actions {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
}

.text-right {
  text-align: right;
}

.modal-backdrop {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 50;
}

.modal {
  background: #ffffff;
  padding: 1.5rem;
  border-radius: 8px;
  width: 100%;
  max-width: 420px;
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1.25rem;
}
</style>