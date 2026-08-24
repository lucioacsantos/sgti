import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { relationshipApi } from '../../lib/api'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import { GitBranch, Server, ChevronLeft, Edit, Trash2, Loader2, AlertTriangle, ExternalLink } from 'lucide-react'
import { useNavigate } from 'react-router-dom'

export function RelationshipDetail() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const queryClient = useQueryClient()

  const { data: relationship, isLoading, error } = useQuery({
    queryKey: ['relationship', id],
    queryFn: () => relationshipApi.get(Number(id!)),
    enabled: !!id,
  })

  const deleteMutation = useMutation({
    mutationFn: () => relationshipApi.delete(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['relationships'] })
      navigate('/relationships')
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-12 w-12 animate-spin text-primary-600" />
      </div>
    )
  }

  if (error || !relationship) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-secondary-900">Relacionamento não encontrado</h2>
        <p className="text-secondary-500 mt-2">O relacionamento solicitado não existe ou foi removido.</p>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <nav className="flex items-center gap-2 text-sm text-secondary-500 mb-2">
            <a href="/relationships" className="hover:text-primary-600">Relacionamentos</a>
            <ChevronLeft className="h-4 w-4" />
            <span className="text-secondary-900 font-medium">{relationship.tipo?.nome || `ID: ${relationship.id}`}</span>
          </nav>
          <div className="flex items-center gap-2">
            <span className="badge badge-primary">{relationship.tipo?.nome || 'N/A'}</span>
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary">
            <Edit className="h-4 w-4" />
            Editar
          </button>
          <button
            className="btn-danger"
            onClick={() => { if (confirm('Excluir este relacionamento?')) deleteMutation.mutate() }}
          >
            <Trash2 className="h-4 w-4" />
            Excluir
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Relationship Details */}
        <div className="lg:col-span-2 space-y-6">
          {/* Overview */}
          <div className="card p-6">
            <h2 className="text-xl font-bold text-secondary-900 mb-4">Visão Geral</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="p-4 bg-secondary-50 rounded-lg">
                <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Tipo de Relacionamento</label>
                <p className="font-medium text-secondary-900 mt-1 flex items-center gap-2">
                  <GitBranch className="h-4 w-4 text-primary-600" />
                  {relationship.tipo?.nome || 'Não definido'}
                </p>
              </div>
              <div className="p-4 bg-secondary-50 rounded-lg">
                <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Descrição</label>
                <p className="font-medium text-secondary-900 mt-1">{relationship.descricao || 'Sem descrição'}</p>
              </div>
              <div className="p-4 bg-secondary-50 rounded-lg">
                <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Criado em</label>
                <p className="font-medium text-secondary-900 mt-1">
                  {new Date(relationship.created_at).toLocaleString('pt-BR')}
                </p>
              </div>
              <div className="p-4 bg-secondary-50 rounded-lg">
                <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">ID</label>
                <p className="font-medium text-secondary-900 mt-1 font-mono text-sm">{relationship.id}</p>
              </div>
            </div>
          </div>

          {/* Source Asset */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold text-secondary-900 mb-4 flex items-center gap-2">
              <Server className="h-5 w-5 text-blue-600" />
              Ativo de Origem
            </h3>
            <div className="flex items-center gap-4 p-4 bg-secondary-50 rounded-lg">
              <div className="h-12 w-12 rounded-lg bg-blue-100 flex items-center justify-center">
                <Server className="h-6 w-6 text-blue-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-secondary-900 truncate">{relationship.origem?.nome || `ID: ${relationship.origem_id}`}</p>
                <p className="text-sm text-secondary-500">{relationship.origem?.tipo?.nome || 'Host'}</p>
              </div>
              {relationship.origem && (
                <a href={`/hosts/${relationship.origem.id}`} className="btn-secondary text-sm">
                  <ExternalLink className="h-4 w-4" />
                  Ver Detalhes
                </a>
              )}
            </div>
          </div>

          {/* Destination Asset */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold text-secondary-900 mb-4 flex items-center gap-2">
              <Server className="h-5 w-5 text-green-600" />
              Ativo de Destino
            </h3>
            <div className="flex items-center gap-4 p-4 bg-secondary-50 rounded-lg">
              <div className="h-12 w-12 rounded-lg bg-green-100 flex items-center justify-center">
                <Server className="h-6 w-6 text-green-600" />
              </div>
              <div className="flex-1 min-w-0">
                <p className="font-semibold text-secondary-900 truncate">{relationship.destino?.nome || `ID: ${relationship.destino_id}`}</p>
                <p className="text-sm text-secondary-500">{relationship.destino?.tipo?.nome || 'Host'}</p>
              </div>
              {relationship.destino && (
                <a href={`/hosts/${relationship.destino.id}`} className="btn-secondary text-sm">
                  <ExternalLink className="h-4 w-4" />
                  Ver Detalhes
                </a>
              )}
            </div>
          </div>

          {/* Visual Diagram */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold text-secondary-900 mb-4">Diagrama do Relacionamento</h3>
            <div className="flex items-center justify-center gap-8 p-8 bg-secondary-50 rounded-lg">
              <div className="text-center">
                <div className="h-16 w-16 rounded-lg bg-blue-100 flex items-center justify-center mx-auto mb-2">
                  <Server className="h-8 w-8 text-blue-600" />
                </div>
                <p className="font-medium text-secondary-900 text-sm">{relationship.origem?.nome || 'Origem'}</p>
                <p className="text-xs text-secondary-500">{relationship.origem?.tipo?.nome || 'Host'}</p>
              </div>
              <div className="flex flex-col items-center text-primary-600">
                <GitBranch className="h-8 w-8" />
                <p className="text-xs text-secondary-500 mt-1">{relationship.tipo?.nome}</p>
              </div>
              <div className="text-center">
                <div className="h-16 w-16 rounded-lg bg-green-100 flex items-center justify-center mx-auto mb-2">
                  <Server className="h-8 w-8 text-green-600" />
                </div>
                <p className="font-medium text-secondary-900 text-sm">{relationship.destino?.nome || 'Destino'}</p>
                <p className="text-xs text-secondary-500">{relationship.destino?.tipo?.nome || 'Host'}</p>
              </div>
            </div>
          </div>
        </div>

        {/* Right Column - Sidebar */}
        <div className="space-y-6">
          {/* Type Info */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold text-secondary-900 mb-4">Tipo de Relacionamento</h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-secondary-500">Nome</dt>
                <dd className="font-medium text-secondary-900">{relationship.tipo?.nome || '—'}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-secondary-500">Descrição</dt>
                <dd className="font-medium text-secondary-900">{relationship.tipo?.descricao || 'Sem descrição'}</dd>
              </div>
            </dl>
          </div>

          {/* Audit Trail */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold text-secondary-900 mb-4">Auditoria</h3>
            <dl className="space-y-3 text-sm">
              <div className="flex justify-between">
                <dt className="text-secondary-500">Criado em</dt>
                <dd className="font-medium text-secondary-900">{new Date(relationship.created_at).toLocaleString('pt-BR')}</dd>
              </div>
              <div className="flex justify-between">
                <dt className="text-secondary-500">Tempo decorrido</dt>
                <dd className="font-medium text-secondary-900">{formatDistanceToNow(new Date(relationship.created_at), { addSuffix: true, locale: ptBR })}</dd>
              </div>
            </dl>
          </div>

          {/* Quick Actions */}
          <div className="card p-6">
            <h3 className="text-lg font-semibold text-secondary-900 mb-4">Ações Rápidas</h3>
            <div className="space-y-2">
              {relationship.origem && (
                <a href={`/hosts/${relationship.origem.id}`} className="block p-3 rounded-lg border border-secondary-200 hover:border-primary-300 hover:bg-primary-50 transition-colors">
                  <p className="font-medium text-secondary-900">Ver Ativo de Origem</p>
                  <p className="text-sm text-secondary-500">{relationship.origem.nome}</p>
                </a>
              )}
              {relationship.destino && (
                <a href={`/hosts/${relationship.destino.id}`} className="block p-3 rounded-lg border border-secondary-200 hover:border-primary-300 hover:bg-primary-50 transition-colors">
                  <p className="font-medium text-secondary-900">Ver Ativo de Destino</p>
                  <p className="text-sm text-secondary-500">{relationship.destino.nome}</p>
                </a>
              )}
              <a href={`/relationships?origem_id=${relationship.origem_id}`} className="block p-3 rounded-lg border border-secondary-200 hover:border-primary-300 hover:bg-primary-50 transition-colors">
                <p className="font-medium text-secondary-900">Outros relacionamentos desta origem</p>
              </a>
              <a href={`/relationships?destino_id=${relationship.destino_id}`} className="block p-3 rounded-lg border border-secondary-200 hover:border-primary-300 hover:bg-primary-50 transition-colors">
                <p className="font-medium text-secondary-900">Outros relacionamentos deste destino</p>
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}