import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { fetchMyOrders, fetchOrderTelegramLink } from '../api.js'
import { formatPrice, statusMeta } from '../lib/format.js'

// Компонент таймлайна статусов заказа
function Timeline({ order }) {
  const meta = statusMeta(order.status)
  const terminal = order.status === 'rejected' || order.status === 'cancelled'

  return (
    <div className="mt-3">
      <div className="flex items-center gap-2">
        <span
          data-testid="order-status"
          className={`rounded-full px-2.5 py-1 text-xs font-semibold ${meta.badge}`}
        >
          {meta.label}
        </span>
        {order.is_night_order ? (
          <span className="rounded-full bg-indigo-50 px-2.5 py-1 text-xs font-semibold text-indigo-700">
            🌙 ночной
          </span>
        ) : null}
      </div>
      {meta.description ? (
        <p className="mt-1.5 text-sm text-gray-500">{meta.description}</p>
      ) : null}

      {order.events?.length ? (
        <ol className="mt-3 space-y-2 border-l-2 border-gray-100 pl-3">
          {order.events.map((event) => (
            <li key={event.id} className="relative">
              <span className="absolute -left-[19px] top-1.5 h-2 w-2 rounded-full bg-accent-strong" />
              <p className="text-sm font-medium text-gray-800">
                {statusMeta(event.status).label}
                {event.note ? ` — ${event.note}` : ''}
              </p>
              <p className="text-xs text-gray-400">
                {new Date(event.created_at).toLocaleString('ru-RU', {
                  day: '2-digit',
                  month: '2-digit',
                  hour: '2-digit',
                  minute: '2-digit',
                })}
                {event.actor === 'manager' ? ' · менеджер' : ''}
              </p>
            </li>
          ))}
        </ol>
      ) : null}
      {terminal ? null : null}
    </div>
  )
}

export default function CabinetPage() {
  const [orders, setOrders] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [expanded, setExpanded] = useState(null)
  // Ссылка-подписка на уведомления в Telegram для каждого заказа.
  const [telegramLinks, setTelegramLinks] = useState({})

  const load = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const list = await fetchMyOrders()
      setOrders(list)
      // Подписка нужна только для активных заказов — по завершённым
      // уведомления уже не приходят.
      const active = list.filter(
        (order) => order.status !== 'completed'
          && order.status !== 'rejected'
          && order.status !== 'cancelled',
      )
      const pairs = await Promise.all(
        active.map(async (order) => {
          try {
            const link = await fetchOrderTelegramLink(order.order_number)
            return [order.order_number, link]
          } catch {
            return null
          }
        }),
      )
      setTelegramLinks(
        Object.fromEntries(pairs.filter(Boolean)),
      )
    } catch (err) {
      setError(err.message || 'Не удалось загрузить заказы')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    // Автообновление статуса: менеджер может нажать кнопку в Telegram.
    const timer = setInterval(load, 30000)
    return () => clearInterval(timer)
  }, [load])

  return (
    <div className="mx-auto max-w-3xl px-4 py-6">
      <h1 className="text-2xl font-bold text-gray-900">Мои заказы</h1>
      <p className="mt-1 text-sm text-gray-500">
        Статус обновляется автоматически. Менеджер меняет его в Telegram.
      </p>

      {error ? (
        <div className="card mt-4 border border-red-200 bg-red-50 p-4">
          <p className="text-sm text-red-700">{error}</p>
          <button type="button" onClick={load} className="btn-secondary mt-3">
            Повторить
          </button>
        </div>
      ) : null}

      {loading && orders.length === 0 ? (
        <div className="mt-4 space-y-3">
          {[0, 1].map((index) => (
            <div key={index} className="card animate-pulse p-4">
              <div className="h-4 w-40 rounded bg-gray-200" />
              <div className="mt-3 h-3 w-3/4 rounded bg-gray-100" />
            </div>
          ))}
        </div>
      ) : null}

      {!loading && orders.length === 0 && !error ? (
        <div className="card mt-4 p-8 text-center">
          <p className="text-sm text-gray-500">Заказов пока нет.</p>
          <Link to="/" className="btn-primary mt-4">
            Перейти в каталог
          </Link>
        </div>
      ) : null}

      <div className="mt-4 space-y-3">
        {orders.map((order) => {
          const isOpen = expanded === order.order_number
          return (
            <article
              key={order.order_number}
              data-testid="cabinet-order"
              className="card p-4"
            >
              <button
                type="button"
                onClick={() =>
                  setExpanded(isOpen ? null : order.order_number)
                }
                className="flex w-full items-start justify-between gap-3 text-left"
              >
                <div className="min-w-0">
                  <p className="font-semibold text-gray-900">
                    {order.order_number}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-500">
                    {new Date(order.created_at).toLocaleString('ru-RU', {
                      day: '2-digit',
                      month: '2-digit',
                      year: 'numeric',
                      hour: '2-digit',
                      minute: '2-digit',
                    })}
                    {' · '}
                    {order.pickup_method === 'delivery'
                      ? 'Доставка'
                      : 'Самовывоз'}
                  </p>
                </div>
                <div className="shrink-0 text-right">
                  <p className="font-bold text-gray-900">
                    {formatPrice(order.total)}
                  </p>
                  <p className="mt-0.5 text-xs text-gray-400">
                    {order.items.length} поз.
                  </p>
                </div>
              </button>

              <Timeline order={order} />

              {telegramLinks[order.order_number]?.link &&
              !telegramLinks[order.order_number]?.subscribed ? (
                <a
                  href={telegramLinks[order.order_number].link}
                  target="_blank"
                  rel="noreferrer"
                  data-testid="telegram-subscribe"
                  className="mt-3 block rounded-lg border border-blue-200 bg-blue-50 px-3 py-2 text-center text-sm font-medium text-blue-700 hover:bg-blue-100"
                >
                  Получать уведомления в Telegram
                </a>
              ) : null}
              {telegramLinks[order.order_number]?.subscribed ? (
                <p
                  data-testid="telegram-subscribed"
                  className="mt-3 rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-center text-sm text-emerald-700"
                >
                  Уведомления о заказе включены
                </p>
              ) : null}

              {isOpen ? (
                <div className="mt-3 space-y-2 border-t border-gray-100 pt-3">
                  {order.items.map((item, index) => (
                    <div
                      key={index}
                      className="flex items-center justify-between gap-3 text-sm"
                    >
                      <span className="min-w-0 truncate text-gray-700">
                        {item.product_name} × {item.qty}
                      </span>
                      <span className="shrink-0 font-medium text-gray-900">
                        {formatPrice(item.line_total)}
                      </span>
                    </div>
                  ))}
                  {order.comment ? (
                    <p className="rounded-lg bg-gray-50 p-3 text-sm text-gray-600">
                      <span className="font-medium">Комментарий: </span>
                      {order.comment}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </article>
          )
        })}
      </div>
    </div>
  )
}
