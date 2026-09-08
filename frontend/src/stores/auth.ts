import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authService, type AuthUser } from '@/services/auth.service'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const refreshToken = ref<string | null>(localStorage.getItem('refresh_token'))

  const user = ref<AuthUser | null>(
    JSON.parse(localStorage.getItem('user_data') || 'null')
  )

  const isAuthenticated = computed(() => !!token.value)
  const userName = computed(() => user.value?.display_name || user.value?.username || '')
  const roles = computed(() => user.value?.roles ?? [])
  const isAdmin = computed(() => roles.value.includes('admin'))

  async function login(username: string, password: string) {
    const response = await authService.login(username, password)

    token.value = response.access_token
    refreshToken.value = response.refresh_token
    user.value = { ...response.user, two_fa_enabled: false }

    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('refresh_token', response.refresh_token)
    localStorage.setItem('user_data', JSON.stringify(user.value))
  }

  async function refreshTokens() {
    if (!refreshToken.value) {
      throw new Error('Sem refresh token')
    }
    const response = await authService.refresh(refreshToken.value)

    token.value = response.access_token
    refreshToken.value = response.refresh_token
    user.value = { ...response.user, two_fa_enabled: user.value?.two_fa_enabled }

    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('refresh_token', response.refresh_token)
    localStorage.setItem('user_data', JSON.stringify(user.value))
  }

  async function logout() {
    try {
      if (refreshToken.value) {
        await authService.logout(refreshToken.value)
      }
    } catch {
      /* logout server-side é best-effort */
    }
    token.value = null
    refreshToken.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    localStorage.removeItem('user_data')
    router.push({ name: 'login' })
  }

  async function syncUser() {
    try {
      const me = await authService.me()
      user.value = me
      localStorage.setItem('user_data', JSON.stringify(me))
    } catch {
      /* silencioso — token pode estar expirando */
    }
  }

  return {
    token,
    refreshToken,
    user,
    userName,
    roles,
    isAdmin,
    isAuthenticated,
    login,
    refreshTokens,
    logout,
    syncUser
  }
})