import { useEffect, useState } from 'react'
import { Link, NavLink, Route, Routes, useNavigate } from 'react-router-dom'
import { fetchStoreInfo } from './api.js'
import { useAuth } from './auth.jsx'
import AdminPage from './pages/AdminPage.jsx'
import CabinetPage from './pages/CabinetPage.jsx'
import LoginPage from './pages/LoginPage.jsx'
import RegisterPage from './pages/RegisterPage.jsx'
import StorefrontPage from './pages/StorefrontPage.jsx'

function StoreLogo({ name }) {
  return (
    <span
      aria-hidden="true"
      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-gradient-to-br from-accent-strong to-accent-deep text-xl shadow-sm"
    >
      <span className="text-white">🚗</span>
    </span>
  )
}

function Header() {
  const { user, isOwner, signOut } = useAuth()
  const navigate = useNavigate()
  const [store, setStore] = useState(null)

  useEffect(() => {
    let alive = true
    fetchStoreInfo()
      .then((data) => {
        if (alive) setStore(data)
      })
      .catch(() => {
        if (alive) setStore(null)
      })
    return () => {
      alive = false
    }
  }, [])

  const linkClass = ({ isActive }) =>
    `rounded-lg px-3 py-1.5 text-sm font-medium transition ${
      isActive
        ? 'bg-accent-soft text-accent-strong'
        : 'text-gray-600 hover:bg-gray-50'
    }`

  const phoneHref = store?.phone_href ?? 'tel:+79610108001'
  const phoneText = store?.phone ?? '+7 (961) 010-80-01'
  const address = store?.address ?? 'ул. Высоковольтная, 49, Рязань'
  const mapsUrl = store?.maps_url ?? 'https://yandex.ru/maps/org/avtodom/56955083106/'
  const openHour = store?.open_hour ?? 8
  const closeHour = store?.close_hour ?? 20

  return (
    <header className="sticky top-0 z-20 border-b border-gray-200 bg-white/95 backdrop-blur">
      {/* Верхняя полоса — контакты */}
      <div className="hidden bg-gray-900 text-gray-300 md:block">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-4 py-1.5 text-xs sm:px-6">
          <div className="flex items-center gap-4">
            <a
              href={phoneHref}
              data-testid="header-phone"
              className="flex items-center gap-1.5 transition hover:text-white focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 focus:ring-offset-gray-900"
            >
              <span aria-hidden="true">📞</span>
              <span className="font-medium">{phoneText}</span>
            </a>
            <a
              href={mapsUrl}
              target="_blank"
              rel="noreferrer"
              data-testid="header-address"
              className="flex items-center gap-1.5 transition hover:text-white focus:outline-none focus:ring-2 focus:ring-orange-500 focus:ring-offset-2 focus:ring-offset-gray-900"
            >
              <span aria-hidden="true">📍</span>
              <span>{address}</span>
            </a>
          </div>
          <div className="flex items-center gap-4">
            {store?.rating ? (
              <span data-testid="header-rating" className="flex items-center gap-1">
                <span aria-hidden="true" className="text-amber-400">
                  ★
                </span>
                {store.rating}
                {store.rating_count ? (
                  <span className="text-gray-500">({store.rating_count})</span>
                ) : null}
              </span>
            ) : null}
            <span
              data-testid="store-hours"
              className="flex items-center gap-1.5"
              title="Магазин работает ежедневно с 8:00 до 20:00"
            >
              <span
                className={`h-1.5 w-1.5 rounded-full ${
                  store?.is_open ? 'bg-emerald-400' : 'bg-gray-500'
                }`}
              />
              {String(openHour).padStart(2, '0')}:00–
              {String(closeHour).padStart(2, '0')}:00
            </span>
          </div>
        </div>
      </div>

      {/* Основная строка */}
      <div className="mx-auto flex max-w-5xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <StoreLogo />
          <div className="min-w-0">
            <Link
              to="/"
              data-testid="header-store-name"
              className="block truncate text-lg font-bold leading-tight text-gray-900 transition hover:text-accent-strong focus:outline-none focus:ring-2 focus:ring-orange-500"
            >
              {store?.name ?? 'Автодом'}
            </Link>
            <span className="block truncate text-xs text-gray-500">
              Запчасти для вашего авто · Рязань
            </span>
          </div>
          <nav className="ml-4 hidden items-center gap-1 sm:flex">
            <NavLink to="/" end className={linkClass}>
              Витрина
            </NavLink>
            {user ? (
              <NavLink to="/cabinet" className={linkClass}>
                Мои заказы
              </NavLink>
            ) : null}
            {isOwner ? (
              <NavLink to="/admin" className={linkClass}>
                Кабинет владельца
              </NavLink>
            ) : null}
          </nav>
        </div>

        <div className="flex shrink-0 items-center gap-2">
          {/* На телефоне контакты видны прямо в шапке */}
          <a
            href={phoneHref}
            data-testid="header-phone-mobile"
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-soft text-accent-strong transition hover:bg-orange-100 md:hidden"
            aria-label={`Позвонить ${phoneText}`}
          >
            <span aria-hidden="true">📞</span>
          </a>
          <a
            href={mapsUrl}
            target="_blank"
            rel="noreferrer"
            data-testid="header-address-mobile"
            className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent-soft text-accent-strong transition hover:bg-orange-100 md:hidden"
            aria-label={`Открыть ${address} на карте`}
          >
            <span aria-hidden="true">📍</span>
          </a>
          {user ? (
            <div className="flex items-center gap-2">
              <span
                data-testid="current-user"
                className="hidden text-sm text-gray-600 lg:inline"
              >
                {user.full_name || user.email}
              </span>
              <button
                type="button"
                data-testid="logout-button"
                onClick={async () => {
                  await signOut()
                  navigate('/')
                }}
                className="btn-secondary"
              >
                Выйти
              </button>
            </div>
          ) : (
            <Link to="/login" className="btn-secondary">
              Войти
            </Link>
          )}
        </div>
      </div>

      {/* Мобильная навигация */}
      <nav className="flex items-center gap-1 border-t border-gray-100 px-4 py-2 sm:hidden">
        <NavLink to="/" end className={linkClass}>
          Витрина
        </NavLink>
        {user ? (
          <NavLink to="/cabinet" className={linkClass}>
            Мои заказы
          </NavLink>
        ) : null}
        {isOwner ? (
          <NavLink to="/admin" className={linkClass}>
            Кабинет владельца
          </NavLink>
        ) : null}
      </nav>
    </header>
  )
}

function RequireAuth({ children, ownerOnly = false }) {
  const { user, loading } = useAuth()
  const navigate = useNavigate()

  if (loading) {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center text-sm text-gray-400">
        Загружаем…
      </div>
    )
  }
  if (!user) {
    navigate('/login', { replace: true, state: { from: ownerOnly ? '/admin' : '/cabinet' } })
    return null
  }
  if (ownerOnly && user.role !== 'owner') {
    return (
      <div className="mx-auto max-w-md px-4 py-16 text-center">
        <p className="text-sm text-gray-600">
          Раздел доступен только владельцу магазина.
        </p>
      </div>
    )
  }
  return children
}

export default function App() {
  return (
    <div className="min-h-screen bg-gray-50">
      <Header />
      <Routes>
        <Route path="/" element={<StorefrontPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route
          path="/cabinet"
          element={
            <RequireAuth>
              <CabinetPage />
            </RequireAuth>
          }
        />
        <Route
          path="/admin"
          element={
            <RequireAuth ownerOnly>
              <AdminPage />
            </RequireAuth>
          }
        />
        <Route
          path="*"
          element={
            <div className="mx-auto max-w-md px-4 py-16 text-center">
              <p className="text-lg font-semibold text-gray-900">Страница не найдена</p>
              <Link to="/" className="btn-primary mt-4">
                На витрину
              </Link>
            </div>
          }
        />
      </Routes>
    </div>
  )
}
