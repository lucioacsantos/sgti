import { Link } from 'react-router-dom'
import { Home, Search, AlertCircle } from 'lucide-react'

export function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-secondary-50 px-4">
      <div className="text-center">
        <div className="inline-flex items-center justify-center w-24 h-24 rounded-full bg-yellow-100 mb-6">
          <AlertCircle className="h-12 w-12 text-yellow-600" />
        </div>
        <h1 className="text-4xl font-bold text-secondary-900 mb-2">Página não encontrada</h1>
        <p className="text-secondary-500 text-lg mb-8 max-w-md mx-auto">
          A página que você está procurando não existe ou foi movida.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 justify-center">
          <Link to="/" className="btn-primary">
            <Home className="h-4 w-4" />
            Voltar ao Início
          </Link>
          <Link to="/hosts" className="btn-secondary">
            <Search className="h-4 w-4" />
            Explorar Hosts
          </Link>
        </div>
      </div>
    </div>
  )
}