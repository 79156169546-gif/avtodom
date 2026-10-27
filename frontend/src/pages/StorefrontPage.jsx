import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  fetchCarMakes,
  fetchCarModels,
  fetchCarVin,
  fetchHealth,
  fetchOrderTelegramLink,
  fetchProducts,
  fetchStoreInfo,
  submitOrder,
} from '../api.js'
import { useAuth } from '../auth.jsx'
import storeConfig from '../config.js'
import CarPicker from '../components/CarPicker.jsx'
import CartBar from '../components/CartBar.jsx'
import CheckoutSheet from '../components/CheckoutSheet.jsx'
import FilterPanel from '../components/FilterPanel.jsx'
import ProductCard, { SORTS, sortProducts } from '../components/ProductCard.jsx'
import ProductSkeleton from '../components/ProductSkeleton.jsx'
import {
  IconCar,
  IconClose,
  IconSearch,
  IconSliders,
  categoryIcon,
} from '../components/icons.jsx'
import { formatPrice, pluralItems } from '../lib/format.js'
import {
  SEARCH_MODES,
  fitsCar,
  matchesQuery,
  priceBounds,
} from '../lib/catalog.js'
import { clearCart, loadCart, saveCart } from '../storage.js'

// Сколько карточек показываем за раз.
const PAGE_SIZE = 24

// Выбранный автомобиль хранится в localStorage — клиент не выбирает его заново.
const CAR_KEY = 'autodom.car'

function loadCar() {
  try {
    const raw = localStorage.getItem(CAR_KEY)
    if (!raw) return { make: '', model: '', year: '' }
    const parsed = JSON.parse(raw)
    return {
      make: parsed?.make ?? '',
      model: parsed?.model ?? '',
      year: parsed?.year ?? '',
    }
  } catch {
    return { make: '', model: '', year: '' }
  }
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
  // Ссылка-подписка на уведомления в Telegram для свежего заказа.
  const [telegramLink, setTelegramLink] = useState(null)
  const [health, setHealth] = useState(null)
  const [store, setStore] = useState(null)

  // Поиск
  const [query, setQuery] = useState('')
  const [searchMode, setSearchMode] = useState('name')
  const [vinInfo, setVinInfo] = useState(null)

  // Фильтры
  const [car, setCar] = useState(() => loadCar())
  const [category, setCategory] = useState('')
  const [brands, setBrands] = useState([])
  const [catalogMakes, setCatalogMakes] = useState([])
  const [selectedMakes, setSelectedMakes] = useState([])
  const [models, setModels] = useState([])
  const [selectedModels, setSelectedModels] = useState([])
  // Показываем товары порциями: каталог большой, а 80 карточек подряд
  // клиента перегружают.
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE)
  const [price, setPrice] = useState({ min: 0, max: 0 })
  const [inStockOnly, setInStockOnly] = useState(false)
  const [onOrderOnly, setOnOrderOnly] = useState(false)
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
    // Справочник марок для фильтра в левой колонке.
    fetchCarMakes('', 40)
      .then((data) => setCatalogMakes(data?.makes ?? []))
      .catch(() => setCatalogMakes([]))
    fetchHealth()
      .then(setHealth)
      .catch(() => setHealth(null))
    fetchStoreInfo()
      .then(setStore)
      .catch(() => setStore(null))
  }, [loadProducts])

  // Модели в фильтре зависят от выбранных марок: показываем модели
  // всех выбранных марок, иначе — ничего.
  useEffect(() => {
    if (selectedMakes.length === 0) {
      setModels([])
      return undefined
    }
    let cancelled = false
    Promise.all(
      selectedMakes.map((make) =>
        fetchCarModels(make, '').catch(() => ({ models: [] })),
      ),
    ).then((responses) => {
      if (cancelled) return
      const names = new Set()
      responses.forEach((response) => {
        ;(response?.models ?? []).forEach((name) => names.add(name))
      })
      // Счётчика по моделям нет — отдаём null, чтобы панель не показывала «0».
      setModels(
        [...names].sort((a, b) => a.localeCompare(b, 'ru')).map((n) => [n, null]),
      )
    })
    return () => {
      cancelled = true
    }
  }, [selectedMakes])

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

  // Все доступные категории и бренды — из загруженного каталога.
  const categories = useMemo(() => {
    const map = new Map()
    products.forEach((item) => {
      if (!item.category) return
      map.set(item.category, (map.get(item.category) ?? 0) + 1)
    })
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0], 'ru'))
  }, [products])

  // Марки для фильтра: из справочника, но счётчик — реальное число
  // деталей в каталоге, совместимых с этой маркой.
  const makeList = useMemo(() => {
    const counts = new Map()
    products.forEach((item) => {
      const marks = new Set(
        (item.compatibility ?? []).map((fit) => (fit.make ?? '').toUpperCase()),
      )
      marks.forEach((mark) => {
        if (mark) counts.set(mark, (counts.get(mark) ?? 0) + 1)
      })
    })
    const catalog = catalogMakes
    if (catalog.length === 0) {
      return [...counts.entries()].sort((a, b) => a[0].localeCompare(b[0], 'ru'))
    }
    return catalog.map((name) => [name, counts.get(name) ?? 0])
  }, [products, catalogMakes])

  const brandList = useMemo(() => {
    const map = new Map()
    products.forEach((item) => {
      if (!item.brand) return
      map.set(item.brand, (map.get(item.brand) ?? 0) + 1)
    })
    return [...map.entries()].sort((a, b) => a[0].localeCompare(b[0], 'ru'))
  }, [products])

  // Границы слайдера цены — по всему каталогу, а не по отфильтрованному.
  const bounds = useMemo(() => priceBounds(products), [products])

  useEffect(() => {
    setPrice((prev) => ({
      min: Math.min(prev.min || bounds.min, bounds.max),
      max: Math.max(prev.max || bounds.max, bounds.min),
    }))
  }, [bounds])

  // VIN разбираем на сервере: он знает WMI-префиксы и коды годов.
  useEffect(() => {
    const value = query.trim()
    if (searchMode !== 'vin' || !value) {
      setVinInfo(null)
      return undefined
    }
    if (value.length !== 17) {
      setVinInfo({
        valid: false,
        reason: `VIN состоит из 17 символов — введено ${value.length}.`,
        make: null,
        year: null,
      })
      return undefined
    }
    let cancelled = false
    fetchCarVin(value)
      .then((data) => {
        if (!cancelled) setVinInfo(data)
      })
      .catch(() => setVinInfo(null))
    return () => {
      cancelled = true
    }
  }, [query, searchMode])

  // Фильтры: авто -> поиск -> категория -> бренд -> цена -> наличие.
  const visibleProducts = useMemo(() => {
    let list = products

    // Авто для подбора: выбор пользователя + уточнение по VIN.
    // VIN точнее, поэтому он задаёт марку и год; модель берём из выбора,
    // но только если она из той же марки.
    const vinCar =
      vinInfo?.valid && vinInfo.make
        ? { make: vinInfo.make, year: vinInfo.year ?? '' }
        : null
    const effectiveCar = {
      make: vinCar?.make || car.make,
      model:
        vinCar && car.make && car.make !== vinCar.make
          ? ''
          : car.model,
      year: vinCar?.year || car.year,
    }

    if (effectiveCar.make || effectiveCar.model || effectiveCar.year) {
      list = list.filter((item) => fitsCar(item.compatibility, effectiveCar))
    }

    if (query.trim() && searchMode !== 'vin') {
      list = list.filter((item) => matchesQuery(item, query, searchMode))
    }
    if (category) {
      list = list.filter((item) => item.category === category)
    }
    if (selectedMakes.length > 0) {
      list = list.filter((item) =>
        (item.compatibility ?? []).some((fit) =>
          selectedMakes.includes((fit.make ?? '').toUpperCase()),
        ),
      )
    }
    if (selectedModels.length > 0) {
      list = list.filter((item) =>
        (item.compatibility ?? []).some(
          (fit) =>
            selectedModels.includes(fit.model ?? '') &&
            (selectedMakes.length === 0 ||
              selectedMakes.includes((fit.make ?? '').toUpperCase())),
        ),
      )
    }
    if (brands.length > 0) {
      list = list.filter((item) => brands.includes(item.brand))
    }
    if (price.min > bounds.min || price.max < bounds.max) {
      list = list.filter((item) => {
        const value = Number(item.price)
        return value >= price.min && value <= price.max
      })
    }
    // «В наличии» и «Под заказ» — это одно измерение, поэтому включаются
    // вместе через ИЛИ: оба флага = показать и те, и другие детали.
    if (inStockOnly || onOrderOnly) {
      list = list.filter(
        (item) =>
          (inStockOnly && item.in_stock) ||
          (onOrderOnly && item.is_on_order && !item.in_stock),
      )
    }
    return sortProducts(list, sort)
  }, [
    products,
    car,
    vinInfo,
    query,
    searchMode,
    category,
    selectedMakes,
    selectedModels,
    brands,
    price,
    bounds,
    inStockOnly,
    onOrderOnly,
    sort,
  ])

  const activeFilters =
    (query.trim() ? 1 : 0) +
    (category ? 1 : 0) +
    (selectedMakes.length ? 1 : 0) +
    (selectedModels.length ? 1 : 0) +
    (brands.length ? 1 : 0) +
    (inStockOnly ? 1 : 0) +
    (onOrderOnly ? 1 : 0) +
    (price.min > bounds.min || price.max < bounds.max ? 1 : 0) +
    (car.make || car.model || car.year ? 1 : 0)

  const resetFilters = () => {
    setQuery('')
    setCategory('')
    setBrands([])
    setSelectedMakes([])
    setSelectedModels([])
    setInStockOnly(false)
    setOnOrderOnly(false)
    setPrice({ min: bounds.min, max: bounds.max })
    setVinInfo(null)
  }

  const resetCar = () => {
    const cleared = { make: '', model: '', year: '' }
    try {
      localStorage.removeItem(CAR_KEY)
    } catch {
      /* игнор */
    }
    setCar(cleared)
  }

  // Смена фильтров возвращает список к первой странице.
  useEffect(() => {
    setVisibleCount(PAGE_SIZE)
  }, [
    query,
    searchMode,
    category,
    selectedMakes,
    selectedModels,
    brands,
    price.min,
    price.max,
    inStockOnly,
    onOrderOnly,
    sort,
    car,
    vinInfo,
  ])

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

  const activeMode = SEARCH_MODES.find((mode) => mode.id === searchMode)

  // Порция каталога для показа.
  const pagedProducts = useMemo(
    () => visibleProducts.slice(0, visibleCount),
    [visibleProducts, visibleCount],
  )

  const filterPanelProps = {
    makes: makeList,
    selectedMakes,
    onMakesChange: setSelectedMakes,
    models,
    selectedModels,
    onModelsChange: setSelectedModels,
    brands: brandList,
    selectedBrands: brands,
    onBrandsChange: setBrands,
    price,
    onPriceChange: setPrice,
    bounds,
    inStockOnly,
    onInStockChange: setInStockOnly,
    onOrderOnly,
    onOnOrderChange: setOnOrderOnly,
    onReset: resetFilters,
    activeCount: activeFilters,
  }

  return (
    <div className="min-h-screen bg-gray-50 pb-32">
      <main className="mx-auto max-w-6xl px-4 py-5 sm:px-6">
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
              {telegramLink?.link ? (
                <a
                  href={telegramLink.link}
                  target="_blank"
                  rel="noreferrer"
                  data-testid="telegram-subscribe"
                  className="btn-secondary"
                >
                  Получать уведомления в Telegram
                </a>
              ) : null}
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

        {/* --- Верхняя панель: умный поиск и авто --- */}
        <section aria-label="Каталог автозапчастей" className="space-y-3">
          <CarPicker car={car} onChange={setCar} />

          {/* Поиск с табами */}
          <div className="card p-3">
            <div
              role="tablist"
              aria-label="Режим поиска"
              className="mb-2.5 flex gap-1 overflow-x-auto"
            >
              {SEARCH_MODES.map((mode) => (
                <button
                  key={mode.id}
                  type="button"
                  role="tab"
                  aria-selected={searchMode === mode.id}
                  data-testid={`catalog-search-mode-${mode.id}`}
                  onClick={() => setSearchMode(mode.id)}
                  className={`shrink-0 rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    searchMode === mode.id
                      ? 'bg-accent-strong text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {mode.title}
                </button>
              ))}
            </div>

            <div className="flex flex-col gap-2 sm:flex-row">
              <div className="relative flex-1">
                <span
                  aria-hidden="true"
                  className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"
                >
                  <IconSearch className="h-4 w-4" />
                </span>
                <input
                  type="search"
                  data-testid="catalog-search"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder={activeMode?.placeholder ?? ''}
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
                    <IconClose className="h-4 w-4" />
                  </button>
                ) : null}
              </div>
              <div className="flex gap-2">
                <button
                  type="button"
                  data-testid="catalog-filters-toggle"
                  onClick={() => setFiltersOpen((value) => !value)}
                  className={`relative flex items-center gap-1.5 rounded-xl border px-3.5 py-3 text-sm font-medium transition lg:hidden ${
                    filtersOpen || activeFilters
                      ? 'border-accent bg-accent-soft text-accent-strong'
                      : 'border-gray-200 bg-white text-gray-700 hover:bg-gray-50'
                  }`}
                >
                  <IconSliders className="h-4 w-4" />
                  <span>Фильтры</span>
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

            {searchMode === 'vin' && vinInfo ? (
              <p
                data-testid="catalog-vin-hint"
                className="mt-2.5 text-xs text-gray-500"
              >
                {vinInfo.valid ? (
                  vinInfo.make ? (
                    <>
                      VIN: {vinInfo.make}
                      {vinInfo.year ? `, ${vinInfo.year} г.` : ''} — показываем
                      совместимые детали.
                    </>
                  ) : (
                    vinInfo.reason
                  )
                ) : (
                  <span className="text-red-600">{vinInfo.reason}</span>
                )}
              </p>
            ) : null}
          </div>

          {/* Категории — горизонтальная панель с иконками */}
          {categories.length > 1 ? (
            <div
              data-testid="catalog-categories"
              className="flex gap-2 overflow-x-auto pb-1"
            >
              <button
                type="button"
                onClick={() => setCategory('')}
                className={`flex shrink-0 flex-col items-center gap-1 rounded-xl px-3 py-2 text-[11px] font-semibold transition ${
                  category === ''
                    ? 'bg-accent-strong text-white'
                    : 'card text-gray-600 hover:bg-gray-50'
                }`}
              >
                <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-soft text-accent-strong">
                  <IconCar className="h-4 w-4" />
                </span>
                <span>Все</span>
              </button>
              {categories.map(([name, amount]) => {
                const Icon = categoryIcon(name)
                const active = category === name
                return (
                  <button
                    key={name}
                    type="button"
                    data-testid={`catalog-chip-${name}`}
                    onClick={() => setCategory(active ? '' : name)}
                    className={`flex shrink-0 flex-col items-center gap-1 rounded-xl px-3 py-2 text-[11px] font-semibold transition ${
                      active
                        ? 'bg-accent-strong text-white'
                        : 'card text-gray-600 hover:bg-gray-50'
                    }`}
                  >
                    <span
                      className={`flex h-8 w-8 items-center justify-center rounded-lg ${
                        active
                          ? 'bg-white/20 text-white'
                          : 'bg-accent-soft text-accent-strong'
                      }`}
                    >
                      <Icon className="h-4 w-4" />
                    </span>
                    <span className="whitespace-nowrap">{name}</span>
                    <span className={active ? 'text-white/70' : 'text-gray-400'}>
                      {amount}
                    </span>
                  </button>
                )
              })}
            </div>
          ) : null}
        </section>

        {/* --- Двухколоночная раскладка: фильтры слева, товары справа --- */}
        <div className="mt-4 flex gap-5">
          {/* Фильтры на десктопе */}
          <aside className="hidden w-[250px] shrink-0 lg:block">
            <div className="sticky top-4 space-y-3">
              <FilterPanel {...filterPanelProps} />
              {car.make ? (
                <button
                  type="button"
                  data-testid="car-filter-reset"
                  onClick={resetCar}
                  className="card flex w-full items-center gap-2 p-3 text-left text-xs font-semibold text-gray-600 transition hover:bg-gray-50"
                >
                  <IconClose className="h-4 w-4 shrink-0 text-gray-400" />
                  Сбросить выбор автомобиля
                </button>
              ) : null}
            </div>
          </aside>

          {/* Сетка товаров */}
          <div className="min-w-0 flex-1">
            <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
              <h2 className="text-base font-semibold text-gray-900">Каталог</h2>
              {!loading && visibleProducts.length > 0 ? (
                <p data-testid="catalog-count" className="text-sm text-gray-500">
                  {pluralItems(visibleProducts.length)}
                </p>
              ) : null}
              {selectedMakes.length > 0 ? (
                <p
                  data-testid="catalog-make-filter"
                  className="text-xs text-gray-500"
                >
                  Марки: {selectedMakes.join(', ')}
                </p>
              ) : null}
            </div>

            {car.make ? (
              <p
                data-testid="catalog-car-filter"
                className="mb-3 flex items-center gap-1.5 text-xs text-gray-500"
              >
                <IconCar className="h-3.5 w-3.5 text-gray-400" />
                Подбор по авто: {car.make} {car.model} {car.year}
              </p>
            ) : null}

            <div
              data-testid="catalog-grid"
              className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3"
            >
              {loading
                ? Array.from({ length: 6 }).map((_, index) => (
                    <ProductSkeleton key={index} />
                  ))
                : pagedProducts.map((product) => (
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

            {/* Подгрузка: каталог большой, показываем по частям */}
            {!loading && visibleProducts.length > pagedProducts.length ? (
              <div className="mt-4 flex flex-col items-center gap-2">
                <button
                  type="button"
                  data-testid="catalog-load-more"
                  onClick={() =>
                    setVisibleCount((value) => value + PAGE_SIZE)
                  }
                  className="btn-secondary w-full sm:w-auto"
                >
                  Показать ещё ({visibleProducts.length - pagedProducts.length})
                </button>
                <p className="text-xs text-gray-400">
                  Показано {pagedProducts.length} из {visibleProducts.length}
                </p>
              </div>
            ) : null}

            {!loading && visibleProducts.length === 0 && !loadError ? (
              <div className="card p-8 text-center">
                <p className="text-3xl">🔍</p>
                <p className="mt-2 text-sm font-semibold text-gray-900">
                  Ничего не нашлось
                </p>
                <p className="mt-1 text-sm text-gray-500">
                  {car.make
                    ? 'Для выбранного автомобиля в каталоге пока нет деталей. Попробуйте другую марку или сбросьте фильтры.'
                    : query.trim()
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
          </div>
        </div>

        {health ? (
          <p className="mt-6 text-center text-xs text-gray-400">
            API: {health.database === 'ok' ? 'БД подключена' : health.database} ·
            Telegram: {health.telegram}
          </p>
        ) : null}

        {/* Контакты — на мобильных дублируют шапку, чтобы не искать */}
        <div className="mt-6 grid gap-3 sm:grid-cols-2">
          <a
            href={store?.phone_href ?? storeConfig.phoneHref}
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
                {store?.phone ?? storeConfig.phone}
              </span>
            </span>
          </a>
          <a
            href={store?.maps_url ?? storeConfig.mapsUrl}
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
                {store?.address ?? storeConfig.address}
              </span>
              <span className="block text-xs text-gray-400">
                Открыть в Яндекс.Картах
              </span>
            </span>
          </a>
        </div>
      </main>

      {/* Мобильная шторка фильтров */}
      {filtersOpen ? (
        <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true">
          <button
            type="button"
            aria-label="Закрыть фильтры"
            data-testid="catalog-filters-backdrop"
            onClick={() => setFiltersOpen(false)}
            className="absolute inset-0 bg-gray-900/40"
          />
          <div
            data-testid="catalog-filters-drawer"
            className="absolute inset-y-0 right-0 flex w-[85%] max-w-sm flex-col bg-gray-50 shadow-2xl"
          >
            <div className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3">
              <p className="text-sm font-semibold text-gray-900">Фильтры</p>
              <button
                type="button"
                onClick={() => setFiltersOpen(false)}
                aria-label="Закрыть фильтры"
                className="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
              >
                <IconClose className="h-5 w-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto p-3">
              <FilterPanel {...filterPanelProps} />
              {car.make ? (
                <button
                  type="button"
                  onClick={resetCar}
                  className="card mt-3 flex w-full items-center gap-2 p-3 text-left text-xs font-semibold text-gray-600 transition hover:bg-gray-50"
                >
                  <IconClose className="h-4 w-4 shrink-0 text-gray-400" />
                  Сбросить выбор автомобиля
                </button>
              ) : null}
            </div>
            <div className="border-t border-gray-200 bg-white p-3">
              <button
                type="button"
                data-testid="catalog-filters-apply"
                onClick={() => setFiltersOpen(false)}
                className="btn-primary w-full"
              >
                Показать {pluralItems(visibleProducts.length)}
              </button>
            </div>
          </div>
        </div>
      ) : null}

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
