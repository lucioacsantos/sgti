import axios, { AxiosError } from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

export const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL || 'http://localhost:8000',
  headers: {
    'Content-Type': 'application/json'
  }
})

export const apiBaseUrl = (import.meta.env.VITE_API_URL || 'http://localhost:8000').replace(/\/$/, '')

let refreshPromise: Promise<void> | null = null

api.interceptors.request.use((config) => {
  const authStore = useAuthStore()
  if (authStore.token) {
    config.headers.Authorization = `Bearer ${authStore.token}`
  }
  return config
})

function extractDetail(error: AxiosError): string {
  const data = error.response?.data as any
  if (data?.errors && Array.isArray(data.errors) && data.errors.length > 0) {
    const first = data.errors[0]
    return first.msg ? `Erro de validação: ${first.msg}` : 'Erro de validação dos dados.'
  }
  return data?.detail || error.message || 'Erro inesperado.'
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const authStore = useAuthStore()
    const original = error.config as any

    // Access token expirado → tenta refresh uma única vez
    if (error.response?.status === 401 && authStore.refreshToken && !original?._retried) {
      if (!refreshPromise) {
        refreshPromise = authStore.refreshTokens().finally(() => {
          refreshPromise = null
        })
      }
      try {
        await refreshPromise
        original._retried = true
        return api(original)
      } catch {
        /* refresh falhou → logout */
      }
    }

    if (error.response?.status === 401) {
      authStore.logout()
      router.push({ name: 'login' })
    }

    return Promise.reject(extractDetail(error))
  }
)