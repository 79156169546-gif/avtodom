import { useEffect, useRef, useState } from 'react'
import { formatPrice, statusMeta } from '../lib/format.js'
import { IconCar, IconMore, IconPhone } from './icons.jsx'

// Все статусы заказа — используются и в выпадающем меню, и в списке.
export const STATUS_OPTIONS = [
  ['new', 'Новый'],
  ['accepted', 'Принят'],
  ['in_progress', 'В работе'],
  ['ready', 'Готов'],
  ['completed', 'Выполнен'],
  ['rejected', 'Отклонён'],
  ['cancelled', 'Отменён'],
]

// Главное действие по текущему статусу: одна большая кнопка вместо
// семи мелких. Владельцу нужно одно движение, а не выбор из списка.
const PRIMARY_ACTION = {
  new: { status: 'accepted', label: 'Принять в работу' },
  accepted: { status: 'in_progress', label: 'В работу' },
  in_progress: { status: 'ready', label: 'Готов к выдаче' },
  ready: { status: 'completed', label: 'Завершить' },
  completed: null,
  rejected: null,
  cancelled: null,
}

// Единица измерения в составе заказа: «шт», «компл», «уп».
function unitFor(name) {
  const text = (name ?? '').toLowerCase()
  if (text.includes('комплект') || text.includes('компл')) return 'компл'
  if (text.includes('уп') || text.includes('упаков')) return 'уп'
  return 'шт'
}

// Короткий состав заказа: «Масляный фильтр (1 шт), Колодки (1 компл)…»
function itemsSummary(items, limit = 3) {
  const list = items ?? []
  const shown = list
    .slice(0, limit)
    .map((item) => `${item.product_name} (${item.qty} ${unitFor(item.product_name)})`)
  const rest = list.length - shown.length
  return { text: shown.join(', '), rest }
}

export default function OrderCard({ order, busy, onStatus }) {
  const [menuOpen, setMenuOpen] = useState(false)
  const menuRef = useRef(null)

  useEffect(() => {
    if (!menuOpen) return undefined
    const onClick = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setMenuOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [menuOpen])

  const meta = statusMeta(order.status)
  const primary = PRIMARY_ACTION[order.status]
  const summary = itemsSummary(order.items)
  const phoneHref = order.phone ? `tel:${order.phone.replace(/[^\d+]/g, '')}` : null

  // В меню — все статусы, кроме текущего и кроме тех, что вынесены
  // на отдельные кнопки.
  const menuStatuses = STATUS_OPTIONS.filter(
    ([value]) => value !== order.status && value !== 'rejected',
  )

  return (
    <article data-testid="admin-order" className="card p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="flex flex-wrap items-center gap-2 font-semibold text-gray-900">
            <span data-testid="admin-order-number">{order.order_number}</span>
            <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${meta.badge}`}>
              {meta.label}
            </span>
            {order.is_night_order ? (
              <span
                data-testid="admin-order-priority"
                className="rounded-full bg-orange-100 px-2 py-0.5 text-xs font-semibold text-accent-strong"
                title="Заказ в нерабочее время (20:00–08:00) — в приоритете"
              >
                🌙 приоритет
              </span>
            ) : null}
          </p>

          <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-gray-600">
            <span>{order.customer_name}</span>
            {phoneHref ? (
              <a
                href={phoneHref}
                data-testid="admin-order-phone"
                className="inline-flex items-center gap-1 font-medium text-accent-strong hover:underline"
              >
                <IconPhone className="h-3.5 w-3.5" />
                {order.phone}
              </a>
            ) : null}
            {order.telegram ? (
              <span className="text-xs text-gray-400">@{order.telegram}</span>
            ) : null}
          </p>

          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-gray-500">
            {order.car_make || order.car_model ? (
              <span className="inline-flex items-center gap-1">
                <IconCar className="h-3.5 w-3.5 text-gray-400" />
                {[order.car_make, order.car_model].filter(Boolean).join(' ')}
                {order.vin ? ` · VIN ${order.vin}` : ''}
              </span>
            ) : (
              <span>Авто не указано</span>
            )}
            <span>
              {order.pickup_method === 'delivery'
                ? `Доставка${order.address ? ` (${order.address})` : ''}`
                : 'Самовывоз'}
            </span>
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
              ? ` · обновлён ${new Date(order.updated_at).toLocaleString('ru-RU', {
                  day: '2-digit',
                  month: '2-digit',
                  hour: '2-digit',
                  minute: '2-digit',
                })}`
              : ''}
          </p>

          {/* Состав заказа — сразу в карточке, без раскрытия */}
          {order.items?.length ? (
            <p
              data-testid="admin-order-items"
              className="mt-2 rounded-lg bg-gray-50 px-3 py-2 text-xs leading-relaxed text-gray-600"
            >
              {summary.text}
              {summary.rest > 0 ? ` и ещё ${summary.rest}…` : ''}
            </p>
          ) : null}

          {order.comment ? (
            <p className="mt-1.5 rounded-lg bg-orange-50 px-3 py-2 text-xs text-gray-700">
              {order.comment}
            </p>
          ) : null}
        </div>

        <p className="shrink-0 text-lg font-bold text-gray-900">
          {formatPrice(order.total)}
        </p>
      </div>

      {/* Действия: одна главная кнопка, отклонение и меню остальных */}
      <div className="mt-3 flex flex-wrap items-center gap-2 border-t border-gray-100 pt-3">
        {primary ? (
          <button
            type="button"
            data-testid={`order-primary-${order.status}`}
            disabled={busy}
            onClick={() => onStatus(order, primary.status)}
            className="btn-primary disabled:cursor-not-allowed disabled:opacity-60"
          >
            {primary.label}
          </button>
        ) : null}

        {order.status !== 'rejected' && order.status !== 'cancelled' ? (
          <button
            type="button"
            data-testid="order-reject"
            disabled={busy}
            onClick={() => onStatus(order, 'rejected')}
            className="rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs font-semibold text-gray-500 transition hover:border-red-200 hover:bg-red-50 hover:text-red-600 disabled:cursor-not-allowed disabled:opacity-60"
          >
            Отклонить
          </button>
        ) : null}

        <div className="relative" ref={menuRef}>
          <button
            type="button"
            data-testid="order-more-status"
            aria-label="Другие статусы"
            aria-expanded={menuOpen}
            disabled={busy}
            onClick={() => setMenuOpen((value) => !value)}
            className="flex h-9 w-9 items-center justify-center rounded-xl border border-gray-200 bg-white text-gray-500 transition hover:bg-gray-50 hover:text-gray-700 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <IconMore className="h-4 w-4" />
          </button>
          {menuOpen ? (
            <div
              data-testid="order-status-menu"
              className="absolute bottom-full right-0 z-20 mb-1 w-44 rounded-xl border border-gray-200 bg-white p-1.5 shadow-lg"
            >
              {menuStatuses.map(([value, title]) => (
                <button
                  key={value}
                  type="button"
                  data-testid={`order-status-${value}`}
                  onClick={() => {
                    setMenuOpen(false)
                    onStatus(order, value)
                  }}
                  className="block w-full rounded-lg px-2.5 py-1.5 text-left text-sm text-gray-700 transition hover:bg-gray-50"
                >
                  {title}
                </button>
              ))}
            </div>
          ) : null}
        </div>
      </div>

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
  )
}
