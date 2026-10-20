import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth.jsx'

export default function RegisterPage() {
  const { signUp } = useAuth()
  const navigate = useNavigate()
  const [form, setForm] = useState({
    full_name: '',
    email: '',
    phone: '',
    telegram: '',
    password: '',
    password2: '',
  })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const update = (field) => (event) => {
    const { value } = event.target
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const submit = async (event) => {
    event.preventDefault()
    setError('')
    if (form.password !== form.password2) {
      setError('Пароли не совпадают')
      return
    }
    setBusy(true)
    try {
      await signUp({
        email: form.email,
        password: form.password,
        full_name: form.full_name || null,
        phone: form.phone || null,
        telegram: form.telegram || null,
      })
      navigate('/cabinet', { replace: true })
    } catch (err) {
      setError(err.message || 'Не удалось зарегистрироваться')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="mx-auto max-w-md px-4 py-10">
      <h1 className="text-2xl font-bold text-gray-900">Регистрация</h1>
      <p className="mt-1 text-sm text-gray-500">
        Аккаунт нужен, чтобы отслеживать статус заказа и не вводить данные
        каждый раз заново.
      </p>

      <form onSubmit={submit} className="card mt-6 space-y-4 p-5">
        <div>
          <label className="label" htmlFor="reg-name">
            Имя
          </label>
          <input
            id="reg-name"
            data-testid="register-name"
            className="field"
            placeholder="Иван"
            value={form.full_name}
            onChange={update('full_name')}
          />
        </div>
        <div>
          <label className="label" htmlFor="reg-email">
            E-mail
          </label>
          <input
            id="reg-email"
            data-testid="register-email"
            type="email"
            autoComplete="email"
            required
            className="field"
            placeholder="you@example.ru"
            value={form.email}
            onChange={update('email')}
          />
        </div>
        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="label" htmlFor="reg-phone">
              Телефон
            </label>
            <input
              id="reg-phone"
              data-testid="register-phone"
              className="field"
              placeholder="+7 900 000-00-00"
              value={form.phone}
              onChange={update('phone')}
            />
          </div>
          <div>
            <label className="label" htmlFor="reg-telegram">
              Telegram
            </label>
            <input
              id="reg-telegram"
              data-testid="register-telegram"
              className="field"
              placeholder="@username"
              value={form.telegram}
              onChange={update('telegram')}
            />
          </div>
        </div>
        <div>
          <label className="label" htmlFor="reg-password">
            Пароль
          </label>
          <input
            id="reg-password"
            data-testid="register-password"
            type="password"
            autoComplete="new-password"
            required
            minLength={6}
            className="field"
            placeholder="Минимум 6 символов"
            value={form.password}
            onChange={update('password')}
          />
        </div>
        <div>
          <label className="label" htmlFor="reg-password2">
            Пароль ещё раз
          </label>
          <input
            id="reg-password2"
            data-testid="register-password2"
            type="password"
            autoComplete="new-password"
            required
            className="field"
            value={form.password2}
            onChange={update('password2')}
          />
        </div>

        {error ? (
          <p
            data-testid="register-error"
            className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700"
          >
            {error}
          </p>
        ) : null}

        <button
          type="submit"
          data-testid="register-submit"
          className="btn-primary w-full"
          disabled={busy}
        >
          {busy ? 'Создаём…' : 'Создать аккаунт'}
        </button>
      </form>

      <p className="mt-4 text-center text-sm text-gray-600">
        Уже есть аккаунт?{' '}
        <Link to="/login" className="font-semibold text-accent-strong">
          Войти
        </Link>
      </p>
    </div>
  )
}
