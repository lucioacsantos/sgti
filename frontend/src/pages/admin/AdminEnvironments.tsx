import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '../../lib/api'
import { Search, Plus, Edit, Trash2, RefreshCw } from 'lucide-react'
import clsx from 'clsx'

export function AdminEnvironments() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingItem, setEditingItem] = useState<any>(null)

  const { data, isLoading, refetch } = useQuery({
    queryKey: ['admin-environments'],
    queryFn: adminApi.environments.list,
  })

  const createMutation = useMutation({
    mutationFn: (data: any) => adminApi.environments.create(data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['admin-environments'] }); setShowCreateModal(false) },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: number; data: any }) => adminApi.environments.update(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['admin-environments'] }); setEditingItem(null) },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => adminApi.environments.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-environments'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Ambientes</h1>
          <p className="text-secondary-500">Gerenciar ambientes de infraestrutura</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={clsx('h-4 w-4', isLoading && 'animate-spin')} />
            Atualizar
          </button>
          <button className="btn-primary" onClick={() => { setEditingItem(null); setShowCreateModal(true) }}>
            <Plus className="h-4 w-4" />
            Novo Ambiente
          </button>
        </div>
      </div>

      <div className="card p-4">
        <div className="flex gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-secondary-400" />
            <input type="search" placeholder="Buscar por nome..." className="input pl-10" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full" role="grid">
            <thead className="bg-secondary-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Nome</th>
                <th className="px-4 py-3 text-right text-xs font-semibold text-secondary-500 uppercase tracking-wider">Ações</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-secondary-200">
              {isLoading ? (
                <tr><td colSpan={2} className="px-4 py-8 text-center"><div className="flex items-center justify-center gap-2"><div className="animate-spin rounded-full h-6 w-6 border-2 border-primary-500 border-t-transparent"></div><span className="text-secondary-500">Carregando...</span></div></td></tr>
              ) : data?.length === 0 ? (
                <tr><td colSpan={2} className="px-4 py-8 text-center text-secondary-500">Nenhum ambiente encontrado</td></tr>
              ) : (
                data?.map((item) => (
                  <tr key={item.id} className="hover:bg-secondary-50">
                    <td className="px-4 py-3 font-medium text-secondary-900">{item.nome}</td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button className="p-2 rounded-lg hover:bg-secondary-100 text-secondary-500" onClick={() => { setEditingItem(item); setShowCreateModal(true) }}><Edit className="h-4 w-4" /></button>
                        <button className="p-2 rounded-lg hover:bg-red-50 text-red-500" onClick={() => { if (confirm('Excluir?')) deleteMutation.mutate(item.id) }}><Trash2 className="h-4 w-4" /></button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {(showCreateModal || editingItem) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full">
            <div className="p-6 border-b border-secondary-200"><h2 className="text-xl font-bold text-secondary-900">{editingItem ? 'Editar Ambiente' : 'Novo Ambiente'}</h2></div>
            <form onSubmit={(e) => { e.preventDefault(); const formData = new FormData(e.currentTarget); const data = Object.fromEntries(formData); if (editingItem) updateMutation.mutate({ id: editingItem.id, data }); else createMutation.mutate(data) }}>
              <div className="p-6 space-y-4">
                <div><label className="label">Nome</label><input name="nome" type="text" className="input" defaultValue={editingItem?.nome || ''} required /></div>
              </div>
              <div className="p-4 border-t border-secondary-200 flex justify-end gap-2">
                <button type="button" className="btn-secondary" onClick={() => { setShowCreateModal(false); setEditingItem(null) }}>Cancelar</button>
                <button type="submit" className="btn-primary" disabled={createMutation.isPending || updateMutation.isPending}>{(createMutation.isPending || updateMutation.isPending) ? 'Salvando...' : 'Salvar'}</button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}