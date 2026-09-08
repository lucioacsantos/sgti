import { api } from './api'

// ===== Tipos baseados nos schemas do backend (schemas.py) =====

export interface Ativo {
  id: number
  nome: string
  descricao?: string | null
  tipo_id: number
  ambiente_id?: number | null
  status_id?: number | null
  criticidade_id?: number | null
  sor_id?: number | null
  areas_id?: number | null
  created_at: string
}

export interface EnderecoIp {
  id: number
  ativo_id: number
  ip: string
  tipo?: string | null
  interface?: string | null
  descricao?: string | null
  primario: boolean
  ativo: boolean
  created_at: string
  updated_at?: string | null
}

export interface TipoAtivo { id: number; nome: string }
export interface Ambiente { id: number; nome: string }
export interface StatusAtivo { id: number; nome: string }
export interface Criticidade { id: number; nivel: string }
export interface SistemaOperacional { id: number; abreviacao: string; descricao: string; lifecycle?: string | null }
export interface Area { id: number; nome: string; sigla: string }
export interface TipoRelacionamento { id: number; nome: string; descricao?: string | null }

export interface Aplicacao {
  sistema: string
  descricao?: string | null
  objetivo?: string | null
  linguagens?: string | null
  bancos_dados?: string | null
  area_tecnologia?: string | null
  area_negocio?: string | null
  created_at: string
}

export interface Cluster { id: number; nome: string; descricao?: string | null; ativo_id?: number | null }
export interface Namespace { id: number; nome: string; cluster_id?: number | null; ativo_id?: number | null }
export interface Servico { id: number; nome: string; tipo?: string | null; host_id?: number | null; ativo_id?: number | null }
export interface ServicoNegocio { id: number; nome: string; descricao?: string | null; ativo_id?: number | null }
export interface InstanciaAplicacao {
  id: number
  aplicacao_id: number
  ativo_id?: number | null
  porta?: number | null
  path_execucao?: string | null
  comando_execucao?: string | null
  created_at: string
}

export interface Relacionamento {
  id: number
  origem_id: number
  destino_id: number
  tipo_id: number
  descricao?: string | null
  created_at: string
}

export interface AuditLog {
  id: number
  entidade: string
  entidade_id?: number | null
  acao?: string | null
  antes?: Record<string, unknown> | null
  depois?: Record<string, unknown> | null
  usuario?: string | null
  created_at: string
}

export interface HealthStatus {
  status: string
  database: string
}

export interface ApiInfo {
  message: string
  status: string
  version: string
  docs: string
}

// ===== Paginação =====
// O backend não fornece total; detectamos fim da lista quando a página
// retorna menos itens que o limite solicitado.
export interface PaginatedResult<T> {
  items: T[]
  page: number
  pageSize: number
  hasMore: boolean
}

export const DEFAULT_PAGE_SIZE = 50
export const MAX_PAGE_SIZE = 100

export async function fetchPage<T>(
  path: string,
  page: number,
  pageSize: number = DEFAULT_PAGE_SIZE,
  extraParams: Record<string, unknown> = {}
): Promise<PaginatedResult<T>> {
  const skip = (page - 1) * pageSize
  const { data } = await api.get<T[]>(path, {
    params: { skip, limit: pageSize, ...extraParams }
  })
  const items = Array.isArray(data) ? data : []
  return {
    items,
    page,
    pageSize,
    hasMore: items.length >= pageSize
  }
}