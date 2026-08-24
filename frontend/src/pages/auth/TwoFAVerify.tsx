import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useAuthStore } from '../../store/auth'
import { Loader2, Smartphone, RefreshCw } from 'lucide-react'

export function TwoFAVerify() {
  const navigate = useNavigate()
  const location = useLocation()
  const { verify2FA } = useAuthStore()
  const [code, setCode] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  const from = location.state?.from?.pathname || '/'

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!code || code.length !== 6) {
      setError('Digite o código de 6 dígitos')
      return
    }
    setLoading(true)
    setError('')
    try {
      await verify2FA(code)
      navigate(from, { replace: true })
    } catch (err) {
      setError('Código inválido ou expirado. Tente novamente.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-secondary-50 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary-100 mb-4">
            <Smartphone className="h-8 w-8 text-primary-600" />
          </div>
          <h1 className="text-2xl font-bold text-secondary-900">Autenticação de Dois Fatores</h1>
          <p className="text-secondary-500 mt-1">Digite o código do seu app autenticador</p>
        </div>

        <div className="card p-6">
          <form onSubmit={handleSubmit} className="space-y-4">
            {error && (
              <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm" role="alert">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="2fa-code" className="label">Código de 6 dígitos</label>
              <input
                id="2fa-code"
                type="text"
                maxLength={6}
                autoComplete="one-time-code"
                autoFocus
                className="input text-center text-lg tracking-widest font-mono"
                placeholder="000000"
                value={code}
                onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="btn-primary w-full py-2.5"
            >
              {loading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Verificando...
                </span>
              ) : (
                'Verificar'
              )}
            </button>

            <div className="text-center">
              <button
                type="button"
                onClick={() => navigate('/login')}
                className="text-sm text-primary-600 hover:text-primary-700"
                disabled={loading}
              >
                <RefreshCw className="inline h-3 w-3 mr-1" />
                Voltar ao login
              </button>
            </div>
          </form>

          <div className="mt-6 p-4 bg-secondary-50 rounded-lg">
            <h3 className="font-medium text-secondary-900 mb-2 flex items-center gap-2 justify-center">
              <Smartphone className="h-5 w-5" />
              Apps Compatíveis
            </h3>
            <ul className="text-sm text-secondary-600 space-y-1 text-center">
              <li>Google Authenticator</li>
              <li>Microsoft Authenticator</li>
              <li>Authy</li>
              <li>1Password</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  )
}