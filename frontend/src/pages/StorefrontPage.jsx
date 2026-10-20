import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { fetchHealth, fetchProducts, fetchStoreInfo, submitOrder } from '../api.js'
import { useAuth } from '../auth.jsx'
import CartBar from '../components/CartBar.jsx'
import CheckoutSheet from '../components/CheckoutSheet.jsx'
import ProductCard, { SORTS, sortProducts } from '../components/ProductCard.jsx'
import ProductSkeleton from '../components/ProductSkeleton.jsx'
import { formatPrice, pluralItems } from '../lib/format.js'
import { clearCart, loadCart, saveCart } from '../storage.js'

// Нормализация для поиска: без пробелов и тире, в нижнем регистре.
function normalize(value) {
  return (value ?? '')
    .toLowerCase()
    .replace(/[^a-zа-яё0-9]/gi, '')
}

function matchesQuery(product, query) {
  if (!query) return true
  const needle = normalize(query)
  if (!needle) return true
  return [product.name, product.brand, product.sku, product.category, product.description]
    .map(normalize)
    .some((value) => value.includes(needle))
}

export default function StorefrontPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [cart, setCart] = useState(() => loadCart())
  const [checkoutOpen, setCheckoutOpen] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  const [submitError, setSubmitError] = useState('')
  const [success, setSuccess] = useState(null)
  const [health, setHealth] = useState(null)
  const [store, setStore] = useState(null)
  const [stockFilter, setStockFilter] = useState('all')
  const [query, setQuery] = useState('')
  const [category, setCategory] = useState('')
  const [brand, setBrand] = useState('')
  const [sort, setSort] = useState('popular')
  const [filtersOpen, setFiltersOpen] = useState(false)

  const loadProducts = useCallback(async () => {
    setLoading(true)
    setLoadError('')
    try {
      setProducts(await fetchProducts())
    } catch (error) {
      setLoadError(error.message || 'Не удалось загрузить каталог')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    loadProducts()
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
    fetchStoreInfo()
      .then(setStore)
      .catch(() => setStore(null))
  }, [loadProducts])

  // Корзина живёт в localStorage — перезагрузка страницы её не сбрасывает.
  const updateCart = useCallback((updater) => {
    setCart((prev) => {
      const next = typeof updater === 'function' ? updater(prev) : updater
      saveCart(next)
      return next
    })
  }, [])

  const addToCart = (id) =>
    updateCart((prev) => ({ ...prev, [id]: (prev[id] ?? 0) + 1 }))

  const increment = (id) =>
    updateCart((prev) => ({ ...prev, [id]: (prev[id] ?? 0) + 1 }))

  const decrement = (id) =>
    updateCart((prev) => {
      const next = { ...prev }
      const value = (next[id] ?? 0) - 1
      if (value <= 0) delete next[id]
      else next[id] = value
      return next
    })

  const cartItems = useMemo(
    () =>
      Object.entries(cart)
        .map(([id, qty]) => {
          const product = products.find((item) => item.id === Number(id))
          return product ? { ...product, qty } : null
        })
        .filter(Boolean),
    [cart, products],
  )

  const total = useMemo(
    () => cartItems.reduce((sum, item) => sum + Number(item.price) * item.qty, 0),
    [cartItems],
  )

  const onOrderCount = useMemo(
    () =>
      products.filter((item) => item.is_on_order && !item.in_stock).length,
    [products],
  )

  // Все доступные категории и бренды — из загруженного каталога.
  const categories = useMemo(() => {
    const map = new Map()
    products.forEach((item) => {
      if (!item.category) return
      map.set(item.category, (map.get(item.category) ?? 0) + 1)
    })
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0], 'ru'))
  }, [products])

  const brands = useMemo(() => {
    const set = new Set()
    products.forEach((item) => {
      if (item.brand) set.add(item.brand)
    })
    return [...set].sort((a, b) => a.localeCompare(b, 'ru'))
  }, [products])

  // Фильтры: наличие → поиск → категория → бренд, затем сортировка.
  const visibleProducts = useMemo(() => {
    let list = products
    if (stockFilter === 'stock') {
      list = list.filter((item) => item.in_stock)
    } else if (stockFilter === 'order') {
      list = list.filter((item) => item.is_on_order && !item.in_stock)
    }
    if (query.trim()) {
      list = list.filter((item) => matchesQuery(item, query))
    }
    if (category) {
      list = list.filter((item) => item.category === category)
    }
    if (brand) {
      list = list.filter((item) => item.brand === brand)
    }
    return sortProducts(list, sort)
  }, [products, stockFilter, query, category, brand, sort])

  const activeFilters =
    (query.trim() ? 1 : 0) +
    (category ? 1 : 0) +
    (brand ? 1 : 0) +
    (stockFilter !== 'all' ? 1 : 0)

  const resetFilters = () => {
    setQuery('')
    setCategory('')
    setBrand('')
    setStockFilter('all')
  }

  const count = cartItems.reduce((sum, item) => sum + item.qty, 0)

  const handleSubmit = async (payload) => {
    setSubmitting(true)
    setSubmitError('')
    try {
      const order = await submitOrder(payload)
      setSuccess(order)
      setCheckoutOpen(false)
      updateCart({})
      clearCart()
      if (user) navigate('/cabinet')
    } catch (error) {
      setSubmitError(error.message || 'Не удалось оформить заказ')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-32">
      <main className="mx-auto max-w-3xl px-4 py-5 sm:px-6">
        {success ? (
          <div
            data-testid="success-banner"
            className="card mb-5 border border-green-200 bg-green-50 p-4"
          >
            <h2 className="text-base font-bold text-green-800">
              Заказ {success.order_number} принят
            </h2>
            <p className="mt-1 text-sm text-green-700">
              Сумма {formatPrice(success.total)} · менеджер получит заявку в
              Telegram и свяжется с вами.
              {success.is_night_order
                ? ' Заказ ночной — ответим в приоритетном порядке.'
                : ''}
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {user ? (
                <button
                  type="button"
                  data-testid="go-to-cabinet"
                  onClick={() => navigate('/cabinet')}
                  className="btn-secondary"
                >
                  Отследить заказ
                </button>
              ) : (
                <button
                  type="button"
                  data-testid="go-to-login"
                  onClick={() => navigate('/login')}
                  className="btn-secondary"
                >
                  Войти, чтобы отслеживать заказ
                </button>
              )}
            </div>
          </div>
        ) : null}

        {loadError ? (
          <div className="card mb-5 border border-red-200 bg-red-50 p-4">
            <p className="text-sm font-medium text-red-700">{loadError}</p>
            <button
              type="button"
              onClick={loadProducts}
              className="btn-secondary mt-3"
            >
              Повторить
            </button>
          </div>
        ) : null}

        <section aria-label="Каталог автозапчастей">
          <div className="mb-3 flex items-baseline justify-between gap-3">
            <h2 className="text-base font-semibold text-gray-900">Каталог</h2>
            {!loading && visibleProducts.length > 0 ? (
              <p className="text-sm text-gray-500">
                {pluralItems(visibleProducts.length)}
              </p>
            ) : null}
          </div>

          {/* Поиск и сортировка */}
          <div className="mb-3 flex flex-col gap-2 sm:flex-row">
            <div className="relative flex-1">
              <span
                aria-hidden="true"
                className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"
              >
                🔍
              </span>
              <input
                type="search"
                data-testid="catalog-search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Поиск по названию, бренду или артикулу…"
                aria-label="Поиск по каталогу"
                className="field pl-10"
              />
              {query ? (
                <button
                  type="button"
                  onClick={() => setQuery('')}
                  aria-label="Очистить поиск"
                  className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
                >
                  ✕
                </button>
              ) : null}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                data-testid="catalog-filters-toggle"
                onClick={() => setFiltersOpen((value) => !value)}
                className={`relative flex items-center gap-1.5 rounded-xl border px-3.5 py-3 text-sm font-medium transition ${
                  filtersOpen || activeFilters
                    ? 'border-accent bg-accent-soft text-accent-strong'
                    : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                }`}
              >
                <span aria-hidden="true">⚙</span>
                <span className="hidden sm:inline">Фильтры</span>
                {activeFilters ? (
                  <span
                    data-testid="catalog-filters-count"
                    className="flex h-5 min-w-5 items-center justify-center rounded-full bg-accent-strong px-1 text-[11px] font-bold text-white"
                  >
                    {activeFilters}
                  </span>
                ) : null}
              </button>
              <select
                data-testid="catalog-sort"
                value={sort}
                onChange={(event) => setSort(event.target.value)}
                aria-label="Сортировка"
                className="field w-auto min-w-[9.5rem] py-3"
              >
                {SORTS.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.title}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {/* Расширенные фильтры */}
          {filtersOpen ? (
            <div
              data-testid="catalog-filters"
              className="card mb-3 space-y-3 p-4"
            >
              <div>
                <p className="label">Наличие</p>
                <div className="flex flex-wrap gap-1.5">
                  {[
                    ['all', 'Все детали'],
                    ['stock', 'В наличии'],
                    ['order', 'Под заказ'],
                  ].map(([id, title]) => (
                    <button
                      key={id}
                      type="button"
                      data-testid={`catalog-filter-${id}`}
                      onClick={() => setStockFilter(id)}
                      className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                        stockFilter === id
                          ? 'bg-accent-strong text-white'
                          : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                      }`}
                    >
                      {title}
                      {id === 'order' && onOrderCount ? (
                        <span className="ml-1.5 opacity-80">({onOrderCount})</span>
                      ) : null}
                    </button>
                  ))}
                </div>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="label" htmlFor="catalog-category">
                    Категория
                  </label>
                  <select
                    id="catalog-category"
                    data-testid="catalog-category"
                    value={category}
                    onChange={(event) => setCategory(event.target.value)}
                    className="field"
                  >
                    <option value="">Все категории</option>
                    {categories.map(([name, amount]) => (
                      <option key={name} value={name}>
                        {name} ({amount})
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label" htmlFor="catalog-brand">
                    Бренд
                  </label>
                  <select
                    id="catalog-brand"
                    data-testid="catalog-brand"
                    value={brand}
                    onChange={(event) => setBrand(event.target.value)}
                    className="field"
                  >
                    <option value="">Все бренды</option>
                    {brands.map((name) => (
                      <option key={name} value={name}>
                        {name}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {activeFilters ? (
                <button
                  type="button"
                  data-testid="catalog-filters-reset"
                  onClick={resetFilters}
                  className="text-xs font-semibold text-accent-strong hover:underline"
                >
                  Сбросить фильтры
                </button>
              ) : null}
            </div>
          ) : null}

          {/* Категории быстрыми чипами */}
          {categories.length > 1 ? (
            <div className="mb-3 flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => setCategory('')}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  category === ''
                    ? 'bg-accent-strong text-white'
                    : 'bg-white text-gray-600 shadow-card hover:bg-gray-50'
                }`}
              >
                Все
              </button>
              {categories.map(([name, amount]) => (
                <button
                  key={name}
                  type="button"
                  data-testid={`catalog-chip-${name}`}
                  onClick={() => setCategory(category === name ? '' : name)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    category === name
                      ? 'bg-accent-strong text-white'
                      : 'bg-white text-gray-600 shadow-card hover:bg-gray-50'
                  }`}
                >
                  {name}
                  <span className="ml-1.5 opacity-70">{amount}</span>
                </button>
              ))}
            </div>
          ) : null}

          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {loading
              ? Array.from({ length: 6 }).map((_, index) => (
                  <ProductSkeleton key={index} />
                ))
              : visibleProducts.map((product) => (
                  <ProductCard
                    key={product.id}
                    product={product}
                    qty={cart[product.id] ?? 0}
                    onAdd={addToCart}
                    onIncrement={increment}
                    onDecrement={decrement}
                  />
                ))}
          </div>

          {!loading && visibleProducts.length === 0 && !loadError ? (
            <div className="card p-8 text-center">
              <p className="text-4xl">🔍</p>
              <p className="mt-2 text-sm font-semibold text-gray-900">
                Ничего не нашлось
              </p>
              <p className="mt-1 text-sm text-gray-500">
                {query.trim()
                  ? `По запросу «${query.trim()}» деталей нет. Попробуйте другое слово или сбросьте фильтры.`
                  : 'Под текущие фильтры не подходит ни одна деталь. Сбросьте фильтры, чтобы увидеть весь каталог.'}
              </p>
              {activeFilters ? (
                <button
                  type="button"
                  onClick={resetFilters}
                  className="btn-secondary mt-4"
                >
                  Сбросить фильтры
                </button>
              ) : null}
            </div>
          ) : null}
        </section>

        {health ? (
          <p className="mt-6 text-center text-xs text-gray-400">
            API: {health.database === 'ok' ? 'БД подключена' : health.database} ·
            Telegram: {health.telegram}
          </p>
        ) : null}

        {/* Контакты — на мобильных дублируют шапку, чтобы не искать */}
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <a
            href={store?.phone_href ?? 'tel:+79610108001'}
            data-testid="store-contact-phone"
            className="card flex items-center gap-3 p-4 transition hover:shadow-md focus:outline-none focus:ring-2 focus:ring-orange-500"
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-lg">
              📞
            </span>
            <span className="min-w-0">
              <span className="block text-xs font-medium uppercase tracking-wide text-gray-400">
                Позвоните нам
              </span>
              <span className="block truncate font-semibold text-gray-900">
                {store?.phone ?? '+7 (961) 010-80-01'}
              </span>
            </span>
          </a>
          <a
            href={store?.maps_url ?? 'https://yandex.ru/maps/org/avtodom/56955083106/'}
            target="_blank"
            rel="noreferrer"
            data-testid="store-contact-address"
            className="card flex items-center gap-3 p-4 transition hover:shadow-md focus:outline-none focus:ring-2 focus:ring-orange-500"
          >
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-lg">
              📍
            </span>
            <span className="min-w-0">
              <span className="block text-xs font-medium uppercase tracking-wide text-gray-400">
                Мы находимся
              </span>
              <span className="block truncate font-semibold text-gray-900">
                {store?.address ?? 'ул. Высоковольтная, 49, Рязань'}
              </span>
              <span className="block text-xs text-gray-400">
                Открыть в Яндекс.Картах
              </span>
            </span>
          </a>
        </div>
      </main>

      <CartBar
        total={total}
        count={count}
        disabled={count === 0}
        onCheckout={() => {
          setSubmitError('')
          setCheckoutOpen(true)
        }}
      />

      <CheckoutSheet
        open={checkoutOpen}
        items={cartItems}
        total={total}
        user={user}
        submitting={submitting}
        error={submitError}
        onClose={() => setCheckoutOpen(false)}
        onSubmit={handleSubmit}
      />
    </div>
  )
}
