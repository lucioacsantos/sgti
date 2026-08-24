import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useAuthStore } from '../store/auth'
import { User, Lock, Smartphone, Loader2, CheckCircle, AlertCircle, Eye, EyeOff, LogOut } from 'lucide-react'
import QRCode from 'qrcode.react'
import clsx from 'clsx'

export function Profile() {
  const { user, setup2FA, enable2FA, disable2FA, logout } = useAuthStore()
  const [activeTab, setActiveTab] = useState<'profile' | 'security' | '2fa'>('profile')
  const [showCurrentPassword, setShowCurrentPassword] = useState(false)
  const [showNewPassword, setShowNewPassword] = useState(false)
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null)
  const [loading, setLoading] = useState(false)

  const [setup2FAData, setSetup2FAData] = useState<{ secret: string; qrCode: string } | null>(null)
  const [verifyCode, setVerifyCode] = useState('')

  const profileForm = useForm({
    defaultValues: {
      displayName: user?.displayName || '',
      email: user?.email || '',
    },
  })

  const passwordForm = useForm({
    defaultValues: {
      currentPassword: '',
      newPassword: '',
      confirmPassword: '',
    },
  })

  const handleProfileSubmit = async () => {
    setLoading(true)
    setMessage(null)
    try {
      // Call API to update profile
      await new Promise(resolve => setTimeout(resolve, 1000))
      setMessage({ type: 'success', text: 'Perfil atualizado com sucesso!' })
    } catch (error) {
      setMessage({ type: 'error', text: 'Erro ao atualizar perfil' })
    } finally {
      setLoading(false)
    }
  }

  const handlePasswordSubmit = async (data: any) => {
    if (data.newPassword !== data.confirmPassword) {
      setMessage({ type: 'error', text: 'As senhas não conferem' })
      return
    }
    setLoading(true)
    setMessage(null)
    try {
      // Call API to change password
      await new Promise(resolve => setTimeout(resolve, 1000))
      setMessage({ type: 'success', text: 'Senha alterada com sucesso!' })
      passwordForm.reset()
    } catch (error) {
      setMessage({ type: 'error', text: 'Erro ao alterar senha' })
    } finally {
      setLoading(false)
    }
  }

  const handleSetup2FA = async () => {
    setLoading(true)
    try {
      const data = await setup2FA()
      setSetup2FAData(data)
      setActiveTab('2fa')
    } catch (error) {
      setMessage({ type: 'error', text: 'Erro ao configurar 2FA' })
    } finally {
      setLoading(false)
    }
  }

  const handleEnable2FA = async () => {
    if (!verifyCode || verifyCode.length !== 6) {
      setMessage({ type: 'error', text: 'Digite o código de 6 dígitos' })
      return
    }
    setLoading(true)
    try {
      await enable2FA(verifyCode)
      setMessage({ type: 'success', text: '2FA ativado com sucesso!' })
      setSetup2FAData(null)
      setVerifyCode('')
      setActiveTab('security')
    } catch (error) {
      setMessage({ type: 'error', text: 'Código inválido' })
    } finally {
      setLoading(false)
    }
  }

  const handleDisable2FA = async () => {
    const password = prompt('Digite sua senha para confirmar:')
    if (!password) return
    
    setLoading(true)
    try {
      await disable2FA(password)
      setMessage({ type: 'success', text: '2FA desativado' })
    } catch (error) {
      setMessage({ type: 'error', text: 'Erro ao desativar 2FA' })
    } finally {
      setLoading(false)
    }
  }

  const handleLogout = () => {
    if (confirm('Tem certeza que deseja sair?')) {
      logout()
    }
  }

  if (!user) return null

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold text-secondary-900">Meu Perfil</h1>
          <p className="text-secondary-500">Gerenciar suas configurações pessoais</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="card">
        <div className="border-b border-secondary-200">
          <nav className="flex gap-1 px-4" aria-label="Profile tabs">
            {[
              { id: 'profile', label: 'Perfil', icon: User },
              { id: 'security', label: 'Segurança', icon: Lock },
              { id: '2fa', label: 'Autenticação 2FA', icon: Smartphone },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as any)}
                className={clsx(
                  'flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors',
                  activeTab === tab.id
                    ? 'border-primary-500 text-primary-600'
                    : 'border-transparent text-secondary-500 hover:text-secondary-700 hover:border-secondary-300'
                )}
              >
                <tab.icon className="h-4 w-4" />
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        <div className="p-6">
          {message && (
            <div className={clsx('mb-6 p-4 rounded-lg', message.type === 'success' ? 'bg-green-50 text-green-700' : 'bg-red-50 text-red-700')}>
              {message.text}
            </div>
          )}

          {/* Profile Tab */}
          {activeTab === 'profile' && (
            <form onSubmit={profileForm.handleSubmit(handleProfileSubmit)} className="space-y-6 max-w-2xl">
              <div className="flex items-center gap-6">
                <div className="h-20 w-20 rounded-full bg-primary-100 flex items-center justify-center">
                  <User className="h-10 w-10 text-primary-600" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-secondary-900">{user?.displayName}</h3>
                  <p className="text-secondary-500">@{user?.username}</p>
                  <p className="text-sm text-secondary-400 mt-1">Membro desde {new Date().getFullYear()}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="label">Nome de Exibição</label>
                  <input
                    type="text"
                    className="input"
                    {...profileForm.register('displayName')}
                  />
                </div>
                <div>
                  <label className="label">Email</label>
                  <input
                    type="email"
                    className="input"
                    {...profileForm.register('email')}
                  />
                </div>
              </div>

              <div className="flex justify-end">
                <button type="submit" className="btn-primary" disabled={loading}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Salvar Alterações'}
                </button>
              </div>
            </form>
          )}

          {/* Security Tab */}
          {activeTab === 'security' && (
            <form onSubmit={passwordForm.handleSubmit(handlePasswordSubmit)} className="space-y-6 max-w-md">
              <div className="p-4 bg-secondary-50 rounded-lg">
                <h3 className="font-medium text-secondary-900 flex items-center gap-2">
                  <Lock className="h-5 w-5" />
                  Alterar Senha
                </h3>
                <p className="text-sm text-secondary-500 mt-1">Sua senha é gerenciada pelo Active Directory. Esta opção altera a senha local do sistema.</p>
              </div>

              <div>
                <label className="label">Senha Atual</label>
                <div className="relative">
                  <input
                    type={showCurrentPassword ? 'text' : 'password'}
                    className="input pr-10"
                    {...passwordForm.register('currentPassword')}
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-secondary-400"
                    onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                  >
                    {showCurrentPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="label">Nova Senha</label>
                <div className="relative">
                  <input
                    type={showNewPassword ? 'text' : 'password'}
                    className="input pr-10"
                    {...passwordForm.register('newPassword')}
                  />
                  <button
                    type="button"
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-secondary-400"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                  >
                    {showNewPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                  </button>
                </div>
              </div>

              <div>
                <label className="label">Confirmar Nova Senha</label>
                <input
                  type={showNewPassword ? 'text' : 'password'}
                  className="input"
                  {...passwordForm.register('confirmPassword')}
                />
              </div>

              <div className="flex justify-end">
                <button type="submit" className="btn-primary" disabled={loading}>
                  {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Alterar Senha'}
                </button>
              </div>
            </form>
          )}

          {/* 2FA Tab */}
          {activeTab === '2fa' && (
            <div className="max-w-2xl space-y-6">
              {user?.twoFAEnabled ? (
                // 2FA Enabled
                <div className="card p-6 border-l-4 border-green-500">
                  <div className="flex items-center gap-4">
                    <div className="h-16 w-16 rounded-full bg-green-100 flex items-center justify-center">
                      <CheckCircle className="h-8 w-8 text-green-600" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-secondary-900">Autenticação de Dois Fatores Ativada</h3>
                      <p className="text-secondary-500">Sua conta está protegida com um app autenticador.</p>
                    </div>
                  </div>
                  <div className="mt-4 flex gap-2">
                    <button
                      className="btn-danger"
                      onClick={handleDisable2FA}
                      disabled={loading}
                    >
                      <Lock className="h-4 w-4" />
                      Desativar 2FA
                    </button>
                  </div>
                </div>
              ) : setup2FAData ? (
                // QR Code Setup
                <div className="card p-6">
                  <div className="text-center">
                    <h3 className="text-lg font-semibold text-secondary-900 mb-4">Configurar App Autenticador</h3>
                    <p className="text-secondary-500 mb-6">Escaneie o QR Code abaixo com seu app autenticador</p>
                    
                    <div className="inline-block p-4 bg-white rounded-lg border border-secondary-200 mb-6">
                      <QRCode
                        value={setup2FAData.qrCode}
                        size={200}
                        level="M"
                        includeMargin={true}
                      />
                    </div>
                    
                    <p className="text-xs text-secondary-500 mb-6">
                      Chave secreta: <code className="font-mono text-secondary-700">{setup2FAData.secret}</code>
                    </p>

                    <div className="p-4 bg-secondary-50 rounded-lg mb-6">
                      <h4 className="font-medium text-secondary-900 mb-2 flex items-center gap-2 justify-center">
                        <Smartphone className="h-5 w-5" />
                        Apps Compatíveis
                      </h4>
                      <ul className="text-sm text-secondary-600 space-y-1 text-center">
                        <li>Google Authenticator</li>
                        <li>Microsoft Authenticator</li>
                        <li>Authy</li>
                        <li>1Password</li>
                      </ul>
                    </div>

                    <div>
                      <label className="label">Código de 6 dígitos</label>
                      <input
                        type="text"
                        maxLength={6}
                        autoComplete="one-time-code"
                        className="input text-center text-lg tracking-widest font-mono"
                        placeholder="000000"
                        value={verifyCode}
                        onChange={(e) => setVerifyCode(e.target.value.replace(/\D/g, ''))}
                        onKeyDown={(e) => e.key === 'Enter' && handleEnable2FA()}
                      />
                    </div>

                    <div className="flex gap-2">
                      <button
                        className="btn-primary flex-1"
                        onClick={handleEnable2FA}
                        disabled={loading}
                      >
                        {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Verificar e Ativar'}
                      </button>
                      <button
                        className="btn-secondary"
                        onClick={() => { setSetup2FAData(null); setActiveTab('security') }}
                        disabled={loading}
                      >
                        Cancelar
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                // 2FA Not Enabled
                <div className="card p-6 border-l-4 border-yellow-500">
                  <div className="flex items-center gap-4">
                    <div className="h-16 w-16 rounded-full bg-yellow-100 flex items-center justify-center">
                      <AlertCircle className="h-8 w-8 text-yellow-600" />
                    </div>
                    <div>
                      <h3 className="text-lg font-semibold text-secondary-900">Autenticação de Dois Fatores Desativada</h3>
                      <p className="text-secondary-500">Adicione uma camada extra de segurança à sua conta.</p>
                    </div>
                  </div>
                  <div className="mt-4">
                    <button
                      className="btn-primary"
                      onClick={handleSetup2FA}
                      disabled={loading}
                    >
                      <Smartphone className="h-4 w-4" />
                      Configurar 2FA
                    </button>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* Danger Zone */}
          <div className="card p-6 border-l-4 border-red-500">
            <h3 className="font-semibold text-secondary-900 flex items-center gap-2 mb-4">
              <AlertCircle className="h-5 w-5 text-red-600" />
              Zona de Perigo
            </h3>
            <p className="text-secondary-500 mb-4">Ações irreversíveis. Use com cautela.</p>
            <button
              className="btn-danger"
              onClick={handleLogout}
            >
              <LogOut className="h-4 w-4" />
              Sair do Sistema
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}