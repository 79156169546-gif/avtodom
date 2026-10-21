import { useCallback, useEffect, useMemo, useState } from 'react'
import {
  createAdminProduct,
  deleteAdminProduct,
  fetchAdminOrders,
  fetchAdminProducts,
  fetchAdminStats,
  updateAdminOrder,
  updateAdminProduct,
} from '../api.js'
import { formatPrice, statusMeta } from '../lib/format.js'
import OrderCard, { STATUS_OPTIONS } from '../components/OrderCard.jsx'
import ProductDrawer, {
  EMPTY_PRODUCT,
  ProductRow,
  productToForm,
} from '../components/ProductDrawer.jsx'
import StatCard from '../components/StatCard.jsx'
import Switch from '../components/Switch.jsx'
import { IconEye, IconPencil, IconSearch } from '../components/icons.jsx'

// Быстрые периоды: подставляем даты в формате ГГГГ-ММ-ДД.
const PERIODS = [
  { id: 'all', title: 'Все' },
  { id: 'today', title: 'Сегодня' },
  { id: 'week', title: '7 дней' },
  { id: 'month', title: '30 дней' },
]

const SORTS = [
  { id: 'newest', title: 'Сначала новые' },
  { id: 'oldest', title: 'Сначала старые' },
  { id: 'night_first', title: 'Приоритетные сверху' },
]

function isoDate(date) {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

function periodRange(period, custom = { dateFrom: '', dateTo: '' }) {
  const now = new Date()
  if (period === 'today') {
    return { dateFrom: isoDate(now), dateTo: isoDate(now) }
  }
  if (period === 'week' || period === 'month') {
    const days = period === 'week' ? 6 : 29
    const from = new Date(now)
    from.setDate(now.getDate() - days)
    return { dateFrom: isoDate(from), dateTo: isoDate(now) }
  }
  if (period === 'custom') {
    return custom
  }
  return { dateFrom: '', dateTo: '' }
}

// Разбор строки совместимости вида «KIA Rio 2011-2017».
// Поддерживаемые формы: «МАРКА МОДЕЛЬ 2011-2017», «МАРКА МОДЕЛЬ 2011»,
// «МАРКА 2011-2017», «МАРКА МОДЕЛЬ».
function parseCompatibilityLine(line) {
  const text = line.trim()
  if (!text) return null

  const years = text.match(/(\d{4})(?:\s*[-–—]\s*(\d{4}))?/)
  const make = text.slice(0, years ? years.index : text.length).trim()
  if (!make) return null

  const model = text
    .slice(years ? years.index : text.length)
    .replace(/(\d{4})(?:\s*[-–—]\s*(\d{4}))?/, '')
    .trim()

  return {
    make,
    model: model || null,
    year_from: years ? Number(years[1]) : null,
    year_to: years && years[2] ? Number(years[2]) : years ? Number(years[1]) : null,
  }
}

function parseCompatibility(text) {
  return (text ?? '')
    .split('\n')
    .map(parseCompatibilityLine)
    .filter(Boolean)
}

export default function AdminPage() {
  const [tab, setTab] = useState('orders')
  const [orders, setOrders] = useState([])
  const [products, setProducts] = useState([])
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState(null)
  const [busy, setBusy] = useState(false)

  // Фильтры заказов
  const [statusFilter, setStatusFilter] = useState('')
  const [period, setPeriod] = useState('all')
  const [search, setSearch] = useState('')
  const [searchDraft, setSearchDraft] = useState('')
  const [nightOnly, setNightOnly] = useState(false)
  const [sort, setSort] = useState('newest')
  // Поиск по каталогу — владелец ищет деталь по артикулу или названию.
  const [productQuery, setProductQuery] = useState('')
  const [expanded, setExpanded] = useState(false)
  const [customRange, setCustomRange] = useState({ dateFrom: '', dateTo: '' })

  // Заказы и каталог грузим раздельно: смена фильтра заказов не должна
  // заново тянуть весь каталог и статистику — иначе каждый клик ждёт
  // лишние запросы к серверу.
  const loadOrders = useCallback(async () => {
    setError('')
    try {
      const range = periodRange(period, customRange)
      const ordersData = await fetchAdminOrders({
        status: statusFilter,
        dateFrom: range.dateFrom,
        dateTo: range.dateTo,
        query: search,
        nightOnly,
        sort,
        limit: 300,
      })
      setOrders(ordersData)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить заказы')
    }
  }, [statusFilter, period, customRange, search, nightOnly, sort])

  const loadProducts = useCallback(async () => {
    try {
      setProducts(await fetchAdminProducts())
    } catch (err) {
      setError(err.message || 'Не удалось загрузить каталог')
    }
  }, [])

  const loadStats = useCallback(async () => {
    try {
      setStats(await fetchAdminStats())
    } catch (err) {
      setError(err.message || 'Не удалось загрузить статистику')
    }
  }, [])

  useEffect(() => {
    loadOrders()
  }, [loadOrders])

  useEffect(() => {
    loadProducts()
    loadStats()
  }, [loadProducts, loadStats])

  // Поиск применяем с задержкой, чтобы не дёргать сервер на каждую букву.
  useEffect(() => {
    const timer = setTimeout(() => setSearch(searchDraft.trim()), 350)
    return () => clearTimeout(timer)
  }, [searchDraft])

  const changeStatus = async (order, status) => {
    setBusy(true)
    setError('')
    try {
      await updateAdminOrder(order.id, { status })
      setNotice(`Заказ ${order.order_number}: статус «${statusMeta(status).label}»`)
      await Promise.all([loadOrders(), loadStats()])
    } catch (err) {
      setError(err.message || 'Не удалось изменить статус')
    } finally {
      setBusy(false)
    }
  }

  const openEditor = (product) => {
    setEditingProduct(product ?? null)
    setDrawerOpen(true)
  }

  const submitProduct = async (payload) => {
    setBusy(true)
    setError('')
    try {
      if (editingProduct) {
        await updateAdminProduct(editingProduct.id, payload)
        setNotice(`Товар ${payload.sku} обновлён`)
      } else {
        await createAdminProduct(payload)
        setNotice(`Товар ${payload.sku} добавлен`)
      }
      setDrawerOpen(false)
      setEditingProduct(null)
      await Promise.all([loadProducts(), loadStats()])
    } catch (err) {
      setError(err.message || 'Не удалось сохранить товар')
    } finally {
      setBusy(false)
    }
  }

  // Мгновенное сохранение: тумблер в таблице шлёт PATCH сразу, без формы.
  // Владелец правит наличие прямо в каталоге — без лишних кликов.
  const patchProduct = async (product, patch, message) => {
    setBusy(true)
    setError('')
    // Оптимистичное обновление: состояние меняется сразу, а при ошибке
    // возвращаем как было.
    const previous = products
    setProducts((items) =>
      items.map((item) => (item.id === product.id ? { ...item, ...patch } : item)),
    )
    try {
      // Совместимость не передаём: её меняют только в форме товара.
      // Иначе PATCH перезаписал бы список авто при каждом переключении.
      const { compatibility, ...rest } = product
      await updateAdminProduct(product.id, { ...rest, ...patch })
      if (message) setNotice(message)
    } catch (err) {
      setProducts(previous)
      setError(err.message || 'Не удалось сохранить изменения')
    } finally {
      setBusy(false)
    }
  }

  const toggleStock = (product, value) =>
    patchProduct(
      product,
      // Деталь в наличии не может быть «под заказ».
      { in_stock: value, is_on_order: value ? false : product.is_on_order },
      value
        ? `${product.sku}: снова в наличии`
        : `${product.sku}: нет в наличии`,
    )

  const toggleOnOrder = (product, value) =>
    patchProduct(
      product,
      { is_on_order: value, in_stock: value ? false : product.in_stock },
      value
        ? `${product.sku}: под заказ, ${product.order_days ?? 3} дн.`
        : `${product.sku}: больше не под заказ`,
    )

  const changeOrderDays = (product, days) =>
    patchProduct(
      product,
      { order_days: days },
      `${product.sku}: срок поставки ${days} дн.`,
    )

  const toggleActive = async (product) => {
    setBusy(true)
    try {
      await deleteAdminProduct(product.id, !product.is_active)
      await Promise.all([loadProducts(), loadStats()])
    } catch (err) {
      setError(err.message || 'Не удалось изменить видимость')
    } finally {
      setBusy(false)
    }
  }

  // Поиск по каталогу: название, артикул, бренд или категория.
  const filteredProducts = useMemo(() => {
    const needle = productQuery.trim().toLowerCase()
    if (!needle) return products
    return products.filter((product) =>
      [product.name, product.sku, product.brand, product.category]
        .filter(Boolean)
        .some((value) => value.toLowerCase().includes(needle)),
    )
  }, [products, productQuery])

  // Скрытых товаров в списке — владельцу важно видеть, что они не в продаже.
  const hiddenCount = useMemo(
    () => products.filter((product) => !product.is_active).length,
    [products],
  )

  const totals = stats?.totals

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <h1 className="text-2xl font-bold text-gray-900">Кабинет владельца</h1>
      <p className="mt-1 text-sm text-gray-500">
        Заказы, каталог, скидки и наличие.
      </p>

      {error ? (
        <div className="card mt-4 border border-red-200 bg-red-50 p-4">
          <p data-testid="admin-error" className="text-sm text-red-700">{error}</p>
        </div>
      ) : null}
      {notice ? (
        <div className="card mt-4 border border-emerald-200 bg-emerald-50 p-4">
          <p data-testid="admin-notice" className="text-sm text-emerald-800">{notice}</p>
        </div>
      ) : null}

      {totals ? (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          {/* Метрики кликабельны: клик сразу применяет фильтр заказов. */}
          <StatCard
            testId="stat-orders-total"
            label="Заказов всего"
            value={totals.orders_total}
            active={statusFilter === '' && period === 'all' && !nightOnly}
            hint="Показать все"
            onClick={() => {
              setStatusFilter('')
              setPeriod('all')
              setNightOnly(false)
            }}
          />
          <StatCard
            testId="stat-orders-new"
            label="Новых"
            value={totals.orders_new}
            active={statusFilter === 'new'}
            hint="Только новые"
            onClick={() => setStatusFilter('new')}
          />
          <StatCard
            testId="stat-revenue"
            label="Выручка за сегодня"
            value={formatPrice(totals.revenue_today)}
            active={period === 'today'}
            hint="Заказы за сегодня"
            onClick={() => setPeriod('today')}
          />
          <StatCard
            testId="stat-products"
            label="Товаров в каталоге"
            value={totals.products_active}
            active={tab === 'products'}
            hint="Открыть каталог"
            onClick={() => setTab('products')}
          />
        </div>
      ) : null}

      <div className="mt-5 flex gap-2">
        {[
          ['orders', 'Заказы'],
          ['products', 'Каталог'],
        ].map(([key, title]) => (
          <button
            key={key}
            type="button"
            data-testid={`admin-tab-${key}`}
            onClick={() => setTab(key)}
            className={`rounded-xl px-4 py-2 text-sm font-semibold transition ${
              tab === key
                ? 'bg-accent-strong text-white'
                : 'bg-white text-gray-600 shadow-card hover:bg-gray-50'
            }`}
          >
            {title}
          </button>
        ))}
      </div>

      {tab === 'orders' ? (
        <div className="mt-4 space-y-3">
          {/* Фильтры */}
          <div
            data-testid="admin-filters"
            className="card space-y-3 p-4"
          >
            <div className="flex items-center justify-between gap-2">
              <h2 className="text-sm font-semibold text-gray-900">Фильтры</h2>
              <button
                type="button"
                data-testid="admin-filters-toggle"
                onClick={() => setExpanded((value) => !value)}
                className="text-xs font-semibold text-accent-strong"
              >
                {expanded ? 'Скрыть' : 'Подробнее'}
              </button>
            </div>

            {/* Статус */}
            <div className="flex flex-wrap gap-1.5">
              <button
                type="button"
                data-testid="filter-status-all"
                onClick={() => setStatusFilter('')}
                className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                  statusFilter === ''
                    ? 'bg-accent-strong text-white'
                    : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                }`}
              >
                Все
                {stats?.by_status ? ` (${stats.totals.orders_total})` : ''}
              </button>
              {STATUS_OPTIONS.map(([value, title]) => (
                <button
                  key={value}
                  type="button"
                  data-testid={`filter-status-${value}`}
                  onClick={() => setStatusFilter(value)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    statusFilter === value
                      ? 'bg-accent-strong text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {title}
                  {stats?.by_status?.[value] ? ` (${stats.by_status[value]})` : ''}
                </button>
              ))}
            </div>

            {/* Период */}
            <div className="flex flex-wrap gap-1.5">
              {PERIODS.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  data-testid={`filter-period-${item.id}`}
                  onClick={() => setPeriod(item.id)}
                  className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                    period === item.id
                      ? 'bg-accent-strong text-white'
                      : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                  }`}
                >
                  {item.title}
                </button>
              ))}
            </div>

            {expanded ? (
              <div className="space-y-3 border-t border-gray-100 pt-3">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div>
                    <label className="label" htmlFor="admin-date-from">
                      Дата с
                    </label>
                    <input
                      id="admin-date-from"
                      data-testid="admin-date-from"
                      type="date"
                      className="field"
                      value={periodRange(period, customRange).dateFrom}
                      onChange={(event) => {
                        setPeriod('custom')
                        setCustomRange((prev) => ({
                          ...prev,
                          dateFrom: event.target.value,
                        }))
                      }}
                    />
                  </div>
                  <div>
                    <label className="label" htmlFor="admin-date-to">
                      Дата по
                    </label>
                    <input
                      id="admin-date-to"
                      data-testid="admin-date-to"
                      type="date"
                      className="field"
                      value={periodRange(period, customRange).dateTo}
                      onChange={(event) => {
                        setPeriod('custom')
                        setCustomRange((prev) => ({
                          ...prev,
                          dateTo: event.target.value,
                        }))
                      }}
                    />
                  </div>
                </div>
                <div>
                  <label className="label" htmlFor="admin-sort">
                    Сортировка
                  </label>
                  <select
                    id="admin-sort"
                    data-testid="admin-sort"
                    className="field"
                    value={sort}
                    onChange={(event) => setSort(event.target.value)}
                  >
                    {SORTS.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.title}
                      </option>
                    ))}
                  </select>
                </div>
                <label className="flex items-center gap-2 text-sm text-gray-700">
                  <input
                    type="checkbox"
                    data-testid="admin-night-only"
                    checked={nightOnly}
                    onChange={(event) => setNightOnly(event.target.checked)}
                    className="h-4 w-4 accent-orange-600"
                  />
                  Только приоритетные (20:00–08:00)
                </label>
              </div>
            ) : null}

            <div className="flex items-center justify-between border-t border-gray-100 pt-3">
              <p className="text-xs text-gray-500">
                Найдено заказов: <span className="font-semibold text-gray-900">{orders.length}</span>
              </p>
              <button
                type="button"
                data-testid="admin-filters-reset"
                onClick={() => {
                  setStatusFilter('')
                  setPeriod('all')
                  setSearch('')
                  setSearchDraft('')
                  setNightOnly(false)
                  setSort('newest')
                  setCustomRange({ dateFrom: '', dateTo: '' })
                }}
                className="text-xs font-semibold text-gray-500 hover:text-gray-700"
              >
                Сбросить
              </button>
            </div>
          </div>

          {/* Поиск — широкая строка прямо над списком заказов */}
          <div className="relative">
            <span
              aria-hidden="true"
              className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"
            >
              <IconSearch className="h-4 w-4" />
            </span>
            <input
              id="admin-search"
              type="search"
              data-testid="admin-search"
              className="field pl-10"
              placeholder="Номер заказа, имя клиента или телефон…"
              value={searchDraft}
              onChange={(event) => setSearchDraft(event.target.value)}
            />
            {searchDraft ? (
              <button
                type="button"
                onClick={() => setSearchDraft('')}
                aria-label="Очистить поиск"
                className="absolute right-3 top-1/2 -translate-y-1/2 rounded-full p-1 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
              >
                ✕
              </button>
            ) : null}
          </div>

          {orders.length === 0 ? (
            <p className="card p-6 text-center text-sm text-gray-500">
              По выбранным фильтрам заказов нет.
            </p>
          ) : null}
          {orders.map((order) => (
            <OrderCard
              key={order.id}
              order={order}
              busy={busy}
              onStatus={changeStatus}
            />
          ))}
        </div>
      ) : null}

      {tab === 'products' ? (
        <div className="mt-4">
          {/* Шапка каталога: поиск и добавление товара */}
          <div className="card flex flex-col gap-3 p-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="relative flex-1">
              <span
                aria-hidden="true"
                className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-gray-400"
              >
                <IconSearch className="h-4 w-4" />
              </span>
              <input
                type="search"
                data-testid="admin-product-search"
                className="field pl-10"
                placeholder="Название, артикул или бренд…"
                value={productQuery}
                onChange={(event) => setProductQuery(event.target.value)}
              />
            </div>
            <div className="flex items-center gap-2">
              <p className="text-sm text-gray-500">
                {hiddenCount > 0 ? (
                  <>
                    Показано{' '}
                    <span className="font-semibold text-gray-900">{filteredProducts.length}</span>
                    , из них скрыто {hiddenCount}
                  </>
                ) : (
                  <>
                    Товаров:{' '}
                    <span className="font-semibold text-gray-900">{filteredProducts.length}</span>
                  </>
                )}
              </p>
              <button
                type="button"
                data-testid="admin-add-product"
                onClick={() => openEditor(null)}
                className="btn-primary whitespace-nowrap"
              >
                + Добавить товар
              </button>
            </div>
          </div>

          {/* Таблица каталога. На узких экранах строки становятся карточками. */}
          {filteredProducts.length === 0 ? (
            <p className="card mt-3 p-6 text-center text-sm text-gray-500">
              Товаров не найдено.
            </p>
          ) : null}

          {filteredProducts.length > 0 ? (
            <>
              {/* Десктоп: таблица */}
              <div className="card mt-3 hidden overflow-hidden md:block">
                <table
                  data-testid="admin-products-table"
                  className="w-full table-fixed border-collapse text-left"
                >
                  <thead>
                    <tr className="border-b border-gray-200 bg-gray-50">
                      <th className="w-[38%] px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Название / Артикул
                      </th>
                      <th className="w-[16%] px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Цена
                      </th>
                      <th className="w-[12%] px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Наличие
                      </th>
                      <th className="w-[18%] px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Под заказ
                      </th>
                      <th className="w-[16%] px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-gray-500">
                        Действия
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredProducts.map((product) => (
                      <ProductRow
                        key={product.id}
                        product={product}
                        busy={busy}
                        onToggleStock={toggleStock}
                        onToggleOnOrder={toggleOnOrder}
                        onDaysChange={changeOrderDays}
                        onEdit={openEditor}
                        onToggleActive={toggleActive}
                      />
                    ))}
                  </tbody>
                </table>
              </div>

              {/* Мобильные: компактные карточки */}
              <div className="mt-3 space-y-2 md:hidden">
                {filteredProducts.map((product) => (
                  <div
                    key={product.id}
                    data-testid="admin-product-card"
                    data-sku={product.sku}
                    className={`card p-3 ${
                      product.is_active ? '' : 'opacity-60'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-gray-900">
                          {product.name}
                        </p>
                        <p className="mt-0.5 text-xs text-gray-400">
                          <span className="font-mono">{product.sku}</span>
                          {product.brand ? ` · ${product.brand}` : ''}
                        </p>
                      </div>
                      <div className="shrink-0 text-right">
                        <p className="text-sm font-bold text-gray-900">
                          {formatPrice(product.price)}
                        </p>
                        {product.old_price ? (
                          <p className="text-[11px] text-gray-400 line-through">
                            {formatPrice(product.old_price)}
                          </p>
                        ) : null}
                        {!product.is_active ? (
                          <span className="mt-0.5 inline-block rounded-full bg-gray-100 px-1.5 py-0.5 text-[10px] font-semibold text-gray-500">
                            скрыт
                          </span>
                        ) : null}
                      </div>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-3 border-t border-gray-100 pt-2">
                      <Switch
                        size="sm"
                        testId={`product-stock-${product.sku}`}
                        label="В наличии"
                        checked={product.in_stock}
                        disabled={busy}
                        onChange={(value) => toggleStock(product, value)}
                      />
                      <Switch
                        size="sm"
                        tone="blue"
                        testId={`product-onorder-${product.sku}`}
                        label="Под заказ"
                        checked={product.is_on_order}
                        disabled={busy}
                        onChange={(value) => toggleOnOrder(product, value)}
                      />
                      {product.is_on_order ? (
                        <input
                          type="number"
                          min="0"
                          max="365"
                          data-testid={`product-days-${product.sku}`}
                          defaultValue={product.order_days ?? 3}
                          onBlur={(event) => {
                            const days = Number(event.target.value)
                            if (days !== product.order_days) {
                              changeOrderDays(product, days)
                            }
                          }}
                          className="w-16 rounded-lg border border-gray-200 px-2 py-1 text-xs outline-none focus:border-accent"
                          aria-label="Срок поставки в днях"
                        />
                      ) : null}
                      <div className="ml-auto flex items-center gap-1.5">
                        <button
                          type="button"
                          data-testid={`product-edit-${product.sku}`}
                          onClick={() => openEditor(product)}
                          className="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700"
                          aria-label={`Редактировать ${product.name}`}
                        >
                          <IconPencil className="h-4 w-4" />
                        </button>
                        <button
                          type="button"
                          data-testid={`product-active-${product.sku}`}
                          onClick={() => toggleActive(product)}
                          disabled={busy}
                          className="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 disabled:opacity-50"
                          aria-label={product.is_active ? 'Скрыть товар' : 'Показать товар'}
                        >
                          <IconEye className="h-4 w-4" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </>
          ) : null}
        </div>
      ) : null}

      <ProductDrawer
        open={drawerOpen}
        product={editingProduct}
        busy={busy}
        onClose={() => {
          setDrawerOpen(false)
          setEditingProduct(null)
        }}
        onSubmit={submitProduct}
      />

    </div>
  )
}
