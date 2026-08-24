import React from 'react'
import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { api } from '../lib/api'

export interface User {
  id: string
  username: string
  email: string
  displayName: string
  roles: string[]
  groups: string[]
  requires2FA: boolean
  twoFAEnabled: boolean
}

export interface AuthState {
  user: User | null
  accessToken: string | null
  refreshToken: string | null
  isAuthenticated: boolean
  isLoading: boolean
  error: string | null
  
  // Actions
  login: (username: string, password: string) => Promise<void>
  testLogin: (username?: string, roles?: string[]) => Promise<void>
  verify2FA: (code: string) => Promise<void>
  setup2FA: () => Promise<{ secret: string; qrCode: string }>
  enable2FA: (code: string) => Promise<void>
  disable2FA: (password: string) => Promise<void>
  logout: () => Promise<void>
  refreshAccessToken: () => Promise<void>
  clearError: () => void
  checkAuth: () => Promise<void>
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const { checkAuth } = useAuthStore()
  
  React.useEffect(() => {
    checkAuth()
  }, [checkAuth])
  
  return <>{children}</>
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set, get) => ({
      user: null,
      accessToken: null,
      refreshToken: null,
      isAuthenticated: false,
      isLoading: false,
      error: null,

      clearError: () => set({ error: null }),

      login: async (username: string, password: string) => {
        set({ isLoading: true, error: null })
        try {
          const response = await api.post('/auth/ad/login', { username, password })
          const { access_token, refresh_token, user, requires_2fa } = response.data
          
          set({
            accessToken: access_token,
            refreshToken: refresh_token,
            user: { 
              id: user.id,
              username: user.username,
              email: user.email,
              displayName: user.display_name,
              roles: user.roles,
              groups: user.groups,
              requires2FA: requires_2fa,
              twoFAEnabled: false 
            },
            isAuthenticated: !requires_2fa,
            isLoading: false,
          })
          
          // Store tokens in axios defaults
          api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
        } catch (error: any) {
          set({ 
            isLoading: false, 
            error: error.response?.data?.detail || 'Erro ao fazer login no Active Directory' 
          })
          throw error
        }
      },

      testLogin: async (username: string = "testuser", roles: string[] = ["admin", "analyst", "viewer"]) => {
        set({ isLoading: true, error: null })
        try {
          const response = await api.post('/auth/test/login', { username, roles })
          const { access_token, refresh_token, user, requires_2fa } = response.data
          
          set({
            accessToken: access_token,
            refreshToken: refresh_token,
            user: { 
              id: user.id,
              username: user.username,
              email: user.email,
              displayName: user.display_name,
              roles: user.roles,
              groups: user.groups,
              requires2FA: requires_2fa,
              twoFAEnabled: false 
            },
            isAuthenticated: !requires_2fa,
            isLoading: false,
          })
          
          // Store tokens in axios defaults
          api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
        } catch (error: any) {
          set({ 
            isLoading: false, 
            error: error.response?.data?.detail || 'Erro ao fazer login de teste' 
          })
          throw error
        }
      },

      verify2FA: async (code: string) => {
        set({ isLoading: true, error: null })
        try {
          const response = await api.post('/auth/2fa/verify', { code })
          const { access_token, refresh_token, user } = response.data
          
          set({
            accessToken: access_token,
            refreshToken: refresh_token,
            user: { ...user, requires2FA: false, twoFAEnabled: true },
            isAuthenticated: true,
            isLoading: false,
          })
          
          api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
        } catch (error: any) {
          set({ 
            isLoading: false, 
            error: error.response?.data?.detail || 'Código 2FA inválido' 
          })
          throw error
        }
      },

      setup2FA: async () => {
        set({ isLoading: true, error: null })
        try {
          const response = await api.post('/auth/2fa/setup')
          set({ isLoading: false })
          return response.data
        } catch (error: any) {
          set({ 
            isLoading: false, 
            error: error.response?.data?.detail || 'Erro ao configurar 2FA' 
          })
          throw error
        }
      },

      enable2FA: async (code: string) => {
        set({ isLoading: true, error: null })
        try {
          await api.post('/auth/2fa/enable', { code })
          set(state => ({
            user: state.user ? { ...state.user, twoFAEnabled: true, requires2FA: false } : null,
            isLoading: false,
          }))
        } catch (error: any) {
          set({ 
            isLoading: false, 
            error: error.response?.data?.detail || 'Erro ao ativar 2FA' 
          })
          throw error
        }
      },

      disable2FA: async (password: string) => {
        set({ isLoading: true, error: null })
        try {
          await api.post('/auth/2fa/disable', { password })
          set(state => ({
            user: state.user ? { ...state.user, twoFAEnabled: false } : null,
            isLoading: false,
          }))
        } catch (error: any) {
          set({ 
            isLoading: false, 
            error: error.response?.data?.detail || 'Erro ao desativar 2FA' 
          })
          throw error
        }
      },

      logout: async () => {
        const { refreshToken } = get()
        try {
          if (refreshToken) {
            await api.post('/auth/logout', { refresh_token: refreshToken })
          }
        } catch (error) {
          // Ignore logout errors
        } finally {
          set({
            user: null,
            accessToken: null,
            refreshToken: null,
            isAuthenticated: false,
            error: null,
          })
          delete api.defaults.headers.common['Authorization']
        }
      },

      refreshAccessToken: async () => {
        const { refreshToken } = get()
        if (!refreshToken) return
        
        try {
          const response = await api.post('/auth/refresh', { refresh_token: refreshToken })
          const { access_token, refresh_token: newRefreshToken } = response.data
          
          set({
            accessToken: access_token,
            refreshToken: newRefreshToken,
          })
          api.defaults.headers.common['Authorization'] = `Bearer ${access_token}`
        } catch (error) {
          // Refresh failed, logout
          get().logout()
          throw error
        }
      },

      checkAuth: async () => {
        const { accessToken, refreshToken } = get()
        if (!accessToken || !refreshToken) return
        
        try {
          const response = await api.get('/auth/me')
          const userData = response.data
          set({
            user: { 
              id: userData.id,
              username: userData.username,
              email: userData.email,
              displayName: userData.display_name,
              roles: userData.roles,
              groups: userData.groups,
              requires2FA: userData.requires_2fa,
              twoFAEnabled: userData.two_fa_enabled 
            },
            isAuthenticated: true,
          })
        } catch (error) {
          // Try refresh
          try {
            await get().refreshAccessToken()
            const response = await api.get('/auth/me')
            const userData = response.data
            set({ 
              user: { 
                id: userData.id,
                username: userData.username,
                email: userData.email,
                displayName: userData.display_name,
                roles: userData.roles,
                groups: userData.groups,
                requires2FA: userData.requires_2fa,
                twoFAEnabled: userData.two_fa_enabled 
              }, 
              isAuthenticated: true 
            })
          } catch {
            get().logout()
          }
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        accessToken: state.accessToken,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
)