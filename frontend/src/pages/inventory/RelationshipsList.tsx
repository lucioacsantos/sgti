import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { relationshipApi } from '../../lib/api'
import { Search, Filter, Plus, Download } from 'lucide-react'
import clsx from 'clsx'

export function RelationshipsList() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [page] = useState(1)
  const pageSize = 20
  const [filters, setFilters] = useState({ tipo_id: '', origem_id: '', destino_id: '' })
  const [showFilters, setShowFilters] = useState(false)

  const { data: types } = useQuery({ queryKey: ['relationship-types'], queryFn: relationshipApi.types.list })

  const { data: relationships, isLoading } = useQuery({
    queryKey: ['relationships', { search, page, pageSize, filters }],
    queryFn: () => relationshipApi.list({
      skip: (page - 1) * pageSize,
      limit: pageSize,
    }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => relationshipApi.delete(id.toString()),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['relationships'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Relacionamentos</h1>
          <p className="text-secondary-500">Gerenciar conexões entre ativos</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary">
            <Download className="h-4 w-4" />
            Exportar
          </button>
          <button className="btn-primary">
            <Plus className="h-4 w-4" />
            Novo Relacionamento
          </button>
        </div>
      </div>

      <div className="card p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-secondary-400" />
            <input
              type="search"
              placeholder="Buscar por origem, destino, tipo..."
              className="input pl-10"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <button
            className={clsx('btn-secondary flex items-center gap-2', showFilters && 'bg-primary-50 border-primary-300 text-primary-700')}
            onClick={() => setShowFilters(!showFilters)}
          >
            <Filter className="h-4 w-4" />
            Filtros
          </button>
          <span className="text-sm text-secondary-500">{(Array.isArray(relationships) ? relationships.length : 0)} relacionamentos</span>
        </div>

        {showFilters && (
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-3 gap-4 pt-4 border-t border-secondary-200">
            <div>
              <label className="label">Tipo de Relacionamento</label>
              <select
                className="input"
                value={filters.tipo_id}
                onChange={(e) => setFilters(prev => ({ ...prev, tipo_id: e.target.value }))}
              >
                <option value="">Todos</option>
                {(Array.isArray(types) ? types : []).map((t: any) => <option key={t.id} value={t.id}>{t.nome}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Origem (Host ID)</label>
              <input
                type="number"
                className="input"
                placeholder="ID do host origem"
                value={filters.origem_id}
                onChange={(e) => setFilters(prev => ({ ...prev, origem_id: e.target.value }))}
              />
            </div>
            <div>
              <label className="label">Destino (Host ID)</label>
              <input
                type="number"
                className="input"
                placeholder="ID do host destino"
                value={filters.destino_id}
                onChange={(e) => setFilters(prev => ({ ...prev, destino_id: e.target.value }))}
              />
            </div>
          </div>
        )}
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full" role="grid">
            <thead className="bg-secondary-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Origem</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Tipo</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Destino</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Descrição</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Criado em</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-secondary-500 uppercase tracking-wider">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-secondary-200">
              {isLoading ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <div className="animate-spin rounded-full h-6 w-6 border-2 border-primary-500 border-t-transparent"></div>
                      <span className="text-secondary-500">Carregando...</span>
                    </div>
                  </td>
                </tr>
              ) : Array.isArray(relationships) && relationships.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-secondary-500">
                    Nenhum relacionamento encontrado
                  </td>
                </tr>
              ) : (
                (Array.isArray(relationships) ? relationships : []).map((rel: any) => (
                  <tr key={rel.id} className="hover:bg-secondary-50">
                    <td className="px-4 py-3">
                      <div className="font-medium text-secondary-900">{rel.origem?.nome || `ID: ${rel.origem_id}`}</div>
                      <div className="text-sm text-secondary-500">{rel.origem?.tipo?.nome || 'Host'}</div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="badge badge-primary">{rel.tipo?.nome || 'N/A'}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-secondary-900">{rel.destino?.nome || `ID: ${rel.destino_id}`}</div>
                      <div className="text-sm text-secondary-500">{rel.destino?.tipo?.nome || 'Host'}</div>
                    </td>
                    <td className="px-4 py-3 text-sm text-secondary-700 max-w-xs truncate">{rel.descricao || '—'}</td>
                    <td className="px-4 py-3 text-sm text-secondary-500 whitespace-nowrap">
                      {new Date(rel.created_at).toLocaleDateString('pt-BR')}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button className="p-2 rounded-lg hover:bg-secondary-100 text-secondary-500" title="Ver detalhes">
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg>
                        </button>
                        <button className="p-2 rounded-lg hover:bg-secondary-100 text-secondary-500" title="Editar">
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg>
                        </button>
                        <button
                          className="p-2 rounded-lg hover:bg-red-50 text-red-500"
                          title="Excluir"
                          onClick={() => deleteMutation.mutate(rel.id)}
                        >
                          <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg>
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

      </div>
    </div>
  )
}