import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { useAuthStore } from '../store/auth'
import {
  LayoutDashboard,
  Server,
  Settings,
  RefreshCw,
  ShieldCheck,
  LogOut,
  Menu,
  X,
  ChevronDown,
  Bell,
  Search,
  User,
} from 'lucide-react'
import { useState, useRef, useEffect } from 'react'
import clsx from 'clsx'

interface NavItem {
  name: string
  href?: string
  icon?: React.ComponentType<{ className?: string }>
  children?: NavItem[]
}

const navigation: NavItem[] = [
  { name: 'Dashboard', href: '/', icon: LayoutDashboard },
  { name: 'Inventário', icon: Server, children: [
    { name: 'Hosts', href: '/hosts' },
    { name: 'Relacionamentos', href: '/relationships' },
    { name: 'Aplicações', href: '/applications' },
    { name: 'Clusters', href: '/clusters' },
    { name: 'Namespaces', href: '/namespaces' },
    { name: 'Serviços', href: '/services' },
  ]},
  { name: 'Reconciliação', href: '/reconciliation', icon: RefreshCw },
  { name: 'Certificação', href: '/certification', icon: ShieldCheck },
  { name: 'Administração', icon: Settings, children: [
    { name: 'Usuários', href: '/admin/users' },
    { name: 'Tipos de Relacionamento', href: '/admin/relationship-types' },
    { name: 'Tipos de Ativo', href: '/admin/asset-types' },
    { name: 'Ambientes', href: '/admin/environments' },
    { name: 'Status', href: '/admin/statuses' },
    { name: 'Criticidades', href: '/admin/criticities' },
    { name: 'Sistemas Operacionais', href: '/admin/operating-systems' },
    { name: 'Áreas', href: '/admin/areas' },
  ]},
]

export function Layout() {
  const location = useLocation()
  const { user, logout } = useAuthStore()
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [expandedMenu, setExpandedMenu] = useState<string | null>(null)
  const [userMenuOpen, setUserMenuOpen] = useState(false)
  const userMenuRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setUserMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const isActive = (href: string) => location.pathname === href || location.pathname.startsWith(href + '/')
  const isChildActive = (href: string) => location.pathname.startsWith(href)

  return (
    <div className="min-h-screen bg-secondary-50">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-40 bg-black/50 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside className={clsx(
        'fixed top-0 left-0 z-50 h-full w-64 bg-white border-r border-secondary-200 transform transition-transform duration-200 lg:translate-x-0',
        sidebarOpen ? 'translate-x-0' : '-translate-x-full'
      )}>
        <div className="flex h-16 items-center justify-between px-4 border-b border-secondary-200">
          <h1 className="text-xl font-bold text-primary-600">SGTI CMDB</h1>
          <button
            className="lg:hidden p-2 rounded-lg hover:bg-secondary-100"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <nav className="flex-1 overflow-y-auto p-4 space-y-1" role="navigation" aria-label="Main navigation">
          {navigation.map((item) => {
            const hasChildren = Boolean(item.children && item.children.length > 0)
            const isExpanded = expandedMenu === item.name
            const active = hasChildren ? item.children!.some(c => isChildActive(c.href ?? '')) : isActive(item.href ?? '/')

            return (
              <div key={item.name}>
                {hasChildren ? (
                  <div>
                    <button
                      className={clsx(
                        'w-full flex items-center justify-between px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                        active ? 'bg-primary-50 text-primary-700' : 'text-secondary-700 hover:bg-secondary-100'
                      )}
                      onClick={() => setExpandedMenu(isExpanded ? null : item.name)}
                      aria-expanded={isExpanded}
                    >
                      <span className="flex items-center gap-2">
                        {item.icon && <item.icon className="h-5 w-5" />}
                        {item.name}
                      </span>
                      <ChevronDown className={clsx('h-4 w-4 transition-transform', isExpanded && 'rotate-180')} />
                    </button>
                    {isExpanded && (
                      <ul className="mt-1 ml-6 space-y-1" role="list">
                        {item.children!.map((child) => (
                          <li key={child.name}>
                            <NavLink
                              to={child.href ?? '/'}
                              className={({ isActive }) => clsx(
                                'block px-3 py-2 rounded-lg text-sm transition-colors',
                                isActive ? 'bg-primary-50 text-primary-700 font-medium' : 'text-secondary-600 hover:bg-secondary-100'
                              )}
                            >
                              {child.name}
                            </NavLink>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                ) : (
                  <NavLink
                    to={item.href ?? '/'}
                    className={({ isActive }) => clsx(
                      'flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-colors',
                      isActive ? 'bg-primary-50 text-primary-700' : 'text-secondary-700 hover:bg-secondary-100'
                    )}
                  >
                    {item.icon && <item.icon className="h-5 w-5" />}
                    {item.name}
                  </NavLink>
                )}
              </div>
            )
          })}
        </nav>

        <div className="p-4 border-t border-secondary-200">
          <div className="flex items-center gap-3 px-3 py-2">
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-secondary-900 truncate">{user?.displayName}</p>
              <p className="text-xs text-secondary-500 truncate">{user?.email}</p>
            </div>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 h-16 bg-white border-b border-secondary-200">
          <div className="flex h-full items-center justify-between px-4 sm:px-6">
            <div className="flex items-center gap-4">
              <button
                className="lg:hidden p-2 rounded-lg hover:bg-secondary-100"
                onClick={() => setSidebarOpen(true)}
                aria-label="Open sidebar"
              >
                <Menu className="h-6 w-6" />
              </button>

              <div className="hidden sm:block flex-1 max-w-md">
                <div className="relative">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-secondary-400" />
                  <input
                    type="search"
                    placeholder="Buscar ativos, relacionamentos..."
                    className="w-full pl-10 pr-4 py-2 text-sm bg-secondary-50 border border-secondary-200 rounded-lg focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500/20"
                  />
                </div>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button className="p-2 rounded-lg hover:bg-secondary-100 relative" aria-label="Notifications">
                <Bell className="h-5 w-5 text-secondary-600" />
                <span className="absolute top-1 right-1 h-4 w-4 rounded-full bg-red-500 text-white text-xs flex items-center justify-center">3</span>
              </button>

              <div className="relative" ref={userMenuRef}>
                <button
                  className="flex items-center gap-2 p-2 rounded-lg hover:bg-secondary-100"
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                  aria-expanded={userMenuOpen}
                >
                  <div className="h-8 w-8 rounded-full bg-primary-100 flex items-center justify-center">
                    <User className="h-5 w-5 text-primary-600" />
                  </div>
                  <span className="hidden sm:block text-sm font-medium text-secondary-700">{user?.displayName}</span>
                  <ChevronDown className="h-4 w-4 text-secondary-500" />
                </button>

                {userMenuOpen && (
                  <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg border border-secondary-200 shadow-lg py-1 z-50">
                    <NavLink
                      to="/profile"
                      className="flex items-center gap-2 px-4 py-2 text-sm text-secondary-700 hover:bg-secondary-50"
                    >
                      <User className="h-4 w-4" />
                      Perfil
                    </NavLink>
                    <hr className="my-1 border-secondary-100" />
                    <button
                      onClick={() => logout()}
                      className="flex items-center gap-2 w-full px-4 py-2 text-sm text-red-600 hover:bg-red-50"
                    >
                      <LogOut className="h-4 w-4" />
                      Sair
                    </button>
                  </div>
                )}
              </div>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 sm:p-6 lg:p-8">
          <Outlet />
        </main>
      </div>
    </div>
  )
}