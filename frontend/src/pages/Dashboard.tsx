import { useQuery } from '@tanstack/react-query'
import { assetApi, relationshipApi, referenceApi, collectionApi } from '../lib/api'
import {
  Server,
  GitBranch,
  Box,
  Cpu,
  RefreshCw,
  ShieldCheck,
  AlertTriangle,
  CheckCircle,
  Clock,
} from 'lucide-react'
import { formatDistanceToNow } from 'date-fns'
import { ptBR } from 'date-fns/locale'
import clsx from 'clsx'

const statCards = [
  { name: 'Total de Hosts', value: 0, icon: Server, color: 'primary', change: '+12%' },
  { name: 'Relacionamentos', value: 0, icon: GitBranch, color: 'green', change: '+5%' },
  { name: 'Aplicações', value: 0, icon: Box, color: 'blue', change: '+3%' },
  { name: 'Clusters', value: 0, icon: Cpu, color: 'purple', change: '0%' },
  { name: 'Conflitos Críticos', value: 0, icon: AlertTriangle, color: 'red', change: '-2' },
  { name: 'Pendentes Certificação', value: 0, icon: ShieldCheck, color: 'orange', change: '+8' },
]

export function Dashboard() {
  const { data: assets } = useQuery({ queryKey: ['assets', 'count'], queryFn: () => assetApi.list({ limit: 1 }) })
  const { data: relationships } = useQuery({ queryKey: ['relationships', 'count'], queryFn: () => relationshipApi.list({ limit: 1 }) })
  const { data: apps } = useQuery({ queryKey: ['applications', 'count'], queryFn: () => referenceApi.applications({ limit: 1 }) })
  const { data: clusters } = useQuery({ queryKey: ['clusters', 'count'], queryFn: () => referenceApi.clusters({ limit: 1 }) })
  const { data: conflicts } = useQuery({ queryKey: ['conflicts'], queryFn: () => collectionApi.reconciliation.conflicts.list('all', { severity: 'critical', resolved: false }) })
  const { data: certRequests } = useQuery({ queryKey: ['cert-requests'], queryFn: () => collectionApi.certification.requests.list({ status: 'pending' }) })
  const { data: recentAssets } = useQuery({ queryKey: ['recent-assets'], queryFn: () => assetApi.list({ limit: 5 }) })
  const { data: recentJobs } = useQuery({ queryKey: ['recent-jobs'], queryFn: () => collectionApi.jobs.list({ limit: 5 }) })

  const stats = [
    { ...statCards[0], value: assets?.length || 0 },
    { ...statCards[1], value: relationships?.length || 0 },
    { ...statCards[2], value: apps?.length || 0 },
    { ...statCards[3], value: clusters?.length || 0 },
    { ...statCards[4], value: conflicts?.length || 0 },
    { ...statCards[5], value: certRequests?.length || 0 },
  ]

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Dashboard</h1>
          <p className="text-secondary-500">Visão geral do ambiente CMDB</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary">Exportar Relatório</button>
          <button className="btn-primary">Nova Coleta</button>
        </div>
      </div>

      {/* Stats Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6 gap-4">
        {stats.map((stat, index) => (
          <div key={index} className="card p-6">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-secondary-500">{stat.name}</p>
                <p className="text-3xl font-bold text-secondary-900 mt-1">{stat.value.toLocaleString()}</p>
              </div>
              <div className={clsx('p-3 rounded-xl', `bg-${stat.color}-100`)}>
                <stat.icon className={clsx('h-6 w-6', `text-${stat.color}-600`)} />
              </div>
            </div>
            <div className="mt-4 flex items-center justify-between">
              <span className={clsx('text-sm font-medium', stat.change.startsWith('-') || stat.change.startsWith('+') ? 'text-green-600' : 'text-red-600')}>
                {stat.change}
              </span>
              <span className="text-xs text-secondary-400">vs mês anterior</span>
            </div>
          </div>
        ))}
      </div>

      {/* Main Content Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Recent Assets */}
        <div className="lg:col-span-2 card">
          <div className="p-4 border-b border-secondary-200 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-secondary-900">Hosts Recentes</h2>
            <a href="/hosts" className="text-sm text-primary-600 hover:text-primary-700">Ver todos</a>
          </div>
          <div className="divide-y divide-secondary-200">
            {recentAssets?.length === 0 ? (
              <div className="p-8 text-center text-secondary-500">Nenhum host encontrado</div>
            ) : (
              recentAssets?.map((asset) => (
                <div key={asset.id} className="p-4 flex items-center justify-between hover:bg-secondary-50">
                  <div className="flex items-center gap-3">
                    <div className="p-2 bg-primary-100 rounded-lg">
                      <Server className="h-5 w-5 text-primary-600" />
                    </div>
                    <div>
                      <p className="font-medium text-secondary-900">{asset.nome}</p>
                      <p className="text-sm text-secondary-500">{asset.tipo?.nome || 'Sem tipo'} • {asset.ambiente?.nome || 'Sem ambiente'}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className={clsx('badge', asset.status?.nome === 'Ativo' ? 'badge-success' : 'badge-secondary')}>
                      {asset.status?.nome || 'N/A'}
                    </span>
                    <span className="text-xs text-secondary-400">{formatDistanceToNow(new Date(asset.created_at), { addSuffix: true, locale: ptBR })}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Side Panel */}
        <div className="space-y-6">
          {/* Collection Status */}
          <div className="card">
            <div className="p-4 border-b border-secondary-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-secondary-900 flex items-center gap-2">
                <RefreshCw className="h-5 w-5 text-primary-600" />
                Coleta de Dados
              </h2>
            </div>
            <div className="p-4 space-y-3">
              {recentJobs?.length === 0 ? (
                <p className="text-secondary-500 text-center py-4">Nenhuma coleta recente</p>
              ) : (
                recentJobs?.map((job) => (
                  <div key={job.id} className="flex items-center justify-between">
                    <div className="flex items-center gap-3">
                      <div className={clsx('p-2 rounded-lg', job.status === 'completed' ? 'bg-green-100' : job.status === 'failed' ? 'bg-red-100' : 'bg-yellow-100')}>
                        <RefreshCw className={clsx('h-5 w-5', job.status === 'completed' ? 'text-green-600' : job.status === 'failed' ? 'text-red-600' : 'text-yellow-600')} />
                      </div>
                      <div>
                        <p className="text-sm font-medium text-secondary-900">{job.source_id}</p>
                        <p className="text-xs text-secondary-500">{job.collection_type}</p>
                      </div>
                    </div>
                    <span className={clsx('badge text-xs', job.status === 'completed' ? 'badge-success' : job.status === 'failed' ? 'badge-danger' : 'badge-warning')}>
                      {job.status}
                    </span>
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Quick Actions */}
          <div className="card">
            <div className="p-4 border-b border-secondary-200">
              <h2 className="text-lg font-semibold text-secondary-900">Ações Rápidas</h2>
            </div>
            <div className="p-4 grid grid-cols-2 gap-3">
              <button className="p-4 rounded-lg border border-secondary-200 hover:border-primary-300 hover:bg-primary-50 transition-colors text-left">
                <Server className="h-6 w-6 text-primary-600 mb-2" />
                <p className="font-medium text-secondary-900">Adicionar Host</p>
                <p className="text-xs text-secondary-500">Cadastrar novo ativo</p>
              </button>
              <button className="p-4 rounded-lg border border-secondary-200 hover:border-primary-300 hover:bg-primary-50 transition-colors text-left">
                <GitBranch className="h-6 w-6 text-primary-600 mb-2" />
                <p className="font-medium text-secondary-900">Criar Relacionamento</p>
                <p className="text-xs text-secondary-500">Vincular ativos</p>
              </button>
              <button className="p-4 rounded-lg border border-secondary-200 hover:border-primary-300 hover:bg-primary-50 transition-colors text-left">
                <ShieldCheck className="h-6 w-6 text-primary-600 mb-2" />
                <p className="font-medium text-secondary-900">Revisar Certificação</p>
                <p className="text-xs text-secondary-500">Pendentes de aprovação</p>
              </button>
              <button className="p-4 rounded-lg border border-secondary-200 hover:border-primary-300 hover:bg-primary-50 transition-colors text-left">
                <RefreshCw className="h-6 w-6 text-primary-600 mb-2" />
                <p className="font-medium text-secondary-900">Nova Reconciliação</p>
                <p className="text-xs text-secondary-500">Comparar fontes</p>
              </button>
            </div>
          </div>

          {/* Alerts */}
          <div className="card">
            <div className="p-4 border-b border-secondary-200 flex items-center justify-between">
              <h2 className="text-lg font-semibold text-secondary-900 flex items-center gap-2">
                <AlertTriangle className="h-5 w-5 text-yellow-600" />
                Alertas
              </h2>
            </div>
            <div className="p-4 space-y-3">
              <div className="p-3 rounded-lg bg-yellow-50 border border-yellow-200">
                <div className="flex items-start gap-2">
                  <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-yellow-800">5 conflitos críticos não resolvidos</p>
                    <p className="text-sm text-yellow-700">Requer atenção imediata da equipe</p>
                  </div>
                </div>
              </div>
              <div className="p-3 rounded-lg bg-blue-50 border border-blue-200">
                <div className="flex items-start gap-2">
                  <Clock className="h-5 w-5 text-blue-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-blue-800">3 certificações próximas do SLA</p>
                    <p className="text-sm text-blue-700">Vencem nas próximas 24 horas</p>
                  </div>
                </div>
              </div>
              <div className="p-3 rounded-lg bg-green-50 border border-green-200">
                <div className="flex items-start gap-2">
                  <CheckCircle className="h-5 w-5 text-green-600 mt-0.5" />
                  <div>
                    <p className="font-medium text-green-800">Coleta do vCenter concluída</p>
                    <p className="text-sm text-green-700">1.245 ativos atualizados há 15 min</p>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}