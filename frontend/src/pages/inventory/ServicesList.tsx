import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { referenceApi, servicesAdminApi } from '../../lib/api'
import { Search, Plus, Download } from 'lucide-react'

export function ServicesList() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [page] = useState(1)
  const [pageSize] = useState(20)
  const [typeFilter, setTypeFilter] = useState('')

  const { data: services, isLoading } = useQuery({
    queryKey: ['services', { page, pageSize, search, type: typeFilter }],
    queryFn: () => referenceApi.services({ skip: (page - 1) * pageSize, limit: pageSize }),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => servicesAdminApi.delete(id.toString()),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['services'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Serviços</h1>
          <p className="text-secondary-500">Gerenciar serviços de infraestrutura</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary"><Download className="h-4 w-4" /> Exportar</button>
          <button className="btn-primary"><Plus className="h-4 w-4" /> Novo Serviço</button>
        </div>
      </div>

      <div className="card p-4">
        <div className="flex gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-secondary-400" />
            <input type="search" placeholder="Buscar por nome..." className="input pl-10" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <select className="input w-auto" value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)}>
            <option value="">Todos os tipos</option>
            <option value="web">Web</option>
            <option value="database">Database</option>
            <option value="cache">Cache</option>
            <option value="message_queue">Message Queue</option>
            <option value="api">API</option>
            <option value="other">Outro</option>
          </select>
          <span className="text-sm text-secondary-500">{(Array.isArray(services) ? services.length : 0)} serviços</span>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full" role="grid">
            <thead className="bg-secondary-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Nome</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Tipo</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Host ID</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Ativo Associado</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-secondary-500 uppercase tracking-wider">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-secondary-200">
              {isLoading ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center"><div className="flex items-center justify-center gap-2"><div className="animate-spin rounded-full h-6 w-6 border-2 border-primary-500 border-t-transparent"></div><span className="text-secondary-500">Carregando...</span></div></td></tr>
              ) : Array.isArray(services) && services.length === 0 ? (
                <tr><td colSpan={5} className="px-4 py-8 text-center text-secondary-500">Nenhum serviço encontrado</td></tr>
              ) : (
                (Array.isArray(services) ? services : []).map((svc) => (
                  <tr key={svc.id} className="hover:bg-secondary-50">
                    <td className="px-4 py-3 font-medium text-secondary-900">{svc.nome}</td>
                    <td className="px-4 py-3"><span className="badge badge-primary">{svc.tipo || '—'}</span></td>
                    <td className="px-4 py-3 text-sm text-secondary-700">{svc.host_id || '—'}</td>
                    <td className="px-4 py-3 text-sm text-secondary-700">{svc.ativo?.nome || '—'}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button className="p-2 rounded-lg hover:bg-secondary-100 text-secondary-500" title="Ver"><svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" /><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" /></svg></button>
                        <button className="p-2 rounded-lg hover:bg-secondary-100 text-secondary-500" title="Editar"><svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" /></svg></button>
                        <button className="p-2 rounded-lg hover:bg-red-50 text-red-500" title="Excluir" onClick={() => deleteMutation.mutate(svc.id)}><svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" /></svg></button>
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