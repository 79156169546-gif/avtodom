import { useCallback, useEffect, useState } from 'react'
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

const STATUS_OPTIONS = [
  ['new', 'Новый'],
  ['accepted', 'Принят'],
  ['in_progress', 'В работе'],
  ['ready', 'Готов'],
  ['completed', 'Выполнен'],
  ['rejected', 'Отклонён'],
  ['cancelled', 'Отменён'],
]

const EMPTY_PRODUCT = {
  sku: '',
  name: '',
  brand: '',
  category: '',
  price: '',
  old_price: '',
  discount_percent: 0,
  in_stock: true,
  is_active: true,
  is_on_order: false,
  order_days: 3,
  description: '',
}

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

function StatCard({ label, value }) {
  return (
    <div className="card p-4">
      <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
        {label}
      </p>
      <p className="mt-1 text-xl font-bold text-gray-900">{value}</p>
    </div>
  )
}

export default function AdminPage() {
  const [tab, setTab] = useState('orders')
  const [orders, setOrders] = useState([])
  const [products, setProducts] = useState([])
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [editing, setEditing] = useState(null)
  const [form, setForm] = useState(EMPTY_PRODUCT)
  const [busy, setBusy] = useState(false)

  // Фильтры заказов
  const [statusFilter, setStatusFilter] = useState('')
  const [period, setPeriod] = useState('all')
  const [search, setSearch] = useState('')
  const [searchDraft, setSearchDraft] = useState('')
  const [nightOnly, setNightOnly] = useState(false)
  const [sort, setSort] = useState('newest')
  const [expanded, setExpanded] = useState(false)
  const [customRange, setCustomRange] = useState({ dateFrom: '', dateTo: '' })

  const load = useCallback(async () => {
    setError('')
    try {
      const range = periodRange(period, customRange)
      const [ordersData, productsData, statsData] = await Promise.all([
        fetchAdminOrders({
          status: statusFilter,
          dateFrom: range.dateFrom,
          dateTo: range.dateTo,
          query: search,
          nightOnly,
          sort,
          limit: 300,
        }),
        fetchAdminProducts(),
        fetchAdminStats(),
      ])
      setOrders(ordersData)
      setProducts(productsData)
      setStats(statsData)
    } catch (err) {
      setError(err.message || 'Не удалось загрузить данные')
    }
  }, [statusFilter, period, customRange, search, nightOnly, sort])

  useEffect(() => {
    load()
  }, [load])

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
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось изменить статус')
    } finally {
      setBusy(false)
    }
  }

  const openEditor = (product) => {
    setEditing(product?.id ?? null)
    setForm(
      product
        ? {
            sku: product.sku,
            name: product.name,
            brand: product.brand ?? '',
            category: product.category ?? '',
            price: String(product.price),
            old_price: product.old_price ? String(product.old_price) : '',
            discount_percent: product.discount_percent ?? 0,
            in_stock: product.in_stock,
            is_active: product.is_active,
            is_on_order: product.is_on_order ?? false,
            order_days: product.order_days ?? 3,
            description: product.description ?? '',
          }
        : EMPTY_PRODUCT,
    )
  }

  const submitProduct = async (event) => {
    event.preventDefault()
    setBusy(true)
    setError('')
    const payload = {
      sku: form.sku.trim(),
      name: form.name.trim(),
      brand: form.brand.trim() || null,
      category: form.category.trim() || null,
      price: Number(form.price) || 0,
      old_price: form.old_price ? Number(form.old_price) : null,
      discount_percent: Number(form.discount_percent) || 0,
      in_stock: form.in_stock,
      is_active: form.is_active,
      is_on_order: form.is_on_order,
      order_days: Number(form.order_days) || 0,
      description: form.description.trim() || null,
    }
    try {
      if (editing) {
        await updateAdminProduct(editing, payload)
        setNotice(`Товар ${payload.sku} обновлён`)
      } else {
        await createAdminProduct(payload)
        setNotice(`Товар ${payload.sku} добавлен`)
      }
      setEditing(null)
      setForm(EMPTY_PRODUCT)
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось сохранить товар')
    } finally {
      setBusy(false)
    }
  }

  const toggleActive = async (product) => {
    setBusy(true)
    try {
      await deleteAdminProduct(product.id, !product.is_active)
      await load()
    } catch (err) {
      setError(err.message || 'Не удалось изменить видимость')
    } finally {
      setBusy(false)
    }
  }

  const totals = stats?.totals

  return (
    <div className="mx-auto max-w-4xl px-4 py-6">
      <h1 className="text-2xl font-bold text-gray-900">Кабинет владельца</h1>
      <p className="mt-1 text-sm text-gray-500">
        Заказы, каталог, скидки и наличие.
      </p>

      {error ? (
        <div className="card mt-4 border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
        </div>
      ) : null}
      {notice ? (
        <div className="card mt-4 border border-emerald-200 bg-emerald-50 p-4">
          <p className="text-sm text-emerald-800">{notice}</p>
        </div>
      ) : null}

      {totals ? (
        <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <StatCard label="Заказов всего" value={totals.orders_total} />
          <StatCard label="Новых" value={totals.orders_new} />
          <StatCard
            label="Выручка за сегодня"
            value={formatPrice(totals.revenue_today)}
          />
          <StatCard label="Товаров в каталоге" value={totals.products_active} />
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
                <div>
                  <label className="label" htmlFor="admin-search">
                    Поиск
                  </label>
                  <input
                    id="admin-search"
                    data-testid="admin-search"
                    className="field"
                    placeholder="Номер заказа, имя, телефон, авто"
                    value={searchDraft}
                    onChange={(event) => setSearchDraft(event.target.value)}
                  />
                </div>
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

          {orders.length === 0 ? (
            <p className="card p-6 text-center text-sm text-gray-500">
              По выбранным фильтрам заказов нет.
            </p>
          ) : null}
          {orders.map((order) => (
            <article
              key={order.id}
              data-testid="admin-order"
              className="card p-4"
            >
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-semibold text-gray-900">
                    {order.order_number}
                    <span
                      className={`ml-2 rounded-full px-2 py-0.5 text-xs font-semibold ${statusMeta(order.status).badge}`}
                    >
                      {statusMeta(order.status).label}
                    </span>
                    {order.is_night_order ? (
                      <span
                        data-testid="admin-order-priority"
                        className="ml-1.5 rounded-full bg-orange-100 px-2 py-0.5 text-xs font-semibold text-accent-strong"
                        title="Заказ в нерабочее время (20:00–08:00) — в приоритете"
                      >
                        🌙 приоритет
                      </span>
                    ) : null}
                  </p>
                  <p className="mt-1 text-sm text-gray-600">
                    {order.customer_name}
                    {order.phone ? ` · ${order.phone}` : ''}
                    {order.telegram ? ` · @${order.telegram}` : ''}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-500">
                    {order.car_make || order.car_model
                      ? `${order.car_make ?? ''} ${order.car_model ?? ''} ${
                          order.vin ? `VIN ${order.vin}` : ''
                        }`
                      : 'Авто не указано'}
                    {' · '}
                    {order.pickup_method === 'delivery'
                      ? `Доставка${order.address ? ` (${order.address})` : ''}`
                      : 'Самовывоз'}
                    {order.is_night_order ? ' · 🌙 ночной' : ''}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-400">
                    {new Date(order.created_at).toLocaleString('ru-RU', {
                      day: '2-digit',
                      month: '2-digit',
                      year: '2-digit',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                    {order.updated_at !== order.created_at
                      ? ` · обновлён ${new Date(
                          order.updated_at,
                        ).toLocaleString('ru-RU', {
                          day: '2-digit',
                          month: '2-digit',
                          hour: '2-digit',
                          minute: '2-digit',
                        })}`
                      : ''}
                  </p>
                  {order.comment ? (
                    <p className="mt-1.5 rounded-lg bg-gray-50 px-3 py-2 text-xs text-gray-600">
                      {order.comment}
                    </p>
                  ) : null}
                </div>
                <p className="shrink-0 font-bold text-gray-900">
                  {formatPrice(order.total)}
                </p>
              </div>

              <div className="mt-3 flex flex-wrap gap-2 border-t border-gray-100 pt-3">
                {STATUS_OPTIONS.map(([value, title]) => (
                  <button
                    key={value}
                    type="button"
                    data-testid={`set-status-${value}`}
                    disabled={busy || order.status === value}
                    onClick={() => changeStatus(order, value)}
                    className={`rounded-lg px-3 py-1.5 text-xs font-semibold transition ${
                      order.status === value
                        ? 'bg-accent-soft text-accent-strong'
                        : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
                    } disabled:cursor-not-allowed disabled:opacity-50`}
                  >
                    {title}
                  </button>
                ))}
              </div>

              {order.items?.length ? (
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs text-gray-400">
                    Состав заказа ({order.items.length})
                  </summary>
                  <ul className="mt-2 space-y-1">
                    {order.items.map((item) => (
                      <li
                        key={`${item.product_id ?? item.product_name}-${item.product_name}`}
                        className="flex justify-between gap-3 text-xs text-gray-600"
                      >
                        <span className="truncate">
                          {item.product_name} × {item.qty}
                          {item.is_on_order ? (
                            <span className="ml-1.5 rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700">
                              под заказ · {item.order_days} дн.
                            </span>
                          ) : null}
                        </span>
                        <span className="shrink-0 font-medium text-gray-800">
                          {formatPrice(item.line_total)}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              ) : null}

              {order.events?.length ? (
                <details className="mt-2">
                  <summary className="cursor-pointer text-xs text-gray-400">
                    История ({order.events.length})
                  </summary>
                  <ol className="mt-2 space-y-1.5 border-l-2 border-gray-100 pl-3">
                    {order.events.map((event) => (
                      <li key={event.id} className="relative">
                        <span className="absolute -left-[19px] top-1.5 h-2 w-2 rounded-full bg-accent-strong" />
                        <p className="text-xs font-medium text-gray-700">
                          {statusMeta(event.status).label}
                          {event.note ? ` — ${event.note}` : ''}
                        </p>
                        <p className="text-[11px] text-gray-400">
                          {new Date(event.created_at).toLocaleString('ru-RU')}
                        </p>
                      </li>
                    ))}
                  </ol>
                </details>
              ) : null}
            </article>
          ))}
        </div>
      ) : null}

      {tab === 'products' ? (
        <div className="mt-4">
          <form onSubmit={submitProduct} className="card space-y-3 p-4">
            <div className="flex items-center justify-between">
              <h2 className="font-semibold text-gray-900">
                {editing ? 'Редактирование товара' : 'Новый товар'}
              </h2>
              {editing ? (
                <button
                  type="button"
                  onClick={() => {
                    setEditing(null)
                    setForm(EMPTY_PRODUCT)
                  }}
                  className="text-xs font-semibold text-gray-500"
                >
                  Отмена
                </button>
              ) : null}
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="label">Артикул</label>
                <input
                  data-testid="product-sku"
                  required
                  className="field"
                  value={form.sku}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, sku: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="label">Название</label>
                <input
                  data-testid="product-name"
                  required
                  className="field"
                  value={form.name}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, name: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="label">Бренд</label>
                <input
                  className="field"
                  value={form.brand}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, brand: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="label">Категория</label>
                <input
                  className="field"
                  value={form.category}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, category: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="label">Цена, ₽</label>
                <input
                  data-testid="product-price"
                  type="number"
                  min="0"
                  step="1"
                  required
                  className="field"
                  value={form.price}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, price: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="label">Цена до скидки, ₽</label>
                <input
                  type="number"
                  min="0"
                  step="1"
                  className="field"
                  value={form.old_price}
                  onChange={(e) =>
                    setForm((prev) => ({ ...prev, old_price: e.target.value }))
                  }
                />
              </div>
              <div>
                <label className="label">Скидка, %</label>
                <input
                  data-testid="product-discount"
                  type="number"
                  min="0"
                  max="90"
                  step="1"
                  className="field"
                  value={form.discount_percent}
                  onChange={(e) =>
                    setForm((prev) => ({
                      ...prev,
                      discount_percent: e.target.value,
                    }))
                  }
                />
              </div>
              <div className="flex flex-wrap items-end gap-4 pb-2">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    data-testid="product-in-stock"
                    checked={form.in_stock}
                    onChange={(e) =>
                      setForm((prev) => ({
                        ...prev,
                        in_stock: e.target.checked,
                        // Деталь в наличии не может быть «под заказ».
                        is_on_order: e.target.checked ? false : prev.is_on_order,
                      }))
                    }
                    className="h-4 w-4 accent-orange-600"
                  />
                  В наличии
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    data-testid="product-on-order"
                    checked={form.is_on_order}
                    onChange={(e) =>
                      setForm((prev) => ({
                        ...prev,
                        is_on_order: e.target.checked,
                        // Под заказ — значит в наличии её нет.
                        in_stock: e.target.checked ? false : prev.in_stock,
                      }))
                    }
                    className="h-4 w-4 accent-orange-600"
                  />
                  Под заказ
                </label>
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={form.is_active}
                    onChange={(e) =>
                      setForm((prev) => ({ ...prev, is_active: e.target.checked }))
                    }
                    className="h-4 w-4 accent-orange-600"
                  />
                  Показывать
                </label>
              </div>

              {form.is_on_order ? (
                <div>
                  <label className="label" htmlFor="product-order-days">
                    Срок поставки, дней
                  </label>
                  <input
                    id="product-order-days"
                    data-testid="product-order-days"
                    type="number"
                    min="0"
                    max="365"
                    step="1"
                    className="field"
                    value={form.order_days}
                    onChange={(e) =>
                      setForm((prev) => ({
                        ...prev,
                        order_days: e.target.value,
                      }))
                    }
                  />
                  <p className="mt-1.5 text-xs text-gray-400">
                    Срок заказа у поставщика. Покажем клиенту на витрине и в
                    подтверждении заказа.
                  </p>
                </div>
              ) : null}
            </div>

            <div>
              <label className="label">Описание</label>
              <textarea
                rows={2}
                className="field resize-none"
                value={form.description}
                onChange={(e) =>
                  setForm((prev) => ({ ...prev, description: e.target.value }))
                }
              />
            </div>

            <button
              type="submit"
              data-testid="product-save"
              className="btn-primary"
              disabled={busy}
            >
              {editing ? 'Сохранить изменения' : 'Добавить товар'}
            </button>
          </form>

          <div className="mt-4 space-y-2">
            {products.map((product) => (
              <article
                key={product.id}
                data-testid="admin-product"
                className={`card flex flex-wrap items-center justify-between gap-3 p-3 ${
                  product.is_active ? '' : 'opacity-60'
                }`}
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-gray-900">
                    {product.name}
                    <span className="ml-2 text-xs font-normal text-gray-400">
                      {product.sku}
                    </span>
                  </p>
                  <p className="text-xs text-gray-500">
                    {formatPrice(product.price)}
                    {product.old_price ? (
                      <span className="ml-1 line-through text-gray-400">
                        {formatPrice(product.old_price)}
                      </span>
                    ) : null}
                    {product.discount_percent ? (
                      <span className="ml-2 rounded-full bg-orange-50 px-1.5 py-0.5 text-[11px] font-semibold text-accent-strong">
                        −{product.discount_percent}%
                      </span>
                    ) : null}
                    {!product.in_stock ? (
                      <span className="ml-2 rounded-full bg-gray-100 px-1.5 py-0.5 text-[11px] font-medium text-gray-500">
                        нет в наличии
                      </span>
                    ) : null}
                    {product.is_on_order ? (
                      <span
                        data-testid="admin-product-on-order"
                        className="ml-2 rounded-full bg-blue-50 px-1.5 py-0.5 text-[11px] font-semibold text-blue-700"
                      >
                        под заказ · {product.order_days} дн.
                      </span>
                    ) : null}
                    {!product.is_active ? (
                      <span className="ml-2 rounded-full bg-gray-100 px-1.5 py-0.5 text-[11px] font-medium text-gray-500">
                        скрыт
                      </span>
                    ) : null}
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    type="button"
                    onClick={() => openEditor(product)}
                    className="btn-secondary"
                  >
                    Изменить
                  </button>
                  <button
                    type="button"
                    onClick={() => toggleActive(product)}
                    disabled={busy}
                    className="btn-secondary"
                  >
                    {product.is_active ? 'Скрыть' : 'Показать'}
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
