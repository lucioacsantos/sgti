<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { Lock, User, ShieldCheck, AlertCircle, Loader2, Smartphone, ArrowLeft } from 'lucide-vue-next'

const router = useRouter()
const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)

// Etapa 2FA
const step = ref<'credentials' | 'twofa'>('credentials')
const twoFACode = ref('')

async function handleSubmit() {
  if (!username.value || !password.value) {
    errorMessage.value = 'Informe usuário e senha para prosseguir.'
    return
  }

  errorMessage.value = null
  isLoading.value = true

  try {
    await authStore.login(username.value, password.value)
    if (authStore.requires2FA) {
      step.value = 'twofa'
      twoFACode.value = ''
      password.value = ''
      return
    }
    router.push({ name: 'dashboard' })
  } catch (error: any) {
    errorMessage.value = typeof error === 'string'
      ? error
      : error?.response?.data?.detail || 'Falha na autenticação. Verifique suas credenciais e a conexão.'
  } finally {
    isLoading.value = false
  }
}

async function handleVerify2FA() {
  const code = twoFACode.value.trim()
  if (!code || code.length < 6) {
    errorMessage.value = 'Informe o código de 6 dígitos do seu app autenticador.'
    return
  }

  errorMessage.value = null
  isLoading.value = true

  try {
    await authStore.verify2FALogin(code)
    router.push({ name: 'dashboard' })
  } catch (error: any) {
    twoFACode.value = ''
    errorMessage.value = typeof error === 'string'
      ? error
      : error?.response?.data?.detail || 'Código 2FA inválido ou expirado. Tente novamente.'
  } finally {
    isLoading.value = false
  }
}

function backToCredentials() {
  authStore.cancel2FA()
  step.value = 'credentials'
  twoFACode.value = ''
  errorMessage.value = null
}
</script>

<template>
  <div class="min-h-screen bg-slate-950 flex flex-col justify-center items-center px-4 relative overflow-hidden">
    <!-- Background Grid Pattern -->
    <div class="absolute inset-0 bg-[linear-gradient(to_right,#1e293b_1px,transparent_1px),linear-gradient(to_bottom,#1e293b_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_50%,#000_70%,transparent_100%)] opacity-30" />

    <div class="w-full max-w-md z-10">
      <!-- Card Container -->
      <div class="bg-slate-900 border border-slate-800 rounded-xl p-8 shadow-2xl backdrop-blur-sm">

        <!-- Header -->
        <div class="flex flex-col items-center mb-8">
          <div class="h-12 w-12 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center mb-3">
            <ShieldCheck class="w-6 h-6 text-emerald-400" />
          </div>
          <h2 class="text-xl font-bold tracking-wide text-slate-100">Controle de Acesso</h2>
          <p class="text-xs text-slate-400 mt-1">CMDB ::: Painel Administrativo de Ativos e Infraestrutura</p>
        </div>

        <!-- Feedback de Erro -->
        <div
          v-if="errorMessage"
          class="mb-6 p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-start gap-2.5 text-rose-400 text-xs leading-relaxed"
        >
          <AlertCircle class="w-4 h-4 shrink-0 mt-0.5" />
          <span>{{ errorMessage }}</span>
        </div>

        <!-- Form: Credenciais -->
        <form v-if="step === 'credentials'" @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Usuário de Rede (sAMAccountName)
            </label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                <User class="w-4 h-4" />
              </div>
              <input
                v-model="username"
                type="text"
                autocomplete="username"
                required
                placeholder="ex: usuario.adm"
                class="w-full pl-9 pr-4 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 transition-colors font-mono"
              />
            </div>
          </div>

          <div>
            <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Senha de Acesso
            </label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                <Lock class="w-4 h-4" />
              </div>
              <input
                v-model="password"
                type="password"
                autocomplete="current-password"
                required
                placeholder="••••••••••••"
                class="w-full pl-9 pr-4 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-sm text-slate-100 placeholder-slate-600 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 transition-colors"
              />
            </div>
          </div>

          <button
            type="submit"
            :disabled="isLoading"
            class="w-full mt-2 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800/50 disabled:cursor-not-allowed text-slate-950 font-semibold text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            <Loader2 v-if="isLoading" class="w-4 h-4 animate-spin text-slate-950" />
            <span>{{ isLoading ? 'Autenticando...' : 'Entrar no Sistema' }}</span>
          </button>
        </form>

        <!-- Form: Verificação 2FA (TOTP) -->
        <form v-else @submit.prevent="handleVerify2FA" class="space-y-4">
          <div class="flex items-center gap-3 p-3 bg-emerald-500/5 border border-emerald-500/20 rounded-lg">
            <div class="h-9 w-9 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center shrink-0">
              <Smartphone class="w-4.5 h-4.5 text-emerald-400" />
            </div>
            <div class="text-xs leading-relaxed text-slate-300">
              <p class="font-semibold text-emerald-400">Verificação em duas etapas</p>
              <p class="text-slate-400 mt-0.5">
                Digite o código de 6 dígitos gerado no app autenticador
                <span v-if="authStore.pending2FAUser" class="text-slate-300">
                  da conta <span class="font-mono text-emerald-400">{{ authStore.pending2FAUser.display_name }}</span></span>.
              </p>
            </div>
          </div>

          <div>
            <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              Código de Verificação (TOTP)
            </label>
            <div class="relative">
              <div class="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-500">
                <ShieldCheck class="w-4 h-4" />
              </div>
              <input
                v-model="twoFACode"
                type="text"
                inputmode="numeric"
                autocomplete="one-time-code"
                maxlength="6"
                required
                placeholder="000000"
                class="w-full pl-9 pr-4 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-lg tracking-[0.5em] text-center text-slate-100 placeholder-slate-700 focus:outline-none focus:ring-1 focus:ring-emerald-500 focus:border-emerald-500 transition-colors font-mono"
              />
            </div>
          </div>

          <button
            type="submit"
            :disabled="isLoading || twoFACode.length < 6"
            class="w-full mt-2 py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800/50 disabled:cursor-not-allowed text-slate-950 font-semibold text-sm rounded-lg transition-colors flex items-center justify-center gap-2"
          >
            <Loader2 v-if="isLoading" class="w-4 h-4 animate-spin text-slate-950" />
            <span>{{ isLoading ? 'Verificando...' : 'Verificar e Entrar' }}</span>
          </button>

          <button
            type="button"
            @click="backToCredentials"
            class="w-full py-2 text-xs text-slate-400 hover:text-slate-200 transition-colors flex items-center justify-center gap-1.5"
          >
            <ArrowLeft class="w-3.5 h-3.5" />
            Usar outra conta
          </button>
        </form>

        <!-- Footer Info -->
        <div class="mt-6 pt-6 border-t border-slate-800/80 text-center">
          <p class="text-[11px] text-slate-500">
            Autenticação via Active Directory com verificação em duas etapas (2FA). Acessos monitorados e auditados.
          </p>
        </div>

      </div>
    </div>
  </div>
</template>