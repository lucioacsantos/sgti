import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuthStore } from '../../store/auth'
import { Loader2, CheckCircle, Smartphone, QrCode } from 'lucide-react'
import QRCode from 'qrcode.react'

export function TwoFASetup() {
  const navigate = useNavigate()
  const { setup2FA, enable2FA, user } = useAuthStore()
  const [loading, setLoading] = useState(false)
  const [setupData, setSetupData] = useState<{ secret: string; qrCode: string } | null>(null)
  const [code, setCode] = useState('')
  const [step, setStep] = useState<'loading' | 'qr' | 'verify' | 'complete'>('loading')
  const [error, setError] = useState('')

  useEffect(() => {
    const init2FA = async () => {
      if (user?.twoFAEnabled) {
        navigate('/')
        return
      }
      try {
        const data = await setup2FA()
        setSetupData(data)
        setStep('qr')
      } catch (err) {
        setError('Erro ao configurar 2FA')
        setStep('qr')
      }
    }
    init2FA()
  }, [setup2FA, user?.twoFAEnabled, navigate])

  const handleVerify = async () => {
    if (!code || code.length !== 6) {
      setError('Digite o código de 6 dígitos')
      return
    }
    setLoading(true)
    setError('')
    try {
      await enable2FA(code)
      setStep('complete')
      setTimeout(() => navigate('/'), 2000)
    } catch (err) {
      setError('Código inválido. Tente novamente.')
    } finally {
      setLoading(false)
    }
  }

  if (step === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary-50">
        <Loader2 className="h-12 w-12 animate-spin text-primary-600" />
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-secondary-50 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary-100 mb-4">
            <QrCode className="h-8 w-8 text-primary-600" />
          </div>
          <h1 className="text-2xl font-bold text-secondary-900">Configurar Autenticação de Dois Fatores</h1>
          <p className="text-secondary-500 mt-1">Proteja sua conta com um app autenticador</p>
        </div>

        <div className="card p-6">
          {step === 'qr' && setupData && (
            <div className="space-y-6">
              <div className="text-center">
                <p className="text-sm text-secondary-600 mb-4">
                  Escaneie o QR Code com seu app autenticador
                </p>
                <div className="inline-block p-4 bg-white rounded-lg border border-secondary-200">
                  <QRCode
                    value={setupData.qrCode}
                    size={200}
                    level="M"
                    includeMargin={true}
                  />
                </div>
                <p className="mt-4 text-xs text-secondary-500">
                  Chave secreta: <code className="font-mono text-secondary-700">{setupData.secret}</code>
                </p>
              </div>

              <div className="p-4 bg-secondary-50 rounded-lg">
                <h3 className="font-medium text-secondary-900 mb-2 flex items-center gap-2">
                  <Smartphone className="h-5 w-5" />
                  Apps Compatíveis
                </h3>
                <ul className="text-sm text-secondary-600 space-y-1">
                  <li>• Google Authenticator</li>
                  <li>• Microsoft Authenticator</li>
                  <li>• Authy</li>
                  <li>• 1Password</li>
                </ul>
              </div>

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
                  className="input text-center text-lg tracking-widest font-mono"
                  placeholder="000000"
                  value={code}
                  onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
                  onKeyDown={(e) => e.key === 'Enter' && handleVerify()}
                />
              </div>

              <button
                onClick={handleVerify}
                disabled={loading}
                className="btn-primary w-full py-2.5"
              >
                {loading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    Verificando...
                  </span>
                ) : (
                  'Verificar e Ativar'
                )}
              </button>
            </div>
          )}

          {step === 'complete' && (
            <div className="text-center py-8">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-green-100 mb-4">
                <CheckCircle className="h-8 w-8 text-green-600" />
              </div>
              <h2 className="text-xl font-bold text-secondary-900">2FA Ativado com Sucesso!</h2>
              <p className="text-secondary-500 mt-2">Sua conta agora está protegida com autenticação de dois fatores.</p>
              <p className="text-sm text-secondary-400 mt-4">Redirecionando...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}