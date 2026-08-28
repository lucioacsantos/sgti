import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { api } from '@/services/api'
import router from '@/router'

// 1. Interface com os campos retornados pela API
export interface AuthUser {
  id: number
  username: string
  display_name: string
  email: string
  roles: string[]
  groups: string[]
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('access_token'))
  
  // 2. Tipagem completa do user
  const user = ref<AuthUser | null>(
    JSON.parse(localStorage.getItem('user_data') || 'null')
  )

  const isAuthenticated = computed(() => !!token.value)

  // 3. Getter conveniente para exibir o nome completo ou fallback para o username
  const userName = computed(() => user.value?.display_name || user.value?.username || '')

  async function login(credentials: { username: string; password: string; provider: 'local' | 'ad' }) {
    const endpoint = credentials.provider === 'ad' ? '/auth/ad/login' : '/auth/login'
    
    const response = await api.post(endpoint, {
      username: credentials.username,
      password: credentials.password
    })

    token.value = response.data.access_token
    
    // 4. Salva o objeto completo de user vindo da API
    user.value = response.data.user
    
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

  return { token, user, userName, isAuthenticated, login, logout }
})