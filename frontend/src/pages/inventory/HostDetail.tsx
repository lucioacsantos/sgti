import { useParams } from 'react-router-dom'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { assetApi, ipApi } from '../../lib/api'
import { format } from 'date-fns'
import {
  Server,
  Building2,
  HardDrive,
  Cpu,
  MemoryStick,
  Globe,
  Shield,
  Edit,
  Trash2,
  Plus,
  ChevronRight,
  Loader2,
  AlertTriangle,
  CheckCircle,
  Info,
} from 'lucide-react'
import clsx from 'clsx'

export function HostDetail() {
  const { id } = useParams<{ id: string }>()
  const queryClient = useQueryClient()

  const { data: asset, isLoading, error } = useQuery({
    queryKey: ['host', id],
    queryFn: () => assetApi.get(id!),
    enabled: !!id,
  })

  const { data: ips } = useQuery({
    queryKey: ['host-ips', id],
    queryFn: () => ipApi.list({ ativo_id: Number(id) }),
    enabled: !!id,
  })

  const deleteMutation = useMutation({
    mutationFn: () => assetApi.delete(id!),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['hosts'] })
    },
  })

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-12 w-12 animate-spin text-primary-600" />
      </div>
    )
  }

  if (error || !asset) {
    return (
      <div className="card p-8 text-center">
        <AlertTriangle className="h-12 w-12 text-red-500 mx-auto mb-4" />
        <h2 className="text-xl font-bold text-secondary-900">Host não encontrado</h2>
        <p className="text-secondary-500 mt-2">O ativo solicitado não existe ou foi removido.</p>
      </div>
    )
  }

  const getStatusBadge = (status?: string) => {
    switch (status) {
      case 'Ativo': return 'badge-success'
      case 'Inativo': return 'badge-secondary'
      case 'Manutenção': return 'badge-warning'
      case 'Descomissionado': return 'badge-danger'
      default: return 'badge-secondary'
    }
  }

  const getCriticityBadge = (level?: string) => {
    switch (level) {
      case 'Crítica': return 'badge-danger'
      case 'Alta': return 'badge-warning'
      case 'Média': return 'badge-primary'
      case 'Baixa': return 'badge-success'
      default: return 'badge-secondary'
    }
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <nav className="flex items-center gap-2 text-sm text-secondary-500 mb-2">
            <a href="/hosts" className="hover:text-primary-600">Hosts</a>
            <ChevronRight className="h-4 w-4" />
            <span className="text-secondary-900 font-medium">{asset.nome}</span>
          </nav>
          <div className="flex items-center gap-2">
            {asset.is_certified && (
              <span className="flex items-center gap-1 px-2 py-1 rounded-lg bg-green-100 text-green-700 text-xs font-medium">
                <CheckCircle className="h-3 w-3" />
                Certificado
              </span>
            )}
            <span className={clsx('badge', getStatusBadge(asset.status?.nome))}>
              {asset.status?.nome || 'Desconhecido'}
            </span>
          </div>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary">
            <Edit className="h-4 w-4" />
            Editar
          </button>
          <button
            className="btn-danger"
            onClick={() => { if (confirm('Excluir este host?')) deleteMutation.mutate() }}
          >
            <Trash2 className="h-4 w-4" />
            Excluir
          </button>
        </div>
      </div>

      {/* Main Content */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column - Main Info */}
        <div className="lg:col-span-2 space-y-6">
          {/* Overview Card */}
          <div className="card p-6">
            <div className="flex items-start justify-between">
              <div>
                <h2 className="text-xl font-bold text-secondary-900">{asset.nome}</h2>
                {asset.descricao && <p className="text-secondary-500 mt-1">{asset.descricao}</p>}
              </div>
              <div className="flex items-center gap-2 text-sm text-secondary-500">
                <Info className="h-4 w-4" />
                <span>Criado em {format(new Date(asset.created_at), 'dd/MM/yyyy HH:mm')}</span>
              </div>
            </div>

            <div className="mt-6 grid grid-cols-2 sm:grid-cols-4 gap-4">
              <div className="p-4 bg-secondary-50 rounded-lg">
                <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Tipo</label>
                <p className="font-medium text-secondary-900 mt-1 flex items-center gap-2">
                  <Server className="h-4 w-4 text-primary-600" />
                  {asset.tipo?.nome || 'Não definido'}
                </p>
              </div>
              <div className="p-4 bg-secondary-50 rounded-lg">
                <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Ambiente</label>
                <p className="font-medium text-secondary-900 mt-1 flex items-center gap-2">
                  <Building2 className="h-4 w-4 text-primary-600" />
                  {asset.ambiente?.nome || 'Não definido'}
                </p>
              </div>
              <div className="p-4 bg-secondary-50 rounded-lg">
                <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Criticidade</label>
                <p className="font-medium text-secondary-900 mt-1 flex items-center gap-2">
                  <Shield className="h-4 w-4 text-primary-600" />
                  <span className={clsx('badge', getCriticityBadge(asset.criticidade?.nivel))}>
                    {asset.criticidade?.nivel || 'Não definido'}
                  </span>
                </p>
              </div>
              <div className="p-4 bg-secondary-50 rounded-lg">
                <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Sistema Operacional</label>
                <p className="font-medium text-secondary-900 mt-1 flex items-center gap-2">
                  <HardDrive className="h-4 w-4 text-primary-600" />
                  {asset.sor?.abreviacao || 'Não definido'}
                </p>
              </div>
            </div>

            {/* Hardware Specs */}
            {asset.cpu_cores || asset.cpu_model || asset.memory_gb || asset.total_storage_gb && (
              <div className="card p-6">
                <h3 className="text-lg font-semibold text-secondary-900 mb-4 flex items-center gap-2">
                  <Cpu className="h-5 w-5 text-primary-600" />
                  Especificações de Hardware
                </h3>
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
                  {asset.cpu_cores && (
                    <div className="p-4 bg-secondary-50 rounded-lg">
                      <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">CPU Cores</label>
                      <p className="font-bold text-2xl text-secondary-900 mt-1">{asset.cpu_cores}</p>
                      {asset.cpu_threads && asset.cpu_threads !== asset.cpu_cores && (
                        <p className="text-xs text-secondary-500">({asset.cpu_threads} threads)</p>
                      )}
                    </div>
                  )}
                  {asset.cpu_model && (
                    <div className="p-4 bg-secondary-50 rounded-lg sm:col-span-2">
                      <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Modelo CPU</label>
                      <p className="font-medium text-secondary-900 mt-1">{asset.cpu_model}</p>
                    </div>
                  )}
                  {asset.cpu_mhz && (
                    <div className="p-4 bg-secondary-50 rounded-lg">
                      <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Frequência</label>
                      <p className="font-medium text-secondary-900 mt-1">{asset.cpu_mhz} MHz</p>
                    </div>
                  )}
                  {asset.memory_gb && (
                    <div className="p-4 bg-secondary-50 rounded-lg">
                      <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Memória</label>
                      <p className="font-bold text-2xl text-secondary-900 mt-1 flex items-center gap-1">
                        <MemoryStick className="h-5 w-5 text-primary-600" />
                        {asset.memory_gb} GB
                      </p>
                    </div>
                  )}
                  {asset.total_storage_gb && (
                    <div className="p-4 bg-secondary-50 rounded-lg">
                      <label className="text-xs font-medium text-secondary-500 uppercase tracking-wider">Armazenamento</label>
                      <p className="font-bold text-2xl text-secondary-900 mt-1 flex items-center gap-1">
                        <HardDrive className="h-5 w-5 text-primary-600" />
                        {asset.total_storage_gb} GB
                      </p>
                    </div>
                  )}
                </div>
              </div>
            )}

            {/* Network */}
            {Array.isArray(ips) && ips.length > 0 && (
              <div className="card p-6">
                <div className="flex items-center justify-between mb-4">
                  <h3 className="text-lg font-semibold text-secondary-900 flex items-center gap-2">
                    <Globe className="h-5 w-5 text-primary-600" />
                    Endereços IP ({ips.length})
                  </h3>
                  <button className="btn-secondary text-sm">
                    <Plus className="h-4 w-4" />
                    Adicionar IP
                  </button>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider border-b border-secondary-200">
                        <th className="pb-2">IP</th>
                        <th className="pb-2">Tipo</th>
                        <th className="pb-2">Interface</th>
                        <th className="pb-2">Descrição</th>
                        <th className="pb-2">Primário</th>
                        <th className="pb-2">Ativo</th>
                        <th className="pb-2 text-right">Ações</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-secondary-200">
                      {(Array.isArray(ips) ? ips : []).map((ip: any) => (
                        <tr key={ip.id} className="hover:bg-secondary-50">
                          <td className="py-3 font-mono text-sm text-secondary-900">{ip.ip}</td>
                          <td className="py-3 text-sm text-secondary-700">{ip.tipo || 'IPv4'}</td>
                          <td className="py-3 text-sm text-secondary-700">{ip.interface || '—'}</td>
                          <td className="py-3 text-sm text-secondary-700">{ip.descricao || '—'}</td>
                          <td className="py-3">
                            {ip.primario ? (
                              <span className="badge badge-primary">Sim</span>
                            ) : (
                              <span className="badge badge-secondary">Não</span>
                            )}
                          </td>
                          <td className="py-3">
                            {ip.ativo ? (
                              <span className="badge badge-success">Sim</span>
                            ) : (
                              <span className="badge badge-secondary">Não</span>
                            )}
                          </td>
                          <td className="py-3 text-right">
                            <button className="p-2 rounded-lg hover:bg-secondary-100 text-secondary-500">
                              <Edit className="h-4 w-4" />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>

          {/* Right Column - Sidebar */}
          <div className="space-y-6">
            {/* Location */}
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-secondary-900 mb-4">Localização</h3>
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-secondary-500">Área</dt>
                  <dd className="font-medium text-secondary-900">{asset.areas?.nome || '—'} ({asset.areas?.sigla})</dd>
                </div>
              </dl>
            </div>

            {/* Audit Trail */}
            <div className="card p-6">
              <h3 className="text-lg font-semibold text-secondary-900 mb-4">Auditoria</h3>
              <dl className="space-y-3 text-sm">
                <div className="flex justify-between">
                  <dt className="text-secondary-500">Criado em</dt>
                  <dd className="font-medium text-secondary-900">{format(new Date(asset.created_at), 'dd/MM/yyyy HH:mm')}</dd>
                </div>
                {asset.updated_at && (
                  <div className="flex justify-between">
                    <dt className="text-secondary-500">Atualizado em</dt>
                    <dd className="font-medium text-secondary-900">{format(new Date(asset.updated_at), 'dd/MM/yyyy HH:mm')}</dd>
                  </div>
                )}
              </dl>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}