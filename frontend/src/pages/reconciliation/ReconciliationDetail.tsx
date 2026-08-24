import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { collectionApi } from '../../lib/api'
import { format } from 'date-fns'
import { RefreshCw, AlertTriangle, CheckCircle, Clock, ChevronLeft, Eye, AlertCircle, Flag, Search, ShieldCheck, GitBranch, Server } from 'lucide-react'
import { useState } from 'react'
import clsx from 'clsx'

const statusConfig = {
  pending: { label: 'Pendente', color: 'secondary', icon: Clock },
  running: { label: 'Executando', color: 'blue', icon: RefreshCw },
  completed: { label: 'Concluído', color: 'green', icon: CheckCircle },
  failed: { label: 'Falhou', color: 'red', icon: AlertTriangle },
  cancelled: { label: 'Cancelado', color: 'secondary', icon: AlertTriangle },
}

const severityConfig = {
  critical: { label: 'Crítica', color: 'red', icon: AlertTriangle },
  high: { label: 'Alta', color: 'orange', icon: Flag },
  medium: { label: 'Média', color: 'blue', icon: AlertCircle },
  low: { label: 'Baixa', color: 'secondary', icon: Clock },
}

const resolutionConfig = {
  source_a_wins: { label: 'Fonte A Vence', color: 'blue' },
  source_b_wins: { label: 'Fonte B Vence', color: 'green' },
  merge: { label: 'Mesclar', color: 'purple' },
  manual: { label: 'Manual', color: 'orange' },
  auto_rule: { label: 'Regra Automática', color: 'green' },
  deferred: { label: 'Adiado', color: 'yellow' },
  escalated: { label: 'Escalado', color: 'red' },
}

export function ReconciliationDetail() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [severityFilter, setSeverityFilter] = useState('')
  const [resolutionFilter, setResolutionFilter] = useState('')
  const [showResolveModal, setShowResolveModal] = useState(false)
  const [selectedConflict, setSelectedConflict] = useState<any>(null)
  const [resolveForm, setResolveForm] = useState({ resolution: '', resolved_value: '', notes: '' })

  const { data: session, isLoading, error, refetch } = useQuery({
    queryKey: ['reconciliation-session', id],
    queryFn: () => collectionApi.reconciliation.sessions.get(id!),
    enabled: !!id,
  })

  const { data: conflicts, isLoading: conflictsLoading } = useQuery({
    queryKey: ['reconciliation-conflicts', id, { search, severity: severityFilter, resolution: resolutionFilter }],
    queryFn: () => collectionApi.reconciliation.conflicts.list(id!, { 
      severity: severityFilter || undefined, 
      resolved: resolutionFilter ? resolutionFilter !== 'unresolved' : undefined 
    }),
    enabled: !!id,
  })

  const resolveMutation = useMutation({
    mutationFn: ({ conflictId, data }: { conflictId: string; data: any }) =>
      collectionApi.reconciliation.conflicts.resolve(conflictId, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['reconciliation-conflicts', id] })
      queryClient.invalidateQueries({ queryKey: ['reconciliation-session', id] })
      setShowResolveModal(false)
      setSelectedConflict(null)
    },
  })

  const createCertMutation = useMutation({
    mutationFn: (data: any) => collectionApi.certification.requests.create(data),
    onSuccess: () => {
      setShowCreateCertModal(false)
    },
  })

  const [showCreateCertModal, setShowCreateCertModal] = useState(false)

  if (isLoading) {
    return <div className="flex items-center justify-center h-64"><RefreshCw className="h-12 w-12 animate-spin text-primary-600" /></div>
  }

  if (error || !session) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-secondary-900">Sessão não encontrada</h2>
        <p className="text-secondary-500 mt-2">A sessão de reconciliação solicitada não existe.</p>
      </div>
    )
  }

  const status = statusConfig[(session as any).status as keyof typeof statusConfig] || statusConfig.pending
  const StatusIcon = status.icon

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <nav className="flex items-center gap-2 text-sm text-secondary-500 mb-2">
            <a href="/reconciliation" className="hover:text-primary-600 flex items-center gap-1">
              <ChevronLeft className="h-4 w-4" />
              Reconciliação
            </a>
            <span className="text-secondary-900 font-medium">{session.name}</span>
          </nav>
          <div className="flex items-center gap-3">
            <span className={clsx('badge flex items-center gap-1', `badge-${status.color}`)}>
              <StatusIcon className="h-3 w-3" />
              {status.label}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          {session.status === 'pending' && (
            <button className="btn-primary" onClick={() => refetch()}>
              <RefreshCw className="h-4 w-4" />
              Executar
            </button>
          )}
          {session.status === 'completed' && session.conflicts_found > 0 && (
            <button className="btn-primary" onClick={() => setShowCreateCertModal(true)}>
              <ShieldCheck className="h-4 w-4" />
              Criar Certificação
            </button>
          )}
          <button className="btn-secondary" onClick={() => refetch()}>
            <RefreshCw className="h-4 w-4" />
            Atualizar
          </button>
        </div>
      </div>

      {/* Session Info Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-secondary-500">Fontes</p>
              <p className="text-2xl font-bold text-secondary-900 mt-1">{(session as any).source_ids?.length || 0}</p>
            </div>
            <div className="p-3 bg-primary-100 rounded-lg">
              <GitBranch className="h-6 w-6 text-primary-600" />
            </div>
          </div>
        </div>
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-secondary-500">Entidades Comparadas</p>
              <p className="text-2xl font-bold text-secondary-900 mt-1">{(session as any).total_entities_compared || 0}</p>
            </div>
            <div className="p-3 bg-blue-100 rounded-lg">
              <Server className="h-6 w-6 text-blue-600" />
            </div>
          </div>
        </div>
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-secondary-500">Conflitos Encontrados</p>
              <p className="text-2xl font-bold text-secondary-900 mt-1">{(session as any).conflicts_found || 0}</p>
            </div>
            <div className="p-3 bg-red-100 rounded-lg">
              <AlertTriangle className="h-6 w-6 text-red-600" />
            </div>
          </div>
        </div>
        <div className="card p-6">
          <div className="flex items-center justify-between">
            <div>
              <p className="text-sm font-medium text-secondary-500">Resolvidos</p>
              <p className="text-2xl font-bold text-secondary-900 mt-1">
                {(session as any).conflicts_resolved || 0} / {(session as any).conflicts_found || 0}
              </p>
            </div>
            <div className="p-3 bg-green-100 rounded-lg">
              <CheckCircle className="h-6 w-6 text-green-600" />
            </div>
          </div>
        </div>
      </div>

      {/* Progress & Timing */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 card p-6">
          <h3 className="text-lg font-semibold text-secondary-900 mb-4">Progresso</h3>
          <div className="space-y-2">
            <div className="flex justify-between text-sm">
              <span className="text-secondary-500">Progresso Geral</span>
              <span className="font-medium text-secondary-900">{(session as any).progress_percent?.toFixed(1) || 0}%</span>
            </div>
            <div className="h-4 bg-secondary-200 rounded-full overflow-hidden">
              <div
                className={clsx('h-full rounded-full transition-all', session.status === 'completed' ? 'bg-green-500' : session.status === 'failed' ? 'bg-red-500' : 'bg-primary-500')}
                style={{ width: `${(session as any).progress_percent || 0}%` }}
              />
            </div>
          </div>
        </div>

        <div className="card p-6">
          <h3 className="text-lg font-semibold text-secondary-900 mb-4">Tempo</h3>
          <dl className="space-y-3 text-sm">
            <div className="flex justify-between">
              <dt className="text-secondary-500">Iniciado em</dt>
              <dd className="font-medium text-secondary-900">{(session as any).started_at ? format(new Date((session as any).started_at), 'dd/MM/yyyy HH:mm') : '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-secondary-500">Concluído em</dt>
              <dd className="font-medium text-secondary-900">{(session as any).completed_at ? format(new Date((session as any).completed_at), 'dd/MM/yyyy HH:mm') : '—'}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-secondary-500">Duração</dt>
              <dd className="font-medium text-secondary-900">{(session as any).duration_seconds ? `${Math.round((session as any).duration_seconds / 60)} min` : '—'}</dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Conflicts Table */}
      <div className="card">
        <div className="p-4 border-b border-secondary-200 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <h3 className="text-lg font-semibold text-secondary-900">Conflitos {(Array.isArray(conflicts) ? conflicts.length : 0)}</h3>
          <div className="flex flex-col sm:flex-row gap-3 w-full sm:w-auto">
            <div className="relative flex-1 max-w-md">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-secondary-400" />
              <input type="search" placeholder="Buscar conflitos..." className="input pl-10" value={search} onChange={(e) => setSearch(e.target.value)} />
            </div>
            <select className="input w-auto" value={severityFilter} onChange={(e) => setSeverityFilter(e.target.value)}>
              <option value="">Todas as severidades</option>
              <option value="critical">Crítica</option>
              <option value="high">Alta</option>
              <option value="medium">Média</option>
              <option value="low">Baixa</option>
            </select>
            <select className="input w-auto" value={resolutionFilter} onChange={(e) => setResolutionFilter(e.target.value)}>
              <option value="">Todas as resoluções</option>
              <option value="unresolved">Não resolvidos</option>
              <option value="source_a_wins">Fonte A Vence</option>
              <option value="source_b_wins">Fonte B Vence</option>
              <option value="merge">Mesclar</option>
              <option value="manual">Manual</option>
              <option value="auto_rule">Regra Automática</option>
              <option value="deferred">Adiado</option>
              <option value="escalated">Escalado</option>
            </select>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full" role="grid">
            <thead className="bg-secondary-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Severidade</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Tipo</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Descrição</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Origem</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Destino</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Atributo</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Valor A</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Valor B</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Resolução</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-secondary-500 uppercase tracking-wider">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-secondary-200">
              {conflictsLoading ? (
                <tr><td colSpan={11} className="px-4 py-8 text-center"><div className="flex items-center justify-center gap-2"><RefreshCw className="h-6 w-6 animate-spin text-primary-600" /><span className="text-secondary-500">Carregando...</span></div></td></tr>
              ) : Array.isArray(conflicts) && conflicts.length === 0 ? (
                <tr><td colSpan={11} className="px-4 py-8 text-center text-secondary-500">Nenhum conflito encontrado</td></tr>
              ) : (
                (Array.isArray(conflicts) ? conflicts : []).map((conflict: any) => {
                  const severity = severityConfig[conflict.severity as keyof typeof severityConfig] || severityConfig.low
                  const resolution = conflict.resolution ? resolutionConfig[conflict.resolution as keyof typeof resolutionConfig] : null
                  const SeverityIcon = severity.icon

                  return (
                    <tr key={conflict.id} className="hover:bg-secondary-50">
                      <td className="px-4 py-3">
                        <span className={clsx('badge flex items-center gap-1', `badge-${severity.color}`)}>
                          <SeverityIcon className="h-3 w-3" />
                          {severity.label}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-sm text-secondary-700">{conflict.conflict_type}</td>
                      <td className="px-4 py-3 text-sm text-secondary-700 max-w-xs truncate" title={conflict.description}>{conflict.description}</td>
                      <td className="px-4 py-3 text-sm text-secondary-700">{conflict.details?.entity_a_name || '—'}</td>
                      <td className="px-4 py-3 text-sm text-secondary-700">{conflict.details?.entity_b_name || '—'}</td>
                      <td className="px-4 py-3 text-sm text-secondary-700 font-mono">{conflict.attribute_name || '—'}</td>
                      <td className="px-4 py-3 text-sm text-secondary-700 font-mono text-xs max-w-xs truncate">{JSON.stringify(conflict.value_a)}</td>
                      <td className="px-4 py-3 text-sm text-secondary-700 font-mono text-xs max-w-xs truncate">{JSON.stringify(conflict.value_b)}</td>
                      <td className="px-4 py-3">
                        {resolution ? (
                          <span className={clsx('badge', `badge-${resolution.color}`)}>{resolution.label}</span>
                        ) : (
                          <span className="badge badge-secondary">Pendente</span>
                        )}
                      </td>
                      <td className="px-4 py-3 text-right">
                        <div className="flex items-center justify-end gap-1">
                          <button className="p-2 rounded-lg hover:bg-secondary-100 text-secondary-500" title="Ver detalhes">
                            <Eye className="h-4 w-4" />
                          </button>
                          {!conflict.resolution && (
                            <button
                              className="p-2 rounded-lg hover:bg-primary-50 text-primary-600"
                              onClick={() => {
                                setSelectedConflict(conflict)
                                setResolveForm({ resolution: 'source_a_wins', resolved_value: '', notes: '' })
                                setShowResolveModal(true)
                              }}
                            >
                              <CheckCircle className="h-4 w-4" />
                            </button>
                          )}
                          {conflict.requires_certification && !conflict.certification_request_id && (
                            <button className="p-2 rounded-lg hover:bg-purple-50 text-purple-600" title="Criar certificação">
                              <ShieldCheck className="h-4 w-4" />
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

      {/* Resolve Modal */}
      {showResolveModal && selectedConflict && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl shadow-xl max-w-2xl w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-secondary-200">
              <h2 className="text-xl font-bold text-secondary-900">Resolver Conflito</h2>
              <p className="text-secondary-500 mt-1">{selectedConflict.description}</p>
            </div>
            <form onSubmit={(e) => { e.preventDefault(); resolveMutation.mutate({ conflictId: selectedConflict.id, data: resolveForm }) }}>
              <div className="p-6 space-y-4">
                <div>
                  <label className="label">Resolução</label>
                  <select className="input" value={resolveForm.resolution} onChange={(e) => setResolveForm(prev => ({ ...prev, resolution: e.target.value }))} required>
                    <option value="source_a_wins">Fonte A Vence</option>
                    <option value="source_b_wins">Fonte B Vence</option>
                    <option value="merge">Mesclar Valores</option>
                    <option value="manual">Decisão Manual</option>
                    <option value="deferred">Adiar</option>
                    <option value="escalated">Escalar</option>
                  </select>
                </div>
                <div>
                  <label className="label">Valor Resolvido (opcional)</label>
                  <textarea className="input" rows={3} value={resolveForm.resolved_value} onChange={(e) => setResolveForm(prev => ({ ...prev, resolved_value: e.target.value }))} placeholder="Valor final após resolução" />
                </div>
                <div>
                  <label className="label">Observações</label>
                  <textarea className="input" rows={3} value={resolveForm.notes} onChange={(e) => setResolveForm(prev => ({ ...prev, notes: e.target.value }))} placeholder="Justificativa da resolução" />
                </div>
              </div>
              <div className="p-4 border-t border-secondary-200 flex justify-end gap-2">
                <button type="button" className="btn-secondary" onClick={() => setShowResolveModal(false)}>Cancelar</button>
                <button type="submit" className="btn-primary" disabled={resolveMutation.isPending}>
                  {resolveMutation.isPending ? 'Resolvendo...' : 'Confirmar Resolução'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Create Certification Modal */}
      {showCreateCertModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full">
            <div className="p-6 border-b border-secondary-200">
              <h2 className="text-xl font-bold text-secondary-900">Criar Solicitação de Certificação</h2>
            </div>
            <form onSubmit={(e) => { e.preventDefault(); createCertMutation.mutate({ reconciliation_session_id: id, title: `Certificação para ${(session as any).name}`, description: 'Conflitos da sessão de reconciliação', requested_by: 'system', priority: 2 }) }}>
              <div className="p-6 space-y-4">
                <div>
                  <label className="label">Título</label>
                  <input type="text" className="input" defaultValue={`Certificação: ${session.name}`} required />
                </div>
                <div>
                  <label className="label">Prioridade</label>
                  <select className="input" defaultValue="2">
                    <option value="1">Crítica</option>
                    <option value="2">Alta</option>
                    <option value="3">Média</option>
                    <option value="4">Baixa</option>
                  </select>
                </div>
              </div>
              <div className="p-4 border-t border-secondary-200 flex justify-end gap-2">
                <button type="button" className="btn-secondary" onClick={() => setShowCreateCertModal(false)}>Cancelar</button>
                <button type="submit" className="btn-primary" disabled={createCertMutation.isPending}>
                  {createCertMutation.isPending ? 'Criando...' : 'Criar Solicitação'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}