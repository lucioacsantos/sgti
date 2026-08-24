import { NavLink, Outlet } from 'react-router-dom'
import { Settings, Users, Link, Box, Building2, Flag, Cpu, FolderOpen, ShieldCheck } from 'lucide-react'
import clsx from 'clsx'

const adminSections = [
  { name: 'Visão Geral', href: '/admin', icon: Settings },
  { name: 'Usuários', href: '/admin/users', icon: Users },
  { name: 'Tipos de Relacionamento', href: '/admin/relationship-types', icon: Link },
  { name: 'Tipos de Ativo', href: '/admin/asset-types', icon: Box },
  { name: 'Ambientes', href: '/admin/environments', icon: Building2 },
  { name: 'Status', href: '/admin/statuses', icon: Flag },
  { name: 'Criticidades', href: '/admin/criticities', icon: ShieldCheck },
  { name: 'Sistemas Operacionais', href: '/admin/operating-systems', icon: Cpu },
  { name: 'Áreas', href: '/admin/areas', icon: FolderOpen },
]

export function AdminSettings() {
  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Administração</h1>
          <p className="text-secondary-500">Configurações do sistema CMDB</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
        {/* Sidebar */}
        <div className="lg:col-span-1">
          <nav className="card p-2 space-y-1" aria-label="Admin navigation">
            {adminSections.map((section) => (
              <NavLink
                key={section.name}
                to={section.href}
                className={({ isActive }) => clsx(
                  'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary-50 text-primary-700'
                    : 'text-secondary-700 hover:bg-secondary-100'
                )}
              >
                <section.icon className="h-5 w-5" />
                {section.name}
              </NavLink>
            ))}
          </nav>
        </div>

        {/* Content */}
        <div className="lg:col-span-3">
          <Outlet />
        </div>
      </div>
    </div>
  )
}