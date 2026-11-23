// Objetivo: Cliente da API do grafo de relacionamentos (Mapa de TI) — GET /relacionamentos/grafo.
// Author: Lucio A C Santos — GitHub: https://github.com/lucioacsantos

import { api } from './api'

export interface GrafoOpcao {
  id: number
  nome: string
}

export interface GrafoNo {
  id: number
  nome: string
  descricao: string | null
  fqdn: string | null
  tipo_id: number | null
  tipo: string | null
  ambiente_id: number | null
  ambiente: string | null
  status_id: number | null
  status: string | null
  criticidade_id: number | null
  criticidade: string | null
  grau: number
}

export interface GrafoAresta {
  id: number
  origem_id: number
  destino_id: number
  tipo_id: number | null
  tipo_nome: string | null
  descricao: string | null
}

export interface GrafoOpcoes {
  ambientes: GrafoOpcao[]
  tipos_ativo: GrafoOpcao[]
  criticidades: GrafoOpcao[]
  status: GrafoOpcao[]
  tipos_relacionamento: GrafoOpcao[]
}

export interface GrafoMeta {
  total_nos: number
  total_arestas: number
  nos_truncados: boolean
  opcoes: GrafoOpcoes
}

export interface GrafoResponse {
  nodes: GrafoNo[]
  edges: GrafoAresta[]
  meta: GrafoMeta
}

export interface GrafoFiltros {
  ambiente_id?: number | null
  tipo_ativo_id?: number | null
  criticidade_id?: number | null
  status_id?: number | null
  tipo_relacionamento_id?: number | null
  q?: string | null
  grau_minimo?: number
  incluir_isolados?: boolean
  limite?: number
}

export const grafoService = {
  /** Carrega o grafo de relacionamentos aplicando os filtros informados. */
  async carregar(filtros: GrafoFiltros): Promise<GrafoResponse> {
    const params = Object.fromEntries(
      Object.entries(filtros).filter(([, valor]) => valor !== null && valor !== undefined && valor !== '')
    )
    const { data } = await api.get<GrafoResponse>('/relacionamentos/grafo', {
      params,
      timeout: 120000
    })
    return data
  }
}
