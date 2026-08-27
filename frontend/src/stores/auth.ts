import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/services/api'
import router from '@/router'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('access_token'))
  const user = ref<{ username: string; role?: string } | null>(
    JSON.parse(localStorage.getItem('user_data') || 'null')
  )

  const isAuthenticated = computed(() => !!token.value)

  async function login(credentials: { username: string; password: string; provider: 'local' | 'ad' }) {
    const endpoint = credentials.provider === 'ad' ? '/auth/ad/login' : '/auth/login'
    
    // O FastAPI OAuth2 espera formato form-urlencoded ou JSON dependendo do router de auth
    const response = await api.post(endpoint, {
      username: credentials.username,
      password: credentials.password
    })

    token.value = response.data.access_token
    user.value = { username: credentials.username }
    
    localStorage.setItem('access_token', token.value!)
    localStorage.setItem('user_data', JSON.stringify(user.value))

    router.push('/dashboard')
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('user_data')
    router.push('/login')
  }

  return { token, user, isAuthenticated, login, logout }
})