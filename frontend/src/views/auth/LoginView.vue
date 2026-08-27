<script setup lang="ts">
import { ref } from 'vue'
import { useAuthStore } from '@/stores/auth'
import { Lock, User, KeyRound, ShieldCheck, AlertCircle, Loader2 } from 'lucide-vue-next'

const authStore = useAuthStore()

const username = ref('')
const password = ref('')
const provider = ref<'local' | 'ad'>('ad')
const isLoading = ref(false)
const errorMessage = ref<string | null>(null)

async function handleSubmit() {
  if (!username.value || !password.value) {
    errorMessage.value = 'Preencha todos os campos para prosseguir.'
    return
  }

  errorMessage.value = null
  isLoading.value = true

  try {
    await authStore.login({
      username: username.value,
      password: password.value,
      provider: provider.value
    })
  } catch (error: any) {
    if (error.response?.data?.detail) {
      errorMessage.value = error.response.data.detail
    } else {
      errorMessage.value = 'Falha na autenticação. Verifique suas credenciais e a conexão.'
    }
  } finally {
    isLoading.value = false
  }
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
          <p class="text-xs text-slate-400 mt-1">Painel Administrativo de Infraestrutura e Ativos</p>
        </div>

        <!-- Provider Switcher -->
        <div class="grid grid-cols-2 gap-1 p-1 bg-slate-950 rounded-lg border border-slate-800 mb-6">
          <button
            type="button"
            @click="provider = 'ad'"
            class="py-2 text-xs font-medium rounded-md transition-all flex items-center justify-center gap-2"
            :class="provider === 'ad' ? 'bg-slate-800 text-emerald-400 shadow-sm' : 'text-slate-400 hover:text-slate-200'"
          >
            <KeyRound class="w-3.5 h-3.5" />
            Active Directory
          </button>
          <button
            type="button"
            @click="provider = 'local'"
            class="py-2 text-xs font-medium rounded-md transition-all flex items-center justify-center gap-2"
            :class="provider === 'local' ? 'bg-slate-800 text-emerald-400 shadow-sm' : 'text-slate-400 hover:text-slate-200'"
          >
            <User class="w-3.5 h-3.5" />
            Usuário Local
          </button>
        </div>

        <!-- Feedback de Erro -->
        <div 
          v-if="errorMessage" 
          class="mb-6 p-3 bg-rose-500/10 border border-rose-500/20 rounded-lg flex items-start gap-2.5 text-rose-400 text-xs leading-relaxed"
        >
          <AlertCircle class="w-4 h-4 shrink-0 mt-0.5" />
          <span>{{ errorMessage }}</span>
        </div>

        <!-- Form -->
        <form @submit.prevent="handleSubmit" class="space-y-4">
          <div>
            <label class="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">
              {{ provider === 'ad' ? 'Usuário de Rede (sAMAccountName)' : 'Nome de Usuário' }}
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

        <!-- Footer Info -->
        <div class="mt-6 pt-6 border-t border-slate-800/80 text-center">
          <p class="text-[11px] text-slate-500">
            Acessos monitorados e auditados em conformidade com as diretrizes de segurança.
          </p>
        </div>

      </div>
    </div>
  </div>
</template>