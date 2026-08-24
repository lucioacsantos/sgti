import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { adminApi } from '../../lib/api'
import { Search, UserPlus, Edit, Trash2, Mail, Lock, RefreshCw } from 'lucide-react'
import clsx from 'clsx'

const roles = ['admin', 'analyst', 'reviewer', 'reconciliator', 'revisor', 'viewer']

export function AdminUsers() {
  const queryClient = useQueryClient()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const pageSize = 20
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [editingUser, setEditingUser] = useState<any>(null)

  const { data: usersData, isLoading, refetch } = useQuery({
    queryKey: ['admin-users', { page, pageSize, search }],
    queryFn: () => adminApi.users.list({ skip: (page - 1) * pageSize, limit: pageSize }),
  })

  const users = usersData

  const createMutation = useMutation({
    mutationFn: (data: any) => adminApi.users.create(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      setShowCreateModal(false)
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => adminApi.users.update(id, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-users'] })
      setEditingUser(null)
    },
  })

  const deleteMutation = useMutation({
    mutationFn: (id: string) => adminApi.users.delete(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['admin-users'] }),
  })

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Usuários</h1>
          <p className="text-secondary-500">Gerenciar usuários e permissões do sistema</p>
        </div>
        <div className="flex gap-2">
          <button className="btn-secondary" onClick={() => refetch()} disabled={isLoading}>
            <RefreshCw className={clsx('h-4 w-4', isLoading && 'animate-spin')} />
            Atualizar
          </button>
          <button className="btn-primary" onClick={() => { setEditingUser(null); setShowCreateModal(true) }}>
            <UserPlus className="h-4 w-4" />
            Novo Usuário
          </button>
        </div>
      </div>

      <div className="card p-4">
        <div className="flex gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-secondary-400" />
            <input
              type="search"
              placeholder="Buscar por nome, email..."
              className="input pl-10"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
        </div>
      </div>

      <div className="card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full" role="grid">
            <thead className="bg-secondary-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Usuário</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Email</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Roles</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Grupos AD</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">2FA</th>
                <th className="px-4 py-3 text-left text-xs font-semibold text-secondary-500 uppercase tracking-wider">Status</th>
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
              ) : Array.isArray(users) && users.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-secondary-500">
                    Nenhum usuário encontrado
                  </td>
                </tr>
              ) : (
                (Array.isArray(users) ? users : []).map((user: any) => (
                  <tr key={user.id} className="hover:bg-secondary-50">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="h-8 w-8 rounded-full bg-primary-100 flex items-center justify-center">
                          <span className="text-primary-600 font-medium">
                            {user.displayName?.charAt(0) || user.username?.charAt(0) || 'U'}
                          </span>
                        </div>
                        <div>
                          <p className="font-medium text-secondary-900">{user.displayName || user.username}</p>
                          <p className="text-xs text-secondary-500">@{user.username}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <Mail className="h-4 w-4 text-secondary-400 inline mr-1" />
                      <span className="text-sm text-secondary-700">{user.email}</span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1">
                        {user.roles?.map((role: string) => (
                          <span key={role} className="badge badge-primary text-xs">{role}</span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-secondary-600">
                      {user.groups?.join(', ') || '—'}
                    </td>
                    <td className="px-4 py-3">
                      {user.twoFAEnabled ? (
                        <span className="badge badge-success flex items-center gap-1">
                          <Lock className="h-3 w-3" />
                          Ativado
                        </span>
                      ) : (
                        <span className="badge badge-secondary">Desativado</span>
                      )}
                    </td>
                    <td className="px-4 py-3">
                      <span className={clsx('badge', user.isActive ? 'badge-success' : 'badge-danger')}>
                        {user.isActive ? 'Ativo' : 'Inativo'}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-right">
                      <div className="flex items-center justify-end gap-1">
                        <button
                          className="p-2 rounded-lg hover:bg-secondary-100 text-secondary-500"
                          onClick={() => { setEditingUser(user); setShowCreateModal(true) }}
                        >
                          <Edit className="h-4 w-4" />
                        </button>
                        <button
                          className="p-2 rounded-lg hover:bg-red-50 text-red-500"
                          onClick={() => { if (confirm('Excluir este usuário?')) deleteMutation.mutate(user.id) }}
                        >
                          <Trash2 className="h-4 w-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {false && usersData && (usersData as any).total_pages > 1 && (
          <div className="px-4 py-3 border-t border-secondary-200 flex items-center justify-between">
            <div className="text-sm text-secondary-500">
              Mostrando {(page - 1) * pageSize + 1} a {Math.min(page * pageSize, (usersData as any).total)} de {(usersData as any).total}
            </div>
            <div className="flex gap-2">
              <button className="btn-secondary text-sm" disabled={page === 1} onClick={() => setPage(p => p - 1)}>Anterior</button>
              <button className="btn-secondary text-sm" disabled={page === (usersData as any).total_pages} onClick={() => setPage(p => p + 1)}>Próxima</button>
            </div>
          </div>
        )}
      </div>

      {/* Create/Edit Modal */}
      {(showCreateModal || editingUser) && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl shadow-xl max-w-md w-full max-h-[90vh] overflow-y-auto">
            <div className="p-6 border-b border-secondary-200">
              <h2 className="text-xl font-bold text-secondary-900">{editingUser ? 'Editar Usuário' : 'Novo Usuário'}</h2>
            </div>
            <form onSubmit={(e) => { e.preventDefault(); const formData = new FormData(e.currentTarget); const data = Object.fromEntries(formData); if (editingUser) updateMutation.mutate({ id: editingUser.id, data }); else createMutation.mutate(data) }}>
              <div className="p-6 space-y-4">
                <div>
                  <label className="label">Nome de Exibição</label>
                  <input name="displayName" type="text" className="input" defaultValue={editingUser?.displayName || ''} required />
                </div>
                <div>
                  <label className="label">Username (AD)</label>
                  <input name="username" type="text" className="input" defaultValue={editingUser?.username || ''} required disabled={!!editingUser} />
                </div>
                <div>
                  <label className="label">Email</label>
                  <input name="email" type="email" className="input" defaultValue={editingUser?.email || ''} required />
                </div>
                <div>
                  <label className="label">Roles</label>
                  <div className="flex flex-wrap gap-2">
                    {roles.map(role => (
                      <label key={role} className="flex items-center gap-2 cursor-pointer">
                        <input
                          type="checkbox"
                          name="roles"
                          value={role}
                          defaultChecked={editingUser?.roles?.includes(role) || false}
                          className="rounded border-secondary-300 text-primary-600 focus:ring-primary-500"
                        />
                        <span className="text-sm text-secondary-700 capitalize">{role}</span>
                      </label>
                    ))}
                  </div>
                </div>
                <div>
                  <label className="label">Grupos AD (separados por vírgula)</label>
                  <input name="groups" type="text" className="input" defaultValue={editingUser?.groups?.join(', ') || ''} placeholder="grupo1, grupo2" />
                </div>
                <div className="flex items-center gap-2">
                  <input name="isActive" type="checkbox" id="isActive" defaultChecked={editingUser?.isActive !== false} className="rounded border-secondary-300 text-primary-600 focus:ring-primary-500" />
                  <label htmlFor="isActive" className="text-sm text-secondary-700">Usuário ativo</label>
                </div>
              </div>
              <div className="p-4 border-t border-secondary-200 flex justify-end gap-2">
                <button type="button" className="btn-secondary" onClick={() => { setShowCreateModal(false); setEditingUser(null) }}>Cancelar</button>
                <button type="submit" className="btn-primary" disabled={createMutation.isPending || updateMutation.isPending}>
                  {(createMutation.isPending || updateMutation.isPending) ? 'Salvando...' : 'Salvar'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  )
}