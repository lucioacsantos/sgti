import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { assetApi, referenceApi } from '../../lib/api'
import { Search, Filter, Plus, Download, Columns, ChevronDown } from 'lucide-react'
import clsx from 'clsx'

const columns = [
  { key: 'nome', label: 'Nome', sortable: true },
  { key: 'tipo', label: 'Tipo', sortable: true },
  { key: 'ambiente', label: 'Ambiente', sortable: true },
  { key: 'status', label: 'Status', sortable: true },
  { key: 'criticidade', label: 'Criticidade', sortable: true },
  { key: 'sor', label: 'SO', sortable: false },
  { key: 'areas', label: 'Área', sortable: true },
  { key: 'created_at', label: 'Criado em', sortable: true },
]

export function HostsList() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [page] = useState(1)
  const [sort, setSort] = useState<{ key: string; dir: 'asc' | 'desc' }>({ key: 'created_at', dir: 'desc' })
  const [filters, setFilters] = useState({ tipo_id: '', ambiente_id: '', status_id: '', criticidade_id: '' })
  const [showFilters, setShowFilters] = useState(false)
  const [selectedIds, setSelectedIds] = useState<number[]>([])

  const { data: types } = useQuery({ queryKey: ['asset-types'], queryFn: referenceApi.assetTypes })
  
  const { data: environments } = useQuery({ queryKey: ['environments'], queryFn: referenceApi.environments })
  
  const { data: statuses } = useQuery({ queryKey: ['statuses'], queryFn: referenceApi.statuses })
  
  const { data: criticities } = useQuery({ queryKey: ['criticities'], queryFn: referenceApi.criticities })

  const { data: assets, isLoading } = useQuery({
    queryKey: ['hosts', { search, page, pageSize: 20, sort, filters }],
    queryFn: () => assetApi.list({
      skip: (page - 1) * 20,
      limit: 20,
      search,
      // Add sort and filters when backend supports them
    }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => assetApi.delete(id.toString()),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['hosts'] }),
  })

  const handleSort = (key: string) => {
    setSort(prev => ({
      key,
      dir: prev.key === key && prev.dir === 'asc' ? 'desc' : 'asc',
    }))
  }

  const handleSelectionChange = (id: number, checked: boolean) => {
    setSelectedIds(prev => checked ? [...prev, id] : prev.filter(x => x !== id))
  }

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedIds((Array.isArray(assets) ? assets : []).map((a: any) => a.id))
    } else {
      setSelectedIds([])
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Hosts</h1>
          <p className="text-secondary-500">Gerenciar ativos de infraestrutura</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary">
            <Download className="h-4 w-4" />
            Exportar
          </button>
          <button className="btn-primary">
            <Plus className="h-4 w-4" />
            Novo Host
          </button>
        </div>
      </div>

      {/* Search and Filters */}
      <div className="card p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-secondary-400" />
            <input
              type="search"
              placeholder="Buscar por nome, IP, descrição..."
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

          <div className="flex items-center gap-2">
            <Columns className="h-5 w-5 text-secondary-400" />
            <span className="text-sm text-secondary-500">{(Array.isArray(assets) ? assets.length : 0)} hosts</span>
          </div>
        </div>

        {showFilters && (
          <div className="mt-4 grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-4 border-t border-secondary-200">
            <div>
              <label className="label">Tipo de Ativo</label>
              <select
                className="input"
                value={filters.tipo_id}
                onChange={(e) => setFilters(prev => ({ ...prev, tipo_id: e.target.value }))}
              >
                <option value="">Todos</option>
                {types?.map((t: any) => <option key={t.id} value={t.id}>{t.nome}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Ambiente</label>
              <select
                className="input"
                value={filters.ambiente_id}
                onChange={(e) => setFilters(prev => ({ ...prev, ambiente_id: e.target.value }))}
              >
                <option value="">Todos</option>
                {environments?.map((e: any) => <option key={e.id} value={e.id}>{e.nome}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Status</label>
              <select
                className="input"
                value={filters.status_id}
                onChange={(e) => setFilters(prev => ({ ...prev, status_id: e.target.value }))}
              >
                <option value="">Todos</option>
                {statuses?.map((s: any) => <option key={s.id} value={s.id}>{s.nome}</option>)}
              </select>
            </div>
            <div>
              <label className="label">Criticidade</label>
              <select
                className="input"
                value={filters.criticidade_id}
                onChange={(e) => setFilters(prev => ({ ...prev, criticidade_id: e.target.value }))}
              >
                <option value="">Todos</option>
                {criticities?.map((c: any) => <option key={c.id} value={c.id}>{c.nivel}</option>)}
              </select>
            </div>
          </div>
        )}
      </div>

      {/* Table */}
      <div className="card overflow-hidden">
        {selectedIds.length > 0 && (
          <div className="p-3 bg-primary-50 border-b border-secondary-200 flex items-center justify-between">
            <span className="text-sm font-medium text-primary-700">{selectedIds.length} selecionados</span>
            <div className="flex gap-2">
              <button className="btn-secondary text-sm">Editar em lote</button>
              <button className="btn-danger text-sm" onClick={() => deleteMutation.mutate(selectedIds[0])}>Excluir</button>
            </div>
          </div>
        )}

        <div className="overflow-x-auto">
          <table className="w-full" role="grid">
            <thead className="bg-secondary-50">
              <tr>
                <th className="w-12 px-4 py-3">
                  <input
                    type="checkbox"
                    checked={selectedIds.length === (Array.isArray(assets) ? assets.length : 0) && (Array.isArray(assets) ? assets.length : 0) > 0}
                    onChange={(e) => handleSelectAll(e.target.checked)}
                    className="rounded border-secondary-300 text-primary-600 focus:ring-primary-500"
                  />
                </th>
                {columns.map(col => (
                  <th
                    key={col.key}
                    className={clsx('px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider cursor-pointer hover:bg-secondary-100', col.sortable && 'select-none')}
                    onClick={() => col.sortable && handleSort(col.key)}
                    style={{ width: col.key === 'nome' ? '250px' : undefined }}
                  >
                    <div className="flex items-center gap-1">
                      {col.label}
                      {col.sortable && sort.key === col.key && (
                        <ChevronDown className={clsx('h-4 w-4', sort.dir === 'desc' && 'rotate-180')} />
                      )}
                    </div>
                  </th>
                ))}
                <th className="px-4 py-3 text-right">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-secondary-200">
              {isLoading ? (
                <tr>
                  <td colSpan={columns.length + 2} className="px-4 py-8 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <div className="animate-spin rounded-full h-6 w-6 border-2 border-primary-500 border-t-transparent"></div>
                      <span className="text-secondary-500">Carregando...</span>
                    </div>
                  </td>
                </tr>
              ) : Array.isArray(assets) && assets.length === 0 ? (
                <tr>
                  <td colSpan={columns.length + 2} className="px-4 py-8 text-center text-secondary-500">
                    Nenhum host encontrado
                  </td>
                </tr>
              ) : (
                (Array.isArray(assets) ? assets : []).map((asset: any) => (
                  <tr key={asset.id} className="hover:bg-secondary-50">
                    <td className="px-4 py-3">
                      <input
                        type="checkbox"
                        checked={selectedIds.includes(asset.id)}
                        onChange={(e) => handleSelectionChange(asset.id, e.target.checked)}
                        className="rounded border-secondary-300 text-primary-600 focus:ring-primary-500"
                      />
                    </td>
                    <td className="px-4 py-3">
                      <div className="font-medium text-secondary-900">{asset.nome}</div>
                      {asset.descricao && <div className="text-sm text-secondary-500 truncate max-w-xs">{asset.descricao}</div>}
                    </td>
                    <td className="px-4 py-3 text-sm text-secondary-700">{asset.tipo?.nome || '—'}</td>
                    <td className="px-4 py-3 text-sm text-secondary-700">{asset.ambiente?.nome || '—'}</td>
                    <td className="px-4 py-3">
                      <span className={clsx('badge', asset.status?.nome === 'Ativo' ? 'badge-success' : 'badge-secondary')}>
                        {asset.status?.nome || '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={clsx('badge', 
                        asset.criticidade?.nivel === 'Crítica' ? 'badge-danger' :
                        asset.criticidade?.nivel === 'Alta' ? 'badge-warning' :
                        asset.criticidade?.nivel === 'Média' ? 'badge-primary' : 'badge-secondary'
                      )}>
                        {asset.criticidade?.nivel || '—'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-secondary-700">{asset.sor?.abreviacao || '—'}</td>
                    <td className="px-4 py-3 text-sm text-secondary-700">{asset.areas?.sigla || '—'}</td>
                    <td className="px-4 py-3 text-sm text-secondary-500 whitespace-nowrap">
                      {new Date(asset.created_at).toLocaleDateString('pt-BR')}
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
                          onClick={() => deleteMutation.mutate(asset.id)}
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