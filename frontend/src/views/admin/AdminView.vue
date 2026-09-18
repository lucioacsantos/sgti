<script setup lang="ts">
import { ref, onMounted, computed, watch } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { adminService, authService, type AdminUser, type ServiceToken, type TwoFASetup } from '@/services/auth.service'
import ErrorAlert from '@/components/ErrorAlert.vue'
import LoadingState from '@/components/LoadingState.vue'
import ConfirmDialog from '@/components/ConfirmDialog.vue'
import {
  Users, KeyRound, ShieldCheck, ShieldOff, RefreshCw, Plus, Copy, Check,
  Trash2, QrCode, Lock, X, ToggleLeft, ToggleRight, Loader2
} from 'lucide-vue-next'

const authStore = useAuthStore()

type TabKey = 'usuarios' | 'tokens' | 'twofa'

const activeTab = ref<TabKey>('usuarios')
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)
const successMessage = ref<string | null>(null)

// ===== Usuários =====
const users = ref<AdminUser[]>([])
const adUsers = computed(() => users.value.filter(u => !u.is_service_account))

// ===== Tokens =====
const tokens = ref<ServiceToken[]>([])
const isTokenModalOpen = ref(false)
const newTokenName = ref('')
const newTokenExpiry = ref('')
const isCreatingToken = ref(false)
const createdToken = ref<string | null>(null)
const copied = ref(false)
const toDeleteToken = ref<ServiceToken | null>(null)

// ===== Meu 2FA =====
const twoFASetup = ref<TwoFASetup | null>(null)
const verifyCode = ref('')
const isVerifying = ref(false)
const disablePassword = ref('')
const isDisabling2FA = ref(false)

// Toggle de usuário
const togglingUser = ref<number | null>(null)

// Reset de 2FA (suporte a usuário que perdeu o 2FA)
const toReset2FA = ref<AdminUser | null>(null)
const isResetting2FA = ref<number | null>(null)

const canAdmin = computed(() => authStore.isAdmin)

async function loadUsers() {
  isLoading.value = true
  errorMessage.value = null
  try {
    users.value = await adminService.users(0, 200)
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    isLoading.value = false
  }
}

async function loadTokens() {
  isLoading.value = true
  errorMessage.value = null
  try {
    tokens.value = await adminService.tokens()
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    isLoading.value = false
  }
}

watch(activeTab, (tab: TabKey) => {
  successMessage.value = null
  if (tab === 'usuarios') loadUsers()
  if (tab === 'tokens') loadTokens()
})

// ===== Toggle ativo/inativo =====
async function toggleUser(user: AdminUser) {
  togglingUser.value = user.id
  errorMessage.value = null
  try {
    const updated = await adminService.updateUser(user.id, { is_active: !user.is_active })
    const idx = users.value.findIndex(u => u.id === user.id)
    if (idx >= 0) users.value[idx] = updated
    successMessage.value = `Usuário ${updated.username} ${updated.is_active ? 'ativado' : 'desativado'}.`
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    togglingUser.value = null
  }
}

// ===== Tokens =====
function openTokenModal() {
  newTokenName.value = ''
  newTokenExpiry.value = ''
  createdToken.value = null
  isTokenModalOpen.value = true
}

async function createToken() {
  if (!newTokenName.value.trim()) return
  isCreatingToken.value = true
  errorMessage.value = null
  try {
    const result = await adminService.createToken(
      newTokenName.value.trim(),
      newTokenExpiry.value || undefined
    )
    createdToken.value = result.token || null
    await loadTokens()
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    isCreatingToken.value = false
  }
}

async function confirmDeleteToken() {
  if (!toDeleteToken.value) return
  try {
    await adminService.deleteToken(toDeleteToken.value.id)
    toDeleteToken.value = null
    successMessage.value = 'Token de serviço removido.'
    await loadTokens()
  } catch (err) {
    errorMessage.value = String(err)
  }
}

async function copyToken() {
  if (!createdToken.value) return
  await navigator.clipboard.writeText(createdToken.value)
  copied.value = true
  setTimeout(() => (copied.value = false), 2000)
}

// ===== Admin: zerar 2FA de usuário (suporte) =====
async function adminDisable2FA(user: AdminUser) {
  if (!toReset2FA.value) return
  isResetting2FA.value = user.id
  errorMessage.value = null
  try {
    await adminService.disableUser2FA(user.id)
    successMessage.value = `2FA zerado para ${user.username}. O usuário poderá refazer o setup em 'Meu 2FA' no próximo login.`
    await loadUsers()
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    isResetting2FA.value = null
    toReset2FA.value = null
  }
}

// ===== Meu 2FA =====
async function startSetup() {
  errorMessage.value = null
  try {
    twoFASetup.value = await authService.setup2FA()
    verifyCode.value = ''
  } catch (err) {
    errorMessage.value = String(err)
  }
}

async function verifySetup() {
  if (!verifyCode.value) return
  isVerifying.value = true
  errorMessage.value = null
  try {
    await authService.verify2FA(verifyCode.value)
    twoFASetup.value = null
    verifyCode.value = ''
    successMessage.value = '2FA habilitado com sucesso!'
    await authStore.syncUser()
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    isVerifying.value = false
  }
}

async function disableMy2FA() {
  if (!disablePassword.value) return
  isDisabling2FA.value = true
  errorMessage.value = null
  try {
    await authService.disable2FA(disablePassword.value)
    disablePassword.value = ''
    successMessage.value = '2FA desabilitado para sua conta.'
    await authStore.syncUser()
  } catch (err) {
    errorMessage.value = String(err)
  } finally {
    isDisabling2FA.value = false
  }
}

function fmtDate(iso?: string | null): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('pt-BR', { dateStyle: 'short', timeStyle: 'short' })
}

const tabs = [
  { key: 'usuarios' as TabKey, label: 'Usuários', icon: Users },
  { key: 'tokens' as TabKey, label: 'Tokens de Serviço', icon: KeyRound },
  { key: 'twofa' as TabKey, label: 'Meu 2FA', icon: ShieldCheck }
]

onMounted(loadUsers)
</script>

<template>
  <div class="space-y-6">
    <!-- Cabeçalho -->
    <div class="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
      <div>
        <h2 class="text-lg font-bold text-slate-100 flex items-center gap-2">
          <ShieldCheck class="w-5 h-5 text-emerald-400" />
          Administração
        </h2>
        <p class="text-xs text-slate-400 mt-0.5">
          Gestão de usuários AD, tokens de automação e autenticação em dois fatores.
        </p>
      </div>
      <span
        v-if="!canAdmin"
        class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium bg-amber-500/10 text-amber-400 border border-amber-500/20"
      >
        <Lock class="w-3.5 h-3.5" />
        Ações restritas exigem perfil admin
      </span>
    </div>

    <ErrorAlert :error="errorMessage" />

    <!-- Sucesso -->
    <div v-if="successMessage" class="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-lg flex items-center gap-2 text-emerald-400 text-xs">
      <Check class="w-4 h-4 shrink-0" />
      <span>{{ successMessage }}</span>
    </div>

    <!-- Abas -->
    <div class="flex border-b border-slate-800 overflow-x-auto">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        @click="activeTab = tab.key"
        class="px-4 py-3 text-xs font-semibold whitespace-nowrap border-b-2 transition-colors flex items-center gap-2"
        :class="activeTab === tab.key
          ? 'border-emerald-500 text-emerald-400 bg-slate-950/40'
          : 'border-transparent text-slate-400 hover:text-slate-200 hover:border-slate-700'"
      >
        <component :is="tab.icon" class="w-3.5 h-3.5" />
        {{ tab.label }}
      </button>
    </div>

    <!-- ===== USUÁRIOS ===== -->
    <div v-if="activeTab === 'usuarios'" class="space-y-6">
      <div class="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div class="px-4 py-3 border-b border-slate-800 bg-slate-900/50 flex items-center justify-between">
          <h3 class="text-xs font-bold uppercase tracking-wider text-slate-300">Usuários AD</h3>
          <button @click="loadUsers" :disabled="isLoading" class="text-slate-400 hover:text-slate-100">
            <RefreshCw class="w-3.5 h-3.5" :class="{ 'animate-spin': isLoading }" />
          </button>
        </div>

        <LoadingState v-if="isLoading" />

        <table v-else class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
              <th class="p-3 pl-4">Usuário</th>
              <th class="p-3">Perfis</th>
              <th class="p-3 text-center">2FA</th>
              <th class="p-3 text-center">Situação</th>
              <th class="p-3 pr-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="adUsers.length === 0">
              <td colspan="5" class="p-8 text-center text-slate-500">Nenhum usuário AD registrado.</td>
            </tr>
            <tr v-for="user in adUsers" :key="user.id" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4">
                <div class="font-medium text-slate-100 font-mono">{{ user.username }}</div>
                <div class="text-[10px] text-slate-500">{{ user.email }}</div>
              </td>
              <td class="p-3">
                <div class="flex flex-wrap gap-1">
                  <span
                    v-for="role in user.roles"
                    :key="role"
                    class="text-[10px] font-medium px-1.5 py-0.5 rounded bg-indigo-500/10 text-indigo-300 border border-indigo-500/20"
                  >
                    {{ role }}
                  </span>
                </div>
              </td>
              <td class="p-3 text-center">
                <span
                  class="inline-flex items-center gap-1 text-[10px] font-medium"
                  :class="user.two_fa_enabled ? 'text-emerald-400' : 'text-slate-500'"
                >
                  <ShieldCheck v-if="user.two_fa_enabled" class="w-3.5 h-3.5" />
                  <ShieldOff v-else class="w-3.5 h-3.5" />
                  {{ user.two_fa_enabled ? 'ativo' : 'inativo' }}
                </span>
              </td>
              <td class="p-3 text-center">
                <button
                  v-if="canAdmin"
                  @click="toggleUser(user)"
                  :disabled="togglingUser === user.id"
                  class="inline-flex items-center gap-1.5 px-2 py-1 rounded text-[10px] font-medium transition-colors"
                  :class="user.is_active
                    ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 hover:bg-emerald-500/20'
                    : 'bg-slate-800 text-slate-400 border border-slate-700 hover:bg-slate-700'"
                >
                  <component :is="user.is_active ? ToggleRight : ToggleLeft" class="w-3.5 h-3.5" />
                  {{ user.is_active ? 'ativo' : 'inativo' }}
                </button>
                <span v-else class="text-[10px]" :class="user.is_active ? 'text-emerald-400' : 'text-slate-500'">
                  {{ user.is_active ? 'ativo' : 'inativo' }}
                </span>
              </td>
              <td class="p-3 pr-4 text-right">
                <button
                  v-if="canAdmin && user.two_fa_enabled"
                  @click="toReset2FA = user"
                  :disabled="isResetting2FA === user.id"
                  class="p-1.5 hover:bg-rose-500/10 rounded text-slate-400 hover:text-rose-400 transition-colors disabled:opacity-50"
                  title="Zerar 2FA deste usuário (suporte)"
                >
                  <Loader2 v-if="isResetting2FA === user.id" class="w-3.5 h-3.5 animate-spin" />
                  <ShieldOff v-else class="w-3.5 h-3.5" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ===== TOKENS ===== -->
    <div v-if="activeTab === 'tokens'" class="space-y-6">
      <div class="flex justify-end">
        <button
          v-if="canAdmin"
          @click="openTokenModal"
          class="inline-flex items-center gap-2 px-3.5 py-2 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-semibold text-xs rounded-lg transition-colors shadow-sm"
        >
          <Plus class="w-4 h-4" />
          Novo Token
        </button>
      </div>

      <div class="bg-slate-950 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div class="px-4 py-3 border-b border-slate-800 bg-slate-900/50">
          <h3 class="text-xs font-bold uppercase tracking-wider text-slate-300">
            Tokens de Automação (X-Service-Token)
          </h3>
          <p class="text-[10px] text-slate-500 mt-0.5">
            Usados por automações para provisionar ativos, IPs e dados de infraestrutura via API.
          </p>
        </div>

        <LoadingState v-if="isLoading" />

        <table v-else class="w-full text-left border-collapse text-xs">
          <thead>
            <tr class="border-b border-slate-800 text-slate-400 font-semibold uppercase tracking-wider">
              <th class="p-3 pl-4">Nome</th>
              <th class="p-3">Criado em</th>
              <th class="p-3">Expira em</th>
              <th class="p-3 text-center">Situação</th>
              <th class="p-3 pr-4 text-right">Ações</th>
            </tr>
          </thead>
          <tbody class="divide-y divide-slate-800/60 text-slate-300">
            <tr v-if="tokens.length === 0">
              <td colspan="5" class="p-8 text-center text-slate-500">Nenhum token de serviço cadastrado.</td>
            </tr>
            <tr v-for="tok in tokens" :key="tok.id" class="hover:bg-slate-900/40 transition-colors">
              <td class="p-3 pl-4 font-medium text-slate-100 font-mono">{{ tok.name }}</td>
              <td class="p-3 text-slate-400 font-mono">{{ fmtDate(tok.created_at) }}</td>
              <td class="p-3 font-mono" :class="new Date(tok.expires_at || '') < new Date() ? 'text-rose-400' : 'text-slate-400'">
                {{ fmtDate(tok.expires_at) }}
              </td>
              <td class="p-3 text-center">
                <span
                  class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-medium border"
                  :class="tok.is_active ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-slate-800 text-slate-400 border-slate-700'"
                >
                  {{ tok.is_active ? 'ativo' : 'inativo' }}
                </span>
              </td>
              <td class="p-3 pr-4 text-right">
                <button
                  v-if="canAdmin"
                  @click="toDeleteToken = tok"
                  class="p-1.5 hover:bg-rose-500/10 rounded text-slate-400 hover:text-rose-400 transition-colors"
                  title="Revogar token"
                >
                  <Trash2 class="w-3.5 h-3.5" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ===== MEU 2FA ===== -->
    <div v-if="activeTab === 'twofa'" class="max-w-xl space-y-6">
      <div class="bg-slate-950 border border-slate-800 rounded-xl p-6">
        <h3 class="text-sm font-bold text-slate-100 flex items-center gap-2">
          <ShieldCheck class="w-4 h-4 text-emerald-400" />
          Autenticação em Dois Fatores (TOTP)
        </h3>
        <p class="text-xs text-slate-400 mt-1 leading-relaxed">
          Proteja sua conta exigindo um código do aplicativo autenticador (Google Authenticator, Authy...) além da senha.
        </p>

        <div class="mt-4 flex items-center gap-2">
          <span
            class="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium border"
            :class="authStore.user?.two_fa_enabled
              ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
              : 'bg-slate-800 text-slate-400 border-slate-700'"
          >
            <ShieldCheck v-if="authStore.user?.two_fa_enabled" class="w-3.5 h-3.5" />
            <ShieldOff v-else class="w-3.5 h-3.5" />
            {{ authStore.user?.two_fa_enabled ? '2FA habilitado' : '2FA desabilitado' }}
          </span>
        </div>

        <!-- Habilitar -->
        <div v-if="!authStore.user?.two_fa_enabled" class="mt-6">
          <button
            v-if="!twoFASetup"
            @click="startSetup"
            class="inline-flex items-center gap-2 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-semibold text-xs rounded-lg transition-colors"
          >
            <QrCode class="w-4 h-4" />
            Gerar QR Code
          </button>

          <div v-else class="space-y-4">
            <div class="flex flex-col sm:flex-row gap-5 items-start">
              <img
                :src="twoFASetup.qr_code"
                alt="QR Code 2FA"
                class="w-44 h-44 rounded-lg border-4 border-white bg-white"
              />
              <div class="text-xs space-y-2">
                <p class="text-slate-300 leading-relaxed">
                  Escaneie com seu aplicativo autenticador e informe o código de 6 dígitos:
                </p>
                <div class="p-2 bg-slate-900 border border-slate-800 rounded font-mono text-[10px] text-slate-400 break-all">
                  {{ twoFASetup.secret }}
                </div>
              </div>
            </div>

            <div class="flex gap-2">
              <input
                v-model="verifyCode"
                type="text"
                inputmode="numeric"
                maxlength="6"
                placeholder="000000"
                class="w-32 px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono tracking-widest text-center focus:outline-none focus:border-emerald-500"
              />
              <button
                @click="verifySetup"
                :disabled="isVerifying || verifyCode.length !== 6"
                class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-semibold text-xs transition-colors disabled:opacity-50"
              >
                <Lock class="w-3.5 h-3.5" />
                Confirmar e habilitar
              </button>
              <button
                @click="twoFASetup = null"
                class="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 text-xs font-medium transition-colors"
              >
                Cancelar
              </button>
            </div>
          </div>
        </div>

        <!-- Desabilitar -->
        <div v-else class="mt-6 pt-6 border-t border-slate-800">
          <p class="text-xs text-slate-400 mb-3">
            Para desabilitar, confirme sua senha de rede:
          </p>
          <div class="flex gap-2">
            <div class="relative flex-1">
              <Lock class="w-3.5 h-3.5 text-slate-500 absolute left-3 top-2.5 pointer-events-none" />
              <input
                v-model="disablePassword"
                type="password"
                placeholder="Senha atual"
                class="w-full pl-9 pr-4 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder-slate-600 focus:outline-none focus:border-rose-500"
              />
            </div>
            <button
              @click="disableMy2FA"
              :disabled="isDisabling2FA || !disablePassword"
              class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-rose-600 hover:bg-rose-500 text-white font-semibold text-xs transition-colors disabled:opacity-50"
            >
              <ShieldOff class="w-3.5 h-3.5" />
              Desabilitar 2FA
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- Modal: criar token -->
    <div v-if="isTokenModalOpen" class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
      <div class="w-full max-w-md bg-slate-900 border border-slate-800 rounded-xl p-6 shadow-2xl">
        <div class="flex items-center justify-between pb-4 mb-4 border-b border-slate-800">
          <h3 class="text-sm font-bold text-slate-100">Novo Token de Serviço</h3>
          <button @click="isTokenModalOpen = false" class="text-slate-500 hover:text-slate-300">
            <X class="w-4 h-4" />
          </button>
        </div>

        <!-- Token criado -->
        <div v-if="createdToken" class="space-y-4">
          <div class="p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg flex items-start gap-2 text-amber-400 text-xs">
            <KeyRound class="w-4 h-4 shrink-0 mt-0.5" />
            <span>Copie agora: este token <strong>não será exibido novamente</strong>.</span>
          </div>

          <div class="p-3 bg-slate-950 border border-slate-800 rounded-lg font-mono text-xs text-emerald-300 break-all select-all">
            {{ createdToken }}
          </div>

          <div class="flex justify-end gap-2">
            <button
              @click="copyToken"
              class="inline-flex items-center gap-1.5 px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium transition-colors"
            >
              <component :is="copied ? Check : Copy" class="w-3.5 h-3.5" />
              {{ copied ? 'Copiado' : 'Copiar' }}
            </button>
            <button
              @click="isTokenModalOpen = false"
              class="px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 text-xs font-semibold transition-colors"
            >
              Concluir
            </button>
          </div>
        </div>

        <!-- Formulário -->
        <form v-else @submit.prevent="createToken" class="space-y-4 text-xs">
          <div>
            <label class="block font-medium text-slate-300 mb-1">Nome da conta de automação *</label>
            <input
              v-model="newTokenName"
              type="text"
              required
              placeholder="ex: zabbix-sync, ansible-provision"
              class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 font-mono focus:outline-none focus:border-emerald-500"
            />
          </div>

          <div>
            <label class="block font-medium text-slate-300 mb-1">Expira em (opcional)</label>
            <input
              v-model="newTokenExpiry"
              type="datetime-local"
              class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-200 focus:outline-none focus:border-emerald-500"
            />
            <p class="text-[10px] text-slate-500 mt-1">Em branco = válido por 1 ano.</p>
          </div>

          <div class="flex items-center justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              @click="isTokenModalOpen = false"
              class="px-3 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium transition-colors"
            >
              Cancelar
            </button>
            <button
              type="submit"
              :disabled="isCreatingToken || !newTokenName.trim()"
              class="inline-flex items-center gap-1.5 px-4 py-2 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-slate-950 font-semibold transition-colors disabled:opacity-50"
            >
              <Loader2 v-if="isCreatingToken" class="w-3.5 h-3.5 animate-spin" />
              <KeyRound v-else class="w-3.5 h-3.5" />
              Gerar Token
            </button>
          </div>
        </form>
      </div>
    </div>

    <!-- Confirmação: revogar token -->
    <ConfirmDialog
      v-if="toDeleteToken"
      title="Revogar token de serviço"
      :message="`A automação '${toDeleteToken.name}' perderá acesso imediato à API. Esta ação não pode ser desfeita.`"
      confirm-label="Revogar"
      danger
      @confirm="confirmDeleteToken"
      @cancel="toDeleteToken = null"
    />

    <!-- Confirmação: zerar 2FA de usuário -->
    <ConfirmDialog
      v-if="toReset2FA"
      title="Zerar 2FA do usuário"
      :message="`O 2FA de '${toReset2FA.username}' será removido e o segredo apagado. Use apenas para suporte (usuário perdeu o autenticador). No próximo login, o usuário deverá refazer o setup em 'Meu 2FA'. Esta ação não pode ser desfeita.`"
      confirm-label="Zerar 2FA"
      danger
      @confirm="adminDisable2FA(toReset2FA)"
      @cancel="toReset2FA = null"
    />
  </div>
</template>