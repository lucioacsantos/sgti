import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { collectionApi } from '../../lib/api'
import { useAuthStore } from '../../store/auth'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import {
  Search, ShieldCheck, AlertTriangle, Clock, CheckCircle, XCircle,
  User, FileText, RefreshCw, Flag
} from 'lucide-react'
import clsx from 'clsx'

const statusConfig = {
  pending: { label: 'Pendente', color: 'secondary', icon: Clock },
  in_review_analyst: { label: 'Em Análise (Analista)', color: 'blue', icon: User },
  in_review_reviewer: { label: 'Em Revisão (Revisor)', color: 'purple', icon: FileText },
  approved: { label: 'Aprovado', color: 'green', icon: CheckCircle },
  rejected: { label: 'Rejeitado', color: 'red', icon: XCircle },
  escalated: { label: 'Escalado', color: 'orange', icon: Flag },
  expired: { label: 'Expirado', color: 'secondary', icon: Clock },
  cancelled: { label: 'Cancelado', color: 'secondary', icon: XCircle },
}

const priorityConfig = {
  1: { label: 'Crítica', color: 'red', icon: AlertTriangle },
  2: { label: 'Alta', color: 'orange', icon: Flag },
  3: { label: 'Média', color: 'blue', icon: FileText },
  4: { label: 'Baixa', color: 'secondary', icon: Clock },
}

export function CertificationQueue() {
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const [search, setSearch] = useState('')
  const [statusFilter, setStatusFilter] = useState('')
  const [roleFilter, setRoleFilter] = useState<'analyst' | 'reviewer' | 'all'>('all')

  const isAnalyst = user?.roles.includes('analyst') || user?.roles.includes('reconciliator')
  const isReviewer = user?.roles.includes('reviewer') || user?.roles.includes('revisor')

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['certification-requests', { status: statusFilter, assignee: roleFilter === 'all' ? undefined : user?.id, role: roleFilter }],
    queryFn: () => collectionApi.certification.requests.list({
      status: statusFilter || undefined,
      assignee_id: roleFilter === 'all' ? undefined : user?.id,
    }),
  })

  const actionMutation = useMutation({
    mutationFn: ({ id, role, decision, notes }: { id: string; role: string; decision: string; notes?: string }) =>
      collectionApi.certification.requests.action(id, { role, decision, notes, decided_by: user?.id || '' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['certification-requests'] })
    },
  })

  const myQueue = data?.filter(req => 
    (isAnalyst && req.analyst_id === user?.id && ['pending', 'in_review_analyst'].includes(req.status)) ||
    (isReviewer && req.reviewer_id === user?.id && req.status === 'in_review_reviewer')
  ) || []

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Fila de Certificação</h1>
          <p className="text-secondary-500">Revisar e aprovar conflitos de dados</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={clsx('h-4 w-4', isLoading && 'animate-spin')} />
            Atualizar
          </button>
        </div>
      </div>

      {/* My Queue Summary */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="card p-4 border-l-4 border-blue-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-secondary-500">Minha Fila - Analista</p>
              <p className="text-2xl font-bold text-secondary-900 mt-1">
                {myQueue.filter(r => r.status === 'pending' || r.status === 'in_review_analyst').length}
              </p>
            </div>
            <User className="h-8 w-8 text-blue-500" />
          </div>
        </div>
        <div className="card p-4 border-l-4 border-purple-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-secondary-500">Minha Fila - Revisor</p>
              <p className="text-2xl font-bold text-secondary-900 mt-1">
                {myQueue.filter(r => r.status === 'in_review_reviewer').length}
              </p>
            </div>
            <FileText className="h-8 w-8 text-purple-500" />
          </div>
        </div>
        <div className="card p-4 border-l-4 border-red-500">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-secondary-500">SLA Vencendo (24h)</p>
              <p className="text-2xl font-bold text-secondary-900 mt-1">
                {data?.filter(r => {
                  if (!r.due_at) return false
                  const hoursLeft = (new Date(r.due_at).getTime() - Date.now()) / (1000 * 60 * 60)
                  return hoursLeft > 0 && hoursLeft <= 24
                }).length || 0}
              </p>
            </div>
            <Clock className="h-8 w-8 text-red-500" />
          </div>
        </div>
      </div>

      {/* Filters */}
      <div className="card p-4">
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-secondary-400" />
            <input
              type="search"
              placeholder="Buscar por título, ID..."
              className="input pl-10"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <select className="input w-auto" value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="">Todos os status</option>
            <option value="pending">Pendente</option>
            <option value="in_review_analyst">Em Análise (Analista)</option>
            <option value="in_review_reviewer">Em Revisão (Revisor)</option>
            <option value="approved">Aprovado</option>
            <option value="rejected">Rejeitado</option>
            <option value="escalated">Escalado</option>
            <option value="expired">Expirado</option>
          </select>
          <select className="input w-auto" value={roleFilter} onChange={(e) => setRoleFilter(e.target.value as any)}>
            <option value="all">Todas</option>
            <option value="analyst">Analista</option>
            <option value="reviewer">Revisor</option>
          </select>
        </div>
      </div>

      {/* Queue Table */}
      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full" role="grid">
            <thead className="bg-secondary-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Prioridade</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Título</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Responsável</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Vencimento</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Conflitos</th>
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
              ) : data?.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-secondary-500">
                    Nenhuma solicitação de certificação encontrada
                  </td>
                </tr>
              ) : (
                data?.map((request) => {
                  const status = statusConfig[request.status as keyof typeof statusConfig] || statusConfig.pending
                  const priority = priorityConfig[request.priority as keyof typeof priorityConfig] || priorityConfig[3]
                  const StatusIcon = status.icon
                  const PriorityIcon = priority.icon

                  const hoursLeft = request.due_at ? (new Date(request.due_at).getTime() - Date.now()) / (1000 * 60 * 60) : null
                  const isOverdue = hoursLeft !== null && hoursLeft < 0
                  const isDueSoon = hoursLeft !== null && hoursLeft > 0 && hoursLeft <= 24

                  return (
                    <tr key={request.id} className="hover:bg-secondary-50">
                      <td className="px-4 py-3">
                        <span className={clsx('badge flex items-center gap-1', `badge-${priority.color}`)}>
                          <PriorityIcon className="h-3 w-3" />
                          {priority.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-secondary-900">{request.title}</div>
                        <div className="text-sm text-secondary-500 truncate max-w-xs">{request.description}</div>
                      </td>
                      <td className="px-4 py-3">
                        <span className={clsx('badge flex items-center gap-1', `badge-${status.color}`)}>
                          <StatusIcon className="h-3 w-3" />
                          {status.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2 text-sm">
                          {request.status === 'pending' || request.status === 'in_review_analyst' ? (
                            <div className="flex items-center gap-1 text-secondary-600">
                              <User className="h-4 w-4" />
                              <span>{request.analyst_id || 'Não atribuído'}</span>
                            </div>
                          ) : request.status === 'in_review_reviewer' ? (
                            <div className="flex items-center gap-1 text-secondary-600">
                              <FileText className="h-4 w-4" />
                              <span>{request.reviewer_id || 'Não atribuído'}</span>
                            </div>
                          ) : (
                            <span className="text-secondary-500">—</span>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        {request.due_at && (
                          <div className={clsx('flex items-center gap-1 text-sm', isOverdue ? 'text-red-600' : isDueSoon ? 'text-yellow-600' : 'text-secondary-600')}>
                            <Clock className="h-4 w-4" />
                            <span>
                              {isOverdue ? 'VENCIDO' : isDueSoon ? `${Math.round(hoursLeft!)}h` : formatDistanceToNow(new Date(request.due_at), { addSuffix: true, locale: ptBR })}
                            </span>
                          </div>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className="font-mono text-secondary-700">{request.conflict_ids?.length || 0}</span>
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button
                            className="p-2 rounded-lg hover:bg-secondary-100 text-secondary-500"
                            onClick={() => actionMutation.mutate({ id: request.id, role: 'analyst', decision: 'approve' })}
                            disabled={!isAnalyst || !['pending', 'in_review_analyst'].includes(request.status)}
                          >
                            <ShieldCheck className="h-4 w-4" />
                          </button>
                          <button
                            className="p-2 rounded-lg hover:bg-secondary-100 text-secondary-500"
                            onClick={() => actionMutation.mutate({ id: request.id, role: 'analyst', decision: 'reject' })}
                            disabled={!isAnalyst || !['pending', 'in_review_analyst'].includes(request.status)}
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
                          <button
                            className="p-2 rounded-lg hover:bg-secondary-100 text-secondary-500"
                            onClick={() => actionMutation.mutate({ id: request.id, role: 'reviewer', decision: 'approve' })}
                            disabled={!isReviewer || request.status !== 'in_review_reviewer'}
                          >
                            <CheckCircle className="h-4 w-4" />
                          </button>
                          <button
                            className="p-2 rounded-lg hover:bg-secondary-100 text-secondary-500"
                            onClick={() => actionMutation.mutate({ id: request.id, role: 'reviewer', decision: 'reject' })}
                            disabled={!isReviewer || request.status !== 'in_review_reviewer'}
                          >
                            <XCircle className="h-4 w-4" />
                          </button>
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
    </div>
  )
}