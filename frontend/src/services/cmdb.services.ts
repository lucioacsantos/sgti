import { api } from './api'
import type {
  Ativo, EnderecoIp, TipoAtivo, Ambiente, StatusAtivo, Criticidade,
  SistemaOperacional, Area, TipoRelacionamento, Aplicacao, Cluster,
  Namespace, Servico, ServicoNegocio, InstanciaAplicacao, Relacionamento,
  AuditLog, HealthStatus, ApiInfo
} from './cmdb'

// ===== Health =====
export const healthService = {
  async root(): Promise<ApiInfo> {
    const { data } = await api.get<ApiInfo>('/')
    return data
  },
  async health(): Promise<HealthStatus> {
    const { data } = await api.get<HealthStatus>('/health')
    return data
  }
}

// ===== Ativos =====
export const ativosService = {
  async list(skip = 0, limit = 50): Promise<Ativo[]> {
    const { data } = await api.get<Ativo[]>('/ativos/', { params: { skip, limit } })
    return data
  },
  async get(nome: string): Promise<Ativo> {
    const { data } = await api.get<Ativo>(`/ativos/${encodeURIComponent(nome)}`)
    return data
  },
  async update(nome: string, payload: Partial<Ativo>): Promise<Ativo> {
    const { data } = await api.put<Ativo>(`/ativos/${encodeURIComponent(nome)}`, payload)
    return data
  },
  async delete(nome: string): Promise<void> {
    await api.delete(`/ativos/${encodeURIComponent(nome)}`)
  }
}

// ===== Endereços IP =====
export const ipService = {
  async list(ativoId?: number, skip = 0, limit = 50): Promise<EnderecoIp[]> {
    const params: Record<string, unknown> = { skip, limit }
    if (ativoId) params.ativo_id = ativoId
    const { data } = await api.get<EnderecoIp[]>('/enderecos-ip/', { params })
    return data
  },
  async delete(ipId: number): Promise<void> {
    await api.delete(`/enderecos-ip/${ipId}`)
  }
}

// ===== Dados de referência =====
export const referenceService = {
  async tiposAtivos(): Promise<TipoAtivo[]> {
    const { data } = await api.get<TipoAtivo[]>('/tipos-ativos/')
    return data
  },
  async statusAtivos(): Promise<StatusAtivo[]> {
    const { data } = await api.get<StatusAtivo[]>('/status-ativos/')
    return data
  },
  async ambientes(): Promise<Ambiente[]> {
    const { data } = await api.get<Ambiente[]>('/ambientes/')
    return data
  },
  async criticidades(): Promise<Criticidade[]> {
    const { data } = await api.get<Criticidade[]>('/criticidades/')
    return data
  },
  async sistemasOperacionais(): Promise<SistemaOperacional[]> {
    const { data } = await api.get<SistemaOperacional[]>('/sistema-operacional/')
    return data
  },
  async areas(): Promise<Area[]> {
    const { data } = await api.get<Area[]>('/areas/')
    return data
  },

  // CRUD admin
  async createArea(payload: Omit<Area, 'id'>): Promise<Area> {
    const { data } = await api.post<Area>('/admin/areas', payload)
    return data
  },
  async updateArea(id: number, payload: Omit<Area, 'id'>): Promise<Area> {
    const { data } = await api.put<Area>(`/admin/areas/${id}`, payload)
    return data
  },
  async deleteArea(id: number): Promise<void> {
    await api.delete(`/admin/areas/${id}`)
  },

  async createTipoAtivo(payload: { nome: string }): Promise<TipoAtivo> {
    const { data } = await api.post<TipoAtivo>('/admin/asset-types', payload)
    return data
  },
  async updateTipoAtivo(id: number, payload: { nome: string }): Promise<TipoAtivo> {
    const { data } = await api.put<TipoAtivo>(`/admin/asset-types/${id}`, payload)
    return data
  },
  async deleteTipoAtivo(id: number): Promise<void> {
    await api.delete(`/admin/asset-types/${id}`)
  },

  async createAmbiente(payload: { nome: string }): Promise<Ambiente> {
    const { data } = await api.post<Ambiente>('/admin/environments', payload)
    return data
  },
  async updateAmbiente(id: number, payload: { nome: string }): Promise<Ambiente> {
    const { data } = await api.put<Ambiente>(`/admin/environments/${id}`, payload)
    return data
  },
  async deleteAmbiente(id: number): Promise<void> {
    await api.delete(`/admin/environments/${id}`)
  },

  async createStatus(payload: { nome: string }): Promise<StatusAtivo> {
    const { data } = await api.post<StatusAtivo>('/admin/statuses', payload)
    return data
  },
  async updateStatus(id: number, payload: { nome: string }): Promise<StatusAtivo> {
    const { data } = await api.put<StatusAtivo>(`/admin/statuses/${id}`, payload)
    return data
  },
  async deleteStatus(id: number): Promise<void> {
    await api.delete(`/admin/statuses/${id}`)
  },

  async createCriticidade(payload: { nivel: string }): Promise<Criticidade> {
    const { data } = await api.post<Criticidade>('/admin/criticities', payload)
    return data
  },
  async updateCriticidade(id: number, payload: { nivel: string }): Promise<Criticidade> {
    const { data } = await api.put<Criticidade>(`/admin/criticities/${id}`, payload)
    return data
  },
  async deleteCriticidade(id: number): Promise<void> {
    await api.delete(`/admin/criticities/${id}`)
  },

  async createSO(payload: Omit<SistemaOperacional, 'id'>): Promise<SistemaOperacional> {
    const { data } = await api.post<SistemaOperacional>('/admin/operating-systems', payload)
    return data
  },
  async updateSO(id: number, payload: Omit<SistemaOperacional, 'id'>): Promise<SistemaOperacional> {
    const { data } = await api.put<SistemaOperacional>(`/admin/operating-systems/${id}`, payload)
    return data
  },
  async deleteSO(id: number): Promise<void> {
    await api.delete(`/admin/operating-systems/${id}`)
  },

  async tiposRelacionamento(): Promise<TipoRelacionamento[]> {
    const { data } = await api.get<TipoRelacionamento[]>('/admin/relationship-types')
    return data
  },
  async createTipoRelacionamento(payload: Omit<TipoRelacionamento, 'id'>): Promise<TipoRelacionamento> {
    const { data } = await api.post<TipoRelacionamento>('/admin/relationship-types', payload)
    return data
  },
  async updateTipoRelacionamento(id: number, payload: Omit<TipoRelacionamento, 'id'>): Promise<TipoRelacionamento> {
    const { data } = await api.put<TipoRelacionamento>(`/admin/relationship-types/${id}`, payload)
    return data
  },
  async deleteTipoRelacionamento(id: number): Promise<void> {
    await api.delete(`/admin/relationship-types/${id}`)
  }
}

// ===== Infraestrutura (somente leitura — criação via automação) =====
export const infraService = {
  async aplicacoes(): Promise<Aplicacao[]> {
    const { data } = await api.get<Aplicacao[]>('/aplicacoes/')
    return data
  },
  async aplicacao(id: number): Promise<Aplicacao> {
    const { data } = await api.get<Aplicacao>(`/aplicacoes/${id}`)
    return data
  },
  async clusters(): Promise<Cluster[]> {
    const { data } = await api.get<Cluster[]>('/clusters/')
    return data
  },
  async namespaces(): Promise<Namespace[]> {
    const { data } = await api.get<Namespace[]>('/namespaces/')
    return data
  },
  async servicos(): Promise<Servico[]> {
    const { data } = await api.get<Servico[]>('/servicos/')
    return data
  },
  async servicosNegocio(): Promise<ServicoNegocio[]> {
    const { data } = await api.get<ServicoNegocio[]>('/servicos-negocio/')
    return data
  },
  async instancias(aplicacaoId?: number): Promise<InstanciaAplicacao[]> {
    const params = aplicacaoId ? { aplicacao_id: aplicacaoId } : undefined
    const { data } = await api.get<InstanciaAplicacao[]>('/instancias-aplicacao/', { params })
    return data
  },
  async tiposRelacionamento(): Promise<TipoRelacionamento[]> {
    const { data } = await api.get<TipoRelacionamento[]>('/tipos-relacionamento/')
    return data
  },
  async relacionamentos(params?: { origem_id?: number; destino_id?: number; skip?: number; limit?: number }): Promise<Relacionamento[]> {
    const { data } = await api.get<Relacionamento[]>('/relacionamentos/', { params })
    return data
  }
}

// ===== Auditoria =====
export const auditService = {
  async list(params?: { entidade?: string; entidade_id?: number; skip?: number; limit?: number }): Promise<AuditLog[]> {
    const { data } = await api.get<AuditLog[]>('/audit-logs/', { params })
    return data
  }
}