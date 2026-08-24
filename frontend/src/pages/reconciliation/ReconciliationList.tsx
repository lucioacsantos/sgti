import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { collectionApi } from '../../lib/api'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { Search, RefreshCw, AlertTriangle, CheckCircle, Clock, Eye, Plus } from 'lucide-react'
import clsx from 'clsx'

export function ReconciliationList() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [page] = useState(1)
  const [statusFilter, setStatusFilter] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const pageSize = 20

  const { data: sessions, isLoading, refetch } = useQuery({
    queryKey: ['reconciliation-sessions', { page, pageSize, status: statusFilter }],
    queryFn: () => collectionApi.reconciliation.sessions.list({ status: statusFilter || undefined }),
  })

  const createMutation = useMutation({
    mutationFn: (data: any) => collectionApi.reconciliation.sessions.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reconciliation-sessions'] })
      setShowCreateModal(false)
    },
  })

  const statusConfig = {
    pending: { label: 'Pendente', color: 'secondary', icon: Clock },
    running: { label: 'Executando', color: 'blue', icon: RefreshCw },
    completed: { label: 'Concluído', color: 'green', icon: CheckCircle },
    failed: { label: 'Falhou', color: 'red', icon: AlertTriangle },
    cancelled: { label: 'Cancelado', color: 'secondary', icon: AlertTriangle },
  }

  const getSeverityColor = (count: number) => {
    if (count > 10) return 'text-red-600'
    if (count > 5) return 'text-yellow-600'
    if (count > 0) return 'text-blue-600'
    return 'text-green-600'
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Reconciliação</h1>
          <p className="text-secondary-500">Comparar e reconciliar dados entre fontes</p>
        </div>
        <div className="flex gap-2">
          <button
            className="btn-secondary"
            onClick={() => refetch()}
            disabled={isLoading}
          >
            <RefreshCw className={clsx('h-4 w-4', isLoading && 'animate-spin')} />
            Atualizar
          </button>
          <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
            <Plus className="h-4 w-4" />
            Nova Reconciliação
          </button>
        </div>
      </div>

      <div className="card p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-secondary-400" />
            <input
              type="search"
              placeholder="Buscar por nome..."
              className="input pl-10"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select
            className="input w-auto"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="">Todos os status</option>
            <option value="pending">Pendente</option>
            <option value="running">Executando</option>
            <option value="completed">Concluído</option>
            <option value="failed">Falhou</option>
            <option value="cancelled">Cancelado</option>
          </select>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full" role="grid">
            <thead className="bg-secondary-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Nome</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Fontes</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Progresso</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Conflitos</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Iniciado em</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-secondary-500 uppercase tracking-wider">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-secondary-200">
              {isLoading ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center">
                    <div className="flex items-center justify-center gap-2">
                      <div className="animate-spin rounded-full h-6 w-6 border-2 border-primary-500 border-t-transparent"></div>
                      <span className="text-secondary-500">Carregando...</span>
                    </div>
                  </td>
                </tr>
              ) : Array.isArray(sessions) && sessions.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-secondary-500">
                    Nenhuma sessão de reconciliação encontrada
                  </td>
                </tr>
              ) : (
                (Array.isArray(sessions) ? sessions : []).map((session: any) => {
                  const status = statusConfig[session.status as keyof typeof statusConfig] || statusConfig.pending
                  const StatusIcon = status.icon
                  const totalConflicts = session.conflicts_found || 0
                  const criticalConflicts = 0 // Would need separate query

                  return (
                    <tr key={session.id} className="hover:bg-secondary-50">
                      <td className="px-4 py-3 font-medium text-secondary-900">{session.name}</td>
                      <td className="px-4 py-3 text-sm text-secondary-600">
                        {session.source_ids?.length || 0} fontes
                      </td>
                      <td className="px-4 py-3">
                        <span className={clsx('badge flex items-center gap-1', `badge-${status.color}`)}>
                          <StatusIcon className="h-3 w-3" />
                          {status.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="w-32">
                          <div className="h-2 bg-secondary-200 rounded-full overflow-hidden">
                            <div
                              className={clsx('h-full rounded-full transition-all', session.status === 'completed' ? 'bg-green-500' : session.status === 'failed' ? 'bg-red-500' : 'bg-primary-500')}
                              style={{ width: `${session.progress_percent || 0}%` }}
                            />
                          </div>
                          <span className="text-xs text-secondary-500 mt-1">{session.progress_percent?.toFixed(1) || 0}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <span className={clsx('font-mono font-medium', getSeverityColor(totalConflicts))}>
                            {totalConflicts}
                          </span>
                          {totalConflicts > 0 && (
                            <span className="badge badge-warning text-xs">{criticalConflicts} críticos</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3 text-sm text-secondary-500">
                        {session.started_at ? formatDistanceToNow(new Date(session.started_at), { addSuffix: true, locale: ptBR }) : '—'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button className="p-2 rounded-lg hover:bg-secondary-100 text-secondary-500" title="Ver detalhes">
                            <Eye className="h-4 w-4" />
                          </button>
                          {session.status === 'completed' && totalConflicts > 0 && (
                            <button className="p-2 rounded-lg hover:bg-primary-50 text-primary-600" title="Ver conflitos">
                              <AlertTriangle className="h-4 w-4" />
                            </button>
                          )}
                          {session.status === 'pending' && (
                            <button className="p-2 rounded-lg hover:bg-green-50 text-green-600" title="Executar">
                              <RefreshCw className="h-4 w-4" />
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>

      </div>

      {/* Create Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-secondary-200">
              <h2 className="text-xl font-bold text-secondary-900">Nova Reconciliação</h2>
            </div>
            <form onSubmit={(e) => { e.preventDefault(); createMutation.mutate({ name: '', description: '', source_ids: [], primary_source_id: '', entity_types: [], filters: {} }) }}>
              <div className="p-6 space-y-4">
                <div>
                  <label className="label">Nome</label>
                  <input type="text" className="input" placeholder="Ex: Daily vCenter vs Satellite" required />
                </div>
                <div>
                  <label className="label">Descrição</label>
                  <textarea className="input" rows={3} placeholder="Descrição da reconciliação" />
                </div>
                <div>
                  <label className="label">Fonte Primária</label>
                  <select className="input" required>
                    <option value="">Selecione a fonte primária</option>
                  </select>
                </div>
                <div>
                  <label className="label">Fontes Secundárias</label>
                  <select className="input" multiple required>
                    <option value="">Selecione as fontes para comparar</option>
                  </select>
                </div>
                <div>
                  <label className="label">Tipos de Entidade</label>
                  <select className="input" multiple>
                    <option value="vcenter_vm">VMs vCenter</option>
                    <option value="physical_server">Servidores Físicos</option>
                    <option value="vcenter_host">Hosts vCenter</option>
                  </select>
                </div>
              </div>
              <div className="p-4 border-t border-secondary-200 flex justify-end gap-2">
                <button type="button" className="btn-secondary" onClick={() => setShowCreateModal(false)}>Cancelar</button>
                <button type="submit" className="btn-primary" disabled={createMutation.isPending}>
                  {createMutation.isPending ? 'Criando...' : 'Criar Reconciliação'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}