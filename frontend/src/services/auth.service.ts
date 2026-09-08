import { api } from './api'

export interface AuthUser {
  id: number
  username: string
  display_name: string
  email: string
  roles: string[]
  groups: string[]
  two_fa_enabled?: boolean
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: AuthUser
  requires_2fa: boolean
}

export interface AdminUser {
  id: number
  username: string
  display_name: string
  email: string
  roles: string[]
  is_active: boolean
  is_service_account: boolean
  two_fa_enabled: boolean
  created_at?: string | null
  expires_at?: string | null
}

export interface ServiceToken {
  id: number
  name: string
  is_active: boolean
  created_at?: string | null
  expires_at?: string | null
  token?: string | null
}

export interface TwoFASetup {
  secret: string
  qr_code: string
  issuer: string
}

export const authService = {
  async login(username: string, password: string): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>('/auth/ad/login', { username, password })
    return data
  },
  async refresh(refreshToken: string): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>('/auth/refresh', { refresh_token: refreshToken })
    return data
  },
  async logout(refreshToken: string): Promise<void> {
    await api.post('/auth/logout', { refresh_token: refreshToken })
  },
  async me(): Promise<AuthUser> {
    const { data } = await api.get<AuthUser>('/auth/me')
    return data
  },
  async setup2FA(): Promise<TwoFASetup> {
    const { data } = await api.post<TwoFASetup>('/auth/2fa/setup')
    return data
  },
  async verify2FA(code: string): Promise<{ message: string; verified: boolean }> {
    const { data } = await api.post('/auth/2fa/verify', { code })
    return data
  },
  async disable2FA(password: string): Promise<{ message: string }> {
    const { data } = await api.post('/auth/2fa/disable', { password })
    return data
  }
}

export const adminService = {
  async users(skip = 0, limit = 100): Promise<AdminUser[]> {
    const { data } = await api.get<AdminUser[]>('/auth/admin/users', { params: { skip, limit } })
    return data
  },
  async updateUser(id: number, payload: { is_active?: boolean; expires_at?: string }): Promise<AdminUser> {
    const { data } = await api.patch<AdminUser>(`/auth/admin/users/${id}`, payload)
    return data
  },
  async disableUser2FA(id: number): Promise<{ message: string }> {
    const { data } = await api.post(`/auth/admin/users/${id}/2fa/disable`)
    return data
  },
  async roles(): Promise<string[]> {
    const { data } = await api.get<string[]>('/auth/admin/roles')
    return data
  },
  async tokens(): Promise<ServiceToken[]> {
    const { data } = await api.get<ServiceToken[]>('/auth/admin/tokens')
    return data
  },
  async createToken(name: string, expiresAt?: string): Promise<ServiceToken> {
    const payload: Record<string, unknown> = { name }
    if (expiresAt) payload.expires_at = expiresAt
    const { data } = await api.post<ServiceToken>('/auth/admin/tokens', payload)
    return data
  },
  async deleteToken(id: number): Promise<void> {
    await api.delete(`/auth/admin/tokens/${id}`)
  }
}