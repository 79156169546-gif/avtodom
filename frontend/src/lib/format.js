export function formatPrice(value) {
  const amount = Number(value ?? 0)
  return `${amount.toLocaleString('ru-RU', { maximumFractionDigits: 0 })} ₽`
}

export function pluralize(count, one, few, many) {
  const mod10 = count % 10
  const mod100 = count % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}

export function pluralItems(count) {
  return `${count} ${pluralize(count, 'товар', 'товара', 'товаров')}`
}

// Процент скидки: приоритет у discount_percent, иначе считаем от old_price.
export function discountFor(product) {
  const explicit = Number(product.discount_percent ?? 0)
  if (explicit > 0) return explicit
  const price = Number(product.price ?? 0)
  const oldPrice = Number(product.old_price ?? 0)
  if (oldPrice > price && price > 0) {
    return Math.round((1 - price / oldPrice) * 100)
  }
  return 0
}

// Статусы заказа: ключ -> { label, классы Tailwind, описание для клиента }
export const ORDER_STATUS = {
  new: {
    label: 'Новый',
    badge: 'bg-orange-50 text-accent-strong',
    description: 'Заказ отправлен, менеджер скоро свяжется',
  },
  accepted: {
    label: 'Принят',
    badge: 'bg-blue-50 text-blue-700',
    description: 'Менеджер принял заказ в работу',
  },
  in_progress: {
    label: 'В работе',
    badge: 'bg-amber-50 text-amber-700',
    description: 'Детали собираются',
  },
  ready: {
    label: 'Готов',
    badge: 'bg-emerald-50 text-emerald-700',
    description: 'Заказ готов к выдаче или доставке',
  },
  completed: {
    label: 'Выполнен',
    badge: 'bg-emerald-100 text-emerald-800',
    description: 'Заказ выдан клиенту',
  },
  rejected: {
    label: 'Отклонён',
    badge: 'bg-red-50 text-red-700',
    description: 'Менеджер отклонил заказ',
  },
  cancelled: {
    label: 'Отменён',
    badge: 'bg-gray-100 text-gray-600',
    description: 'Заказ отменён',
  },
}

export function statusMeta(status) {
  return (
    ORDER_STATUS[status] || {
      label: status,
      badge: 'bg-gray-100 text-gray-600',
      description: '',
    }
  )
}

// Порядок статусов в таймлайне
export const STATUS_FLOW = [
  'new',
  'accepted',
  'in_progress',
  'ready',
  'completed',
]
