import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { collectionApi } from '../../lib/api'
import { useAuthStore } from '../../store/auth'
import { format } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { AlertTriangle, Clock, CheckCircle, XCircle, Flag, User, FileText, ChevronLeft, Loader2, MessageSquare } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useState } from 'react'
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

export function CertificationDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()
  const { user } = useAuthStore()
  const [showCommentModal, setShowCommentModal] = useState(false)
  const [commentText, setCommentText] = useState('')
  const [activeTab, setActiveTab] = useState<'details' | 'conflicts' | 'comments'>('details')

  const { data: requestData, isLoading, error } = useQuery({
    queryKey: ['certification-request', id],
    queryFn: () => collectionApi.certification.requests.get(id!),
    enabled: !!id,
  })

  const request = requestData?.data || requestData

  const actionMutation = useMutation({
    mutationFn: ({ role, decision, notes }: { role: string; decision: string; notes?: string }) =>
      collectionApi.certification.requests.action(id!, { role, decision, notes, decided_by: user?.id || '' }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['certification-request', id] })
    },
  })

  const commentMutation = useMutation({
    mutationFn: (content: string) =>
      collectionApi.certification.requests.addComment(id!, { author_id: user?.id || '', author_role: user?.roles.includes('reviewer') ? 'reviewer' : 'analyst', content }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['certification-request', id] })
      setCommentText('')
      setShowCommentModal(false)
    },
  })

  const isAnalyst = user?.roles.includes('analyst') || user?.roles.includes('reconciliator')
  const isReviewer = user?.roles.includes('reviewer') || user?.roles.includes('revisor')

  if (isLoading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="h-12 w-12 animate-spin text-primary-600" /></div>
  }

  if (error || !request) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-secondary-900">Solicitação não encontrada</h2>
        <p className="text-secondary-500 mt-2">A solicitação de certificação não existe.</p>
      </div>
    )
  }

  const status = statusConfig[request.status as keyof typeof statusConfig] || statusConfig.pending
  const priority = priorityConfig[request.priority as keyof typeof priorityConfig] || priorityConfig[3]
  const StatusIcon = status.icon
  const PriorityIcon = priority.icon

  const hoursLeft = request.due_at ? (new Date(request.due_at).getTime() - Date.now()) / (1000 * 60 * 60) : null
  const isOverdue = hoursLeft !== null && hoursLeft < 0
  const isDueSoon = hoursLeft !== null && hoursLeft > 0 && hoursLeft <= 24

  const canActAsAnalyst = isAnalyst && ['pending', 'in_review_analyst'].includes(request.status)
  const canActAsReviewer = isReviewer && request.status === 'in_review_reviewer'

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <nav className="flex items-center gap-2 text-sm text-secondary-500 mb-2">
            <a href="/certification" className="hover:text-primary-600 flex items-center gap-1">
              <ChevronLeft className="h-4 w-4" />
              Certificação
            </a>
            <span className="text-secondary-900 font-medium">{request.title}</span>
          </nav>
          <div className="flex items-center gap-3">
            <span className={clsx('badge flex items-center gap-1', `badge-${priority.color}`)}>
              <PriorityIcon className="h-3 w-3" />
              {priority.label}
            </span>
            <span className={clsx('badge flex items-center gap-1', `badge-${status.color}`)}>
              <StatusIcon className="h-3 w-3" />
              {status.label}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => navigate('/certification')}>
            Voltar
          </button>
        </div>
      </div>

      {/* SLA Banner */}
      {request.due_at && (
        <div className={clsx('card p-4 border-l-4', isOverdue ? 'border-red-500 bg-red-50' : isDueSoon ? 'border-yellow-500 bg-yellow-50' : 'border-green-500 bg-green-50')}>
          <div className="flex items-center gap-3">
            <Clock className={clsx('h-6 w-6', isOverdue ? 'text-red-600' : isDueSoon ? 'text-yellow-600' : 'text-green-600')} />
            <div>
              <p className="font-medium text-secondary-900">
                {isOverdue ? 'SLA VENCIDO' : isDueSoon ? `Vence em ${Math.round(hoursLeft!)} horas` : 'Dentro do SLA'}
              </p>
              <p className="text-sm text-secondary-600">
                Prazo: {format(new Date(request.due_at), 'dd/MM/yyyy HH:mm', { locale: ptBR })}
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="card">
        <div className="border-b border-secondary-200">
          <nav className="flex gap-1 px-4" aria-label="Detail tabs">
            {[
              { id: 'details', label: 'Detalhes', icon: FileText },
              { id: 'conflicts', label: 'Conflitos', icon: AlertTriangle },
              { id: 'comments', label: 'Comentários', icon: MessageSquare },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={clsx(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
                  activeTab === tab.id
                    ? 'border-primary-500 text-primary-600'
                    : 'border-transparent text-secondary-500 hover:text-secondary-700 hover:border-secondary-300'
                )}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {/* Details Tab */}
          {activeTab === 'details' && (
            <div className="space-y-6 max-w-4xl">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="p-4 bg-secondary-50 rounded-lg">
                  <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Solicitante</label>
                  <p className="font-medium text-secondary-900 mt-1 flex items-center gap-2">
                    <User className="h-4 w-4 text-primary-600" />
                    {request.requested_by}
                  </p>
                </div>
                <div className="p-4 bg-secondary-50 rounded-lg">
                  <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Criado em</label>
                  <p className="font-medium text-secondary-900 mt-1">{format(new Date(request.created_at), 'dd/MM/yyyy HH:mm')}</p>
                </div>
                <div className="p-4 bg-secondary-50 rounded-lg">
                  <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Analista</label>
                  <p className="font-medium text-secondary-900 mt-1 flex items-center gap-2">
                    <User className="h-4 w-4 text-blue-600" />
                    {request.analyst_id || 'Não atribuído'}
                  </p>
                </div>
                <div className="p-4 bg-secondary-50 rounded-lg">
                  <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Revisor</label>
                  <p className="font-medium text-secondary-900 mt-1 flex items-center gap-2">
                    <FileText className="h-4 w-4 text-purple-600" />
                    {request.reviewer_id || 'Não atribuído'}
                  </p>
                </div>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="label">Título</label>
                  <p className="text-lg font-semibold text-secondary-900">{request.title}</p>
                </div>
                <div>
                  <label className="label">Descrição</label>
                  <div className="p-4 bg-secondary-50 rounded-lg whitespace-pre-wrap text-secondary-700">{request.description}</div>
                </div>

                {/* Decisions */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="card p-4 border-l-4 border-blue-500">
                    <h4 className="font-medium text-secondary-900 mb-2 flex items-center gap-2">
                      <User className="h-4 w-4 text-blue-600" />
                      Decisão do Analista
                    </h4>
                    {request.analyst_decision ? (
                      <div className="space-y-2">
                        <span className={clsx('badge', request.analyst_decision === 'approve' ? 'badge-success' : request.analyst_decision === 'reject' ? 'badge-danger' : 'badge-warning')}>
                          {request.analyst_decision}
                        </span>
                        {request.analyst_notes && <p className="text-sm text-secondary-600">{request.analyst_notes}</p>}
                        {request.analyst_decided_at && <p className="text-xs text-secondary-400">{format(new Date(request.analyst_decided_at), 'dd/MM/yyyy HH:mm')}</p>}
                      </div>
                    ) : (
                      <p className="text-secondary-500">Aguardando decisão</p>
                    )}
                  </div>

                  <div className="card p-4 border-l-4 border-purple-500">
                    <h4 className="font-medium text-secondary-900 mb-2 flex items-center gap-2">
                      <FileText className="h-4 w-4 text-purple-600" />
                      Decisão do Revisor
                    </h4>
                    {request.reviewer_decision ? (
                      <div className="space-y-2">
                        <span className={clsx('badge', request.reviewer_decision === 'approve' ? 'badge-success' : request.reviewer_decision === 'reject' ? 'badge-danger' : 'badge-warning')}>
                          {request.reviewer_decision}
                        </span>
                        {request.reviewer_notes && <p className="text-sm text-secondary-600">{request.reviewer_notes}</p>}
                        {request.reviewer_decided_at && <p className="text-xs text-secondary-400">{format(new Date(request.reviewer_decided_at), 'dd/MM/yyyy HH:mm')}</p>}
                      </div>
                    ) : (
                      <p className="text-secondary-500">Aguardando decisão</p>
                    )}
                  </div>
                </div>

                {request.final_decision && (
                  <div className="card p-4 border-l-4 border-green-500 bg-green-50">
                    <h4 className="font-medium text-green-800 mb-2 flex items-center gap-2">
                      <CheckCircle className="h-4 w-4" />
                      Decisão Final
                    </h4>
                    <p className="text-green-700 font-medium">{request.final_decision.toUpperCase()}</p>
                    {request.final_notes && <p className="text-sm text-green-600 mt-1">{request.final_notes}</p>}
                    <p className="text-xs text-green-500 mt-1">Decidido por {request.decided_by} em {request.decided_at ? format(new Date(request.decided_at), 'dd/MM/yyyy HH:mm') : ''}</p>
                  </div>
                )}

                {/* Actions */}
                {(canActAsAnalyst || canActAsReviewer) && (
                  <div className="card p-4 border-l-4 border-primary-500 bg-primary-50">
                    <h4 className="font-medium text-secondary-900 mb-4">Sua Ação</h4>
                    <div className="space-y-3">
                      <textarea
                        placeholder="Adicionar observações (opcional)..."
                        className="input min-h-[80px]"
                        value={commentText}
                        onChange={(e) => setCommentText(e.target.value)}
                      />
                      <div className="flex gap-2">
                        {canActAsAnalyst && (
                          <>
                            <button
                              className="btn-success"
                              onClick={() => actionMutation.mutate({ role: 'analyst', decision: 'approve', notes: commentText })}
                              disabled={actionMutation.isPending}
                            >
                              Aprovar
                            </button>
                            <button
                              className="btn-danger"
                              onClick={() => actionMutation.mutate({ role: 'analyst', decision: 'reject', notes: commentText })}
                              disabled={actionMutation.isPending}
                            >
                              Rejeitar
                            </button>
                            <button
                              className="btn-warning"
                              onClick={() => actionMutation.mutate({ role: 'analyst', decision: 'request_changes', notes: commentText })}
                              disabled={actionMutation.isPending}
                            >
                              Solicitar Alterações
                            </button>
                          </>
                        )}
                        {canActAsReviewer && (
                          <>
                            <button
                              className="btn-success"
                              onClick={() => actionMutation.mutate({ role: 'reviewer', decision: 'approve', notes: commentText })}
                              disabled={actionMutation.isPending}
                            >
                              Aprovar
                            </button>
                            <button
                              className="btn-danger"
                              onClick={() => actionMutation.mutate({ role: 'reviewer', decision: 'reject', notes: commentText })}
                              disabled={actionMutation.isPending}
                            >
                              Rejeitar
                            </button>
                            <button
                              className="btn-warning"
                              onClick={() => actionMutation.mutate({ role: 'reviewer', decision: 'request_changes', notes: commentText })}
                              disabled={actionMutation.isPending}
                            >
                              Solicitar Alterações
                            </button>
                          </>
                        )}
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Conflicts Tab */}
          {activeTab === 'conflicts' && (
            <div className="space-y-4">
              <p className="text-secondary-500">Lista de conflitos associados a esta solicitação de certificação.</p>
              <div className="card overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className="bg-secondary-50">
                      <tr>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Severidade</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Tipo</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Descrição</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Origem</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Destino</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Atributo</th>
                        <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Resolução</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-secondary-200">
                      <tr><td colSpan={7} className="px-4 py-8 text-center text-secondary-500">Carregar conflitos da API...</td></tr>
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}

          {/* Comments Tab */}
          {activeTab === 'comments' && (
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <h3 className="text-lg font-semibold text-secondary-900">Comentários</h3>
                <button className="btn-primary" onClick={() => setShowCommentModal(true)}>
                  <MessageSquare className="h-4 w-4" />
                  Adicionar Comentário
                </button>
              </div>
              <div className="space-y-4">
                <p className="text-secondary-500 text-center py-8">Carregar comentários da API...</p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Comment Modal */}
      {showCommentModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full">
            <div className="p-6 border-b border-secondary-200">
              <h2 className="text-xl font-bold text-secondary-900">Adicionar Comentário</h2>
            </div>
            <form onSubmit={(e) => { e.preventDefault(); commentMutation.mutate(commentText) }}>
              <div className="p-6">
                <textarea
                  className="input min-h-[120px]"
                  placeholder="Digite seu comentário..."
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  required
                />
              </div>
              <div className="p-4 border-t border-secondary-200 flex justify-end gap-2">
                <button type="button" className="btn-secondary" onClick={() => setShowCommentModal(false)}>Cancelar</button>
                <button type="submit" className="btn-primary" disabled={commentMutation.isPending || !commentText.trim()}>
                  {commentMutation.isPending ? 'Enviando...' : 'Enviar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}