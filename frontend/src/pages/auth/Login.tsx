import { useState } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { useAuthStore } from '../../store/auth'
import { Server, Eye, EyeOff, Loader2, Zap, Shield } from 'lucide-react'
import clsx from 'clsx'

const loginSchema = z.object({
  username: z.string().min(1, 'Usuário é obrigatório'),
  password: z.string().min(1, 'Senha é obrigatória'),
})

type LoginForm = z.infer<typeof loginSchema>

const isTestMode = import.meta.env.VITE_TEST_MODE === 'true' || import.meta.env.MODE === 'test'

export function Login() {
  const navigate = useNavigate()
  const location = useLocation()
  const { login, testLogin, isLoading, error } = useAuthStore()
  const [showPassword, setShowPassword] = useState(false)
  const [testModeLoading, setTestModeLoading] = useState(false)

  const from = location.state?.from?.pathname || '/'

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<LoginForm>({
    resolver: zodResolver(loginSchema),
  })

  const onSubmit = async (data: LoginForm) => {
    try {
      await login(data.username, data.password)
      // Check if 2FA is required
      const { user } = useAuthStore.getState()
      if (user?.requires2FA) {
        navigate('/2fa/verify', { state: { from } })
      } else {
        navigate(from, { replace: true })
      }
    } catch (err) {
      // Error handled by store
    }
  }

  const onTestLogin = async () => {
    setTestModeLoading(true)
    try {
      await testLogin()
      navigate(from, { replace: true })
    } catch (err) {
      // Error handled by store
    } finally {
      setTestModeLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-secondary-50 px-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-primary-100 mb-4">
            <Server className="h-8 w-8 text-primary-600" />
          </div>
          <h1 className="text-2xl font-bold text-secondary-900">SGTI CMDB</h1>
          <p className="text-secondary-500 mt-1">Sistema de Gerenciamento de TI</p>
          {isTestMode && (
            <span className="inline-flex items-center gap-1 mt-2 px-2 py-1 text-xs font-medium rounded-full bg-yellow-100 text-yellow-800">
              <Zap className="h-3 w-3" />
              Modo de Teste
            </span>
          )}
        </div>

        <div className="card p-6">
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            {error && (
              <div className="p-3 rounded-lg bg-red-50 text-red-700 text-sm" role="alert">
                {error}
              </div>
            )}

            <div>
              <label htmlFor="username" className="label">Usuário</label>
              <div className="relative">
                <input
                  id="username"
                  type="text"
                  autoComplete="username"
                  className={clsx('input pl-10', errors.username && 'border-red-500 focus:border-red-500')}
                  placeholder="seu.usuario"
                  {...register('username')}
                />
                <Server className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-secondary-400" />
              </div>
              {errors.username && (
                <p className="mt-1 text-sm text-red-600">{errors.username.message}</p>
              )}
            </div>

            <div>
              <label htmlFor="password" className="label">Senha</label>
              <div className="relative">
                <input
                  id="password"
                  type={showPassword ? 'text' : 'password'}
                  autoComplete="current-password"
                  className={clsx('input pl-10 pr-10', errors.password && 'border-red-500 focus:border-red-500')}
                  placeholder="••••••••"
                  {...register('password')}
                />
                <button
                  type="button"
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-secondary-400 hover:text-secondary-600"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? 'Ocultar senha' : 'Mostrar senha'}
                >
                  {showPassword ? <EyeOff className="h-5 w-5" /> : <Eye className="h-5 w-5" />}
                </button>
              </div>
              {errors.password && (
                <p className="mt-1 text-sm text-red-600">{errors.password.message}</p>
              )}
            </div>

            <div className="flex items-center justify-between">
              <label className="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" className="rounded border-secondary-300 text-primary-600 focus:ring-primary-500" />
                <span className="text-sm text-secondary-600">Lembrar-me</span>
              </label>
              <a href="#" className="text-sm text-primary-600 hover:text-primary-700">Esqueci a senha</a>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="btn-primary w-full py-2.5"
            >
              {isLoading ? (
                <span className="flex items-center justify-center gap-2">
                  <Loader2 className="h-5 w-5 animate-spin" />
                  Entrando...
                </span>
              ) : (
                'Entrar'
              )}
            </button>
          </form>

          {isTestMode && (
            <div className="mt-6 pt-6 border-t border-secondary-200">
              <div className="mb-3 text-center text-sm text-secondary-500">
                <p className="flex items-center justify-center gap-1">
                  <Shield className="h-4 w-4" />
                  Acesso rápido para desenvolvimento/teste
                </p>
              </div>
              <button
                type="button"
                disabled={testModeLoading || isLoading}
                onClick={onTestLogin}
                className="btn-secondary w-full py-2.5 flex items-center justify-center gap-2"
              >
                {testModeLoading ? (
                  <span className="flex items-center justify-center gap-2">
                    <Loader2 className="h-5 w-5 animate-spin" />
                    Entrando como teste...
                  </span>
                ) : (
                  <>
                    <Zap className="h-5 w-5" />
                    Entrar como Usuário de Teste (Admin)
                  </>
                )}
              </button>
            </div>
          )}

          {!isTestMode && (
            <div className="mt-6 text-center text-sm text-secondary-500">
              <p>Use suas credenciais do Active Directory</p>
              <p className="mt-1">Autenticação de dois fatores obrigatória</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}