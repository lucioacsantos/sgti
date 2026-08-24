import axios from 'axios'
import { useAuthStore } from '../store/auth'

const API_URL = import.meta.env.VITE_API_URL || '/api'
const DATA_COLLECTION_URL = import.meta.env.VITE_DATA_COLLECTION_URL || '/data-collection'

export const api = axios.create({
  baseURL: API_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

export const dataCollectionApi = axios.create({
  baseURL: DATA_COLLECTION_URL,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 30000,
})

// Request interceptor to add auth token
const addAuthHeader = (config: any) => {
  const { accessToken } = useAuthStore.getState()
  if (accessToken) {
    config.headers.Authorization = `Bearer ${accessToken}`
  }
  return config
}

api.interceptors.request.use(addAuthHeader)
dataCollectionApi.interceptors.request.use(addAuthHeader)

// Response interceptor for token refresh
api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config
    if (error.response?.status === 401 && !originalRequest._retry) {
      originalRequest._retry = true
      try {
        await useAuthStore.getState().refreshAccessToken()
        return api(originalRequest)
      } catch {
        useAuthStore.getState().logout()
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// CMDB API Types and Functions
export interface Asset {
  id: number
  nome: string
  descricao?: string
  tipo_id: number
  ambiente_id?: number
  status_id?: number
  criticidade_id?: number
  sor_id?: number
  areas_id?: number
  created_at: string
  updated_at?: string
  // Additional fields from collected entities
  cpu_cores?: number
  cpu_threads?: number
  cpu_model?: string
  cpu_mhz?: number
  memory_gb?: number
  total_storage_gb?: number
  power_state?: string
  connection_state?: string
  manufacturer?: string
  model?: string
  serial_number?: string
  uuid?: string
  asset_tag?: string
  datacenter?: string
  rack?: string
  rack_unit?: string
  tags?: Record<string, string>
  first_seen_at?: string
  last_seen_at?: string
  collection_job_id?: string
  is_certified?: boolean
  certified_at?: string
  certified_by?: string
  tipo?: AssetType
  ambiente?: Environment
  status?: AssetStatus
  criticidade?: Criticity
  sor?: OperatingSystem
  areas?: Area
}

export interface AssetType {
  id: number
  nome: string
}

export interface Environment {
  id: number
  nome: string
}

export interface AssetStatus {
  id: number
  nome: string
}

export interface Criticity {
  id: number
  nivel: string
}

export interface OperatingSystem {
  id: number
  abreviacao: string
  descricao: string
  lifecycle?: string
}

export interface Area {
  id: number
  nome: string
  sigla: string
}

export interface IPAddress {
  id: number
  ativo_id: number
  ip: string
  tipo?: string
  interface?: string
  descricao?: string
  primario: boolean
  ativo: boolean
  created_at: string
  updated_at?: string
}

export interface Relationship {
  id: number
  origem_id: number
  destino_id: number
  tipo_id: number
  descricao?: string
  created_at: string
  origem?: Asset
  destino?: Asset
  tipo?: RelationshipType
}

export interface RelationshipType {
  id: number
  nome: string
  descricao?: string
}

export interface Application {
  id: number
  sistema: string
  descricao?: string
  objetivo?: string
  linguagens?: string
  bancos_dados?: string
  area_tecnologia?: string
  area_negocio?: string
  created_at: string
}

export interface Cluster {
  id: number
  nome: string
  descricao?: string
  ativo_id?: number
  ativo?: Asset
}

export interface Namespace {
  id: number
  nome: string
  cluster_id?: number
  ativo_id?: number
  cluster?: Cluster
  ativo?: Asset
}

export interface Service {
  id: number
  nome: string
  tipo?: string
  host_id?: number
  ativo_id?: number
  ativo?: Asset
}

export interface BusinessService {
  id: number
  nome: string
  descricao?: string
  ativo_id?: number
  ativo?: Asset
}

export interface AppInstance {
  id: number
  aplicacao_id: number
  ativo_id?: number
  porta?: number
  path_execucao?: string
  comando_execucao?: string
  created_at: string
  aplicacao?: Application
  ativo?: Asset
}

export interface AuditLog {
  id: number
  entidade: string
  entidade_id?: number
  acao?: string
  antes?: Record<string, any>
  depois?: Record<string, any>
  usuario?: string
  created_at: string
}

export interface PaginatedResponse<T> {
  data: T[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

// Asset API
export const assetApi = {
  list: (params?: { skip?: number; limit?: number; search?: string }) =>
    api.get<Asset[]>('/ativos', { params }).then(res => res.data),
  get: (id: string) => api.get<Asset>(`/ativos/${id}`).then(res => res.data),
  create: (data: Partial<Asset>) => api.post<Asset>('/ativos', data).then(res => res.data),
  update: (id: string, data: Partial<Asset>) => api.put<Asset>(`/ativos/${id}`, data).then(res => res.data),
  delete: (id: string) => api.delete(`/ativos/${id}`),
  upsert: (nome: string, data: Partial<Asset>) => api.put<Asset>(`/ativos/${nome}`, data).then(res => res.data),
}

// IP Address API
export const ipApi = {
  list: (params?: { ativo_id?: number; skip?: number; limit?: number }) =>
    api.get<IPAddress[]>('/enderecos-ip', { params }).then(res => res.data),
  get: (id: number) => api.get<IPAddress>(`/enderecos-ip/${id}`).then(res => res.data),
  upsert: (data: { ativo_id: number; ip: string; tipo?: string; interface?: string; descricao?: string; primario?: boolean; ativo?: boolean }) =>
    api.post<IPAddress>('/enderecos-ip', data).then(res => res.data),
  delete: (id: number) => api.delete(`/enderecos-ip/${id}`),
}

// Relationship API
export const relationshipApi = {
  list: (params?: { origem_id?: number; destino_id?: number; skip?: number; limit?: number }) =>
    api.get<Relationship[]>('/relacionamentos', { params }).then(res => res.data),
  get: (id: number) => api.get<Relationship>(`/relacionamentos/${id}`).then(res => res.data),
  create: (data: { origem_id: number; destino_id: number; tipo_id: number; descricao?: string }) =>
    api.post<Relationship>('/relacionamentos', data).then(res => res.data),
  delete: (id: string) => api.delete(`/relacionamentos/${id}`),
  types: {
    list: () => api.get<RelationshipType[]>('/tipos-relacionamento').then(res => res.data),
    create: (data: { nome: string; descricao?: string }) => api.post<RelationshipType>('/tipos-relacionamento', data).then(res => res.data),
  },
}

// Reference Data API
export const referenceApi = {
  assetTypes: () => api.get<AssetType[]>('/tipos-ativos').then(res => res.data),
  environments: () => api.get<Environment[]>('/ambientes').then(res => res.data),
  statuses: () => api.get<AssetStatus[]>('/status-ativos').then(res => res.data),
  criticities: () => api.get<Criticity[]>('/criticidades').then(res => res.data),
  operatingSystems: () => api.get<OperatingSystem[]>('/sistema-operacional').then(res => res.data),
  areas: () => api.get<Area[]>('/areas').then(res => res.data),
  applications: (params?: { skip?: number; limit?: number }) => api.get<Application[]>('/aplicacoes', { params }).then(res => res.data),
  clusters: (params?: { skip?: number; limit?: number }) => api.get<Cluster[]>('/clusters', { params }).then(res => res.data),
  namespaces: (params?: { skip?: number; limit?: number }) => api.get<Namespace[]>('/namespaces', { params }).then(res => res.data),
  services: (params?: { skip?: number; limit?: number }) => api.get<Service[]>('/servicos', { params }).then(res => res.data),
  businessServices: (params?: { skip?: number; limit?: number }) => api.get<BusinessService[]>('/servicos-negocio', { params }).then(res => res.data),
  appInstances: (params?: { aplicacao_id?: number; skip?: number; limit?: number }) => api.get<AppInstance[]>('/instancias-aplicacao', { params }).then(res => res.data),
}

// Admin applications API
export const applicationsAdminApi = {
  delete: (id: string) => api.delete(`/aplicacoes/${id}`),
}

// Admin clusters API
export const clustersAdminApi = {
  delete: (id: string) => api.delete(`/clusters/${id}`),
}

// Admin namespaces API
export const namespacesAdminApi = {
  delete: (id: string) => api.delete(`/namespaces/${id}`),
}

// Admin services API
export const servicesAdminApi = {
  delete: (id: string) => api.delete(`/servicos/${id}`),
}

// Audit API
export const auditApi = {
  list: (params?: { entidade?: string; entidade_id?: number; skip?: number; limit?: number }) =>
    api.get<AuditLog[]>('/audit-logs', { params }).then(res => res.data),
}

// Admin API
export const adminApi = {
  users: {
    list: (params?: { skip?: number; limit?: number }) => api.get<any[]>('/admin/users', { params }).then(res => res.data),
    get: (id: string) => api.get<any>(`/admin/users/${id}`).then(res => res.data),
    create: (data: any) => api.post<any>('/admin/users', data).then(res => res.data),
    update: (id: string, data: any) => api.put<any>(`/admin/users/${id}`, data).then(res => res.data),
    delete: (id: string) => api.delete(`/admin/users/${id}`),
    roles: () => api.get<string[]>('/admin/roles').then(res => res.data),
  },
  relationshipTypes: {
    list: () => api.get<any[]>('/admin/relationship-types').then(res => res.data),
    create: (data: { nome: string; descricao?: string }) => api.post<any>('/admin/relationship-types', data).then(res => res.data),
    update: (id: number, data: { nome?: string; descricao?: string }) => api.put<any>(`/admin/relationship-types/${id}`, data).then(res => res.data),
    delete: (id: number) => api.delete(`/admin/relationship-types/${id}`),
  },
  assetTypes: {
    list: () => api.get<any[]>('/admin/asset-types').then(res => res.data),
    create: (data: { nome: string }) => api.post<any>('/admin/asset-types', data).then(res => res.data),
    update: (id: number, data: { nome?: string }) => api.put<any>(`/admin/asset-types/${id}`, data).then(res => res.data),
    delete: (id: number) => api.delete(`/admin/asset-types/${id}`),
  },
  environments: {
    list: () => api.get<any[]>('/admin/environments').then(res => res.data),
    create: (data: { nome: string }) => api.post<any>('/admin/environments', data).then(res => res.data),
    update: (id: number, data: { nome?: string }) => api.put<any>(`/admin/environments/${id}`, data).then(res => res.data),
    delete: (id: number) => api.delete(`/admin/environments/${id}`),
  },
  statuses: {
    list: () => api.get<any[]>('/admin/statuses').then(res => res.data),
    create: (data: { nome: string }) => api.post<any>('/admin/statuses', data).then(res => res.data),
    update: (id: number, data: { nome?: string }) => api.put<any>(`/admin/statuses/${id}`, data).then(res => res.data),
    delete: (id: number) => api.delete(`/admin/statuses/${id}`),
  },
  criticities: {
    list: () => api.get<any[]>('/admin/criticities').then(res => res.data),
    create: (data: { nivel: string }) => api.post<any>('/admin/criticities', data).then(res => res.data),
    update: (id: number, data: { nivel?: string }) => api.put<any>(`/admin/criticities/${id}`, data).then(res => res.data),
    delete: (id: number) => api.delete(`/admin/criticities/${id}`),
  },
  operatingSystems: {
    list: () => api.get<any[]>('/admin/operating-systems').then(res => res.data),
    create: (data: { abreviacao: string; descricao: string; lifecycle?: string }) => api.post<any>('/admin/operating-systems', data).then(res => res.data),
    update: (id: number, data: Partial<OperatingSystem>) => api.put<any>(`/admin/operating-systems/${id}`, data).then(res => res.data),
    delete: (id: number) => api.delete(`/admin/operating-systems/${id}`),
  },
  areas: {
    list: () => api.get<any[]>('/admin/areas').then(res => res.data),
    create: (data: { nome: string; sigla: string }) => api.post<any>('/admin/areas', data).then(res => res.data),
    update: (id: number, data: Partial<Area>) => api.put<any>(`/admin/areas/${id}`, data).then(res => res.data),
    delete: (id: number) => api.delete(`/admin/areas/${id}`),
  },
}

// Data Collection API
export const collectionApi = {
  sources: {
    list: (params?: { source_type?: string; status?: string }) => dataCollectionApi.get<any[]>('/api/v1/sources', { params }).then(res => res.data),
    get: (id: string) => dataCollectionApi.get<any>(`/api/v1/sources/${id}`).then(res => res.data),
    create: (data: any) => dataCollectionApi.post<any>('/api/v1/sources', data).then(res => res.data),
    update: (id: string, data: any) => dataCollectionApi.patch<any>(`/api/v1/sources/${id}`, data).then(res => res.data),
    delete: (id: string) => dataCollectionApi.delete(`/api/v1/sources/${id}`),
    test: (id: string) => dataCollectionApi.post<any>(`/api/v1/sources/${id}/test`).then(res => res.data),
  },
    jobs: {
      list: (params?: { source_id?: string; status?: string; limit?: number }) => dataCollectionApi.get<any[]>('/api/v1/collection/jobs', { params }).then(res => res.data),
      get: (id: string) => dataCollectionApi.get<any>(`/api/v1/collection/jobs/${id}`).then(res => res.data),
      create: (data: any) => dataCollectionApi.post<any>('/api/v1/collection/jobs', data).then(res => res.data),
      complete: (id: string, status: string) => dataCollectionApi.post<any>(`/api/v1/collection/jobs/${id}/complete`, { status }).then(res => res.data),
    },
  entities: {
    list: (params?: { source_id?: string; entity_type?: string; is_certified?: boolean }) => dataCollectionApi.get<any[]>('/api/v1/entities', { params }).then(res => res.data),
  },
  reconciliation: {
    sessions: {
      list: (params?: { status?: string }) => dataCollectionApi.get<any[]>('/api/v1/reconciliation/sessions', { params }).then(res => res.data),
      get: (id: string) => dataCollectionApi.get<any>(`/api/v1/reconciliation/sessions/${id}`).then(res => res.data),
      create: (data: any) => dataCollectionApi.post<any>('/api/v1/reconciliation/sessions', data).then(res => res.data),
    },
    conflicts: {
      list: (sessionId: string, params?: { severity?: string; resolved?: boolean }) => dataCollectionApi.get<any[]>(`/api/v1/reconciliation/sessions/${sessionId}/conflicts`, { params }).then(res => res.data),
      resolve: (id: string, data: { resolution: string; resolved_value?: any; notes?: string; resolved_by: string }) => dataCollectionApi.post<any>(`/api/v1/reconciliation/conflicts/${id}/resolve`, data).then(res => res.data),
    },
  },
  certification: {
    requests: {
      list: (params?: { status?: string; assignee_id?: string }) => dataCollectionApi.get<any[]>('/api/v1/certification/requests', { params }).then(res => res.data),
      get: (id: string) => dataCollectionApi.get<any>(`/api/v1/certification/requests/${id}`).then(res => res.data),
      create: (data: any) => dataCollectionApi.post<any>('/api/v1/certification/requests', data).then(res => res.data),
      action: (id: string, data: { role: string; decision: string; notes?: string; decided_by: string }) => dataCollectionApi.post<any>(`/api/v1/certification/requests/${id}/action`, data).then(res => res.data),
      addComment: (id: string, data: { author_id: string; author_role: string; content: string }) => dataCollectionApi.post<any>(`/api/v1/certification/requests/${id}/comments`, data).then(res => res.data),
    },
  },
}

// Health
export const healthApi = {
  check: () => api.get('/health').then(res => res.data),
  detailed: () => api.get('/health/detailed').then(res => res.data),
}