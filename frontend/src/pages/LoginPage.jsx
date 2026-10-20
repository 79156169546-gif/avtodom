import { useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'

export default function LoginPage() {
  const { signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const redirectTo = location.state?.from || '/cabinet'

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    setBusy(true)
    try {
      const user = await signIn(email, password)
      navigate(user.role === 'owner' ? '/admin' : redirectTo, { replace: true })
    } catch (err) {
      setError(err.message || 'Не удалось войти')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">Вход в личный кабинет</h1>
      <p className="mt-1 text-sm text-gray-500">
        Чтобы отслеживать статус заказов и историю покупок.
      </p>

      <form onSubmit={submit} className="card mt-6 space-y-4 p-5">
        <div>
          <label className="label" htmlFor="login-email">
            E-mail
          </label>
          <input
            id="login-email"
            data-testid="login-email"
            type="email"
            autoComplete="email"
            required
            className="field"
            placeholder="you@example.ru"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
          />
        </div>
        <div>
          <label className="label" htmlFor="login-password">
            Пароль
          </label>
          <input
            id="login-password"
            data-testid="login-password"
            type="password"
            autoComplete="current-password"
            required
            className="field"
            placeholder="••••••••"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
          />
        </div>

        {error ? (
          <p
            data-testid="login-error"
            className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          data-testid="login-submit"
          className="btn-primary w-full"
          disabled={busy}
        >
          {busy ? 'Входим…' : 'Войти'}
        </button>
      </form>

      <p className="mt-4 text-center text-sm text-gray-600">
        Нет аккаунта?{' '}
        <Link to="/register" className="font-semibold text-accent-strong">
          Зарегистрироваться
        </Link>
      </p>
    </div>
  )
}
