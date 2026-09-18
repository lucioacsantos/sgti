import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authService, type AuthUser, type TokenResponse } from '@/services/auth.service'
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

  const requires2FA = ref(false)
  const pending2FAUser = ref<{ username: string; display_name: string } | null>(null)
  let pending2FAPassword: string | null = null

  async function login(username: string, password: string) {
    const response = await authService.login(username, password)

    if (response.requires_2fa) {
      requires2FA.value = true
      pending2FAPassword = password
      pending2FAUser.value = {
        username,
        display_name: response.user?.display_name || username
      }
      return
    }

    requires2FA.value = false
    pending2FAUser.value = null
    setSession(response, response.user.two_fa_enabled ?? false)
  }

  async function verify2FALogin(code: string) {
    if (!pending2FAUser.value || !pending2FAPassword) {
      throw new Error('Nenhuma autenticação pendente de 2FA.')
    }
    const username2FA = pending2FAUser.value.username
    const password2FA = pending2FAPassword
    const response = await authService.loginWith2FA(username2FA, password2FA, code)
    if (response.requires_2fa) {
      throw new Error('Código 2FA inválido ou expirado.')
    }
    requires2FA.value = false
    pending2FAUser.value = null
    pending2FAPassword = null
    setSession(response, response.user.two_fa_enabled ?? true)
  }

  function cancel2FA() {
    requires2FA.value = false
    pending2FAUser.value = null
    pending2FAPassword = null
  }

  function setSession(response: TokenResponse, twoFaEnabled: boolean) {
    if (!response.access_token || !response.refresh_token) {
      throw new Error('Resposta de autenticação sem tokens.')
    }

    token.value = response.access_token
    refreshToken.value = response.refresh_token
    user.value = { ...response.user, two_fa_enabled: twoFaEnabled }

    localStorage.setItem('access_token', response.access_token)
    localStorage.setItem('refresh_token', response.refresh_token)
    localStorage.setItem('user_data', JSON.stringify(user.value))
  }

  async function refreshTokens() {
    if (!refreshToken.value) {
      throw new Error('Sem refresh token')
    }
    const currentRefresh = refreshToken.value
    const response = await authService.refresh(currentRefresh)

    if (!response.access_token || !response.refresh_token) {
      throw new Error('Resposta de refresh sem tokens.')
    }

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
    requires2FA,
    pending2FAUser,
    login,
    verify2FALogin,
    cancel2FA,
    refreshTokens,
    logout,
    syncUser
  }
})