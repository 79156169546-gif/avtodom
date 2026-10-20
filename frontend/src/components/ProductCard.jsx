import { formatPrice, discountFor } from '../lib/format.js'

const CATEGORY_ICONS = {
  'Тормоза': '🛞',
  'Масло и жидкости': '🛢️',
  'Фильтры': '🔩',
  'Свечи': '⚡',
  'Электро': '🔋',
  'Двигатель': '⚙️',
  'Кузов': '🚗',
  'Подвеска': '🔧',
}

// Сортировки каталога.
export const SORTS = [
  { id: 'popular', title: 'По популярности' },
  { id: 'price_asc', title: 'Сначала дешевле' },
  { id: 'price_desc', title: 'Сначала дороже' },
  { id: 'discount', title: 'По скидке' },
  { id: 'name', title: 'По названию' },
]

export function sortProducts(items, sortId) {
  const list = [...items]
  switch (sortId) {
    case 'price_asc':
      return list.sort((a, b) => Number(a.price) - Number(b.price))
    case 'price_desc':
      return list.sort((a, b) => Number(b.price) - Number(a.price))
    case 'discount':
      return list.sort(
        (a, b) =>
          discountFor(b) - discountFor(a) ||
          Number(a.price) - Number(b.price),
      )
    case 'name':
      return list.sort((a, b) => a.name.localeCompare(b.name, 'ru'))
    default:
      // По популярности: сначала в наличии, потом со скидкой, дешевле вперёд.
      return list.sort(
        (a, b) =>
          Number(b.in_stock) - Number(a.in_stock) ||
          discountFor(b) - discountFor(a) ||
          Number(a.price) - Number(b.price),
      )
  }
}

export default function ProductCard({ product, qty, onAdd, onIncrement, onDecrement }) {
  const icon = CATEGORY_ICONS[product.category] ?? '🔩'
  const discount = discountFor(product)
  // Деталь под заказ: её заказываем у поставщика, ждём order_days дней.
  const onOrder = product.is_on_order && !product.in_stock

  return (
    <article
      data-testid="product-card"
      data-sku={product.sku}
      data-on-order={onOrder ? 'true' : 'false'}
      className="card flex scroll-mb-28 flex-col gap-3 p-4 transition hover:shadow-md"
    >
      <div className="flex gap-3">
        <div className="flex h-16 w-16 shrink-0 items-center justify-center rounded-xl bg-orange-50 text-2xl">
          {icon}
        </div>
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
            {product.category}
          </p>
          <h3 className="mt-0.5 truncate text-[15px] font-semibold text-gray-900">
            {product.name}
          </h3>
          <p className="mt-0.5 truncate text-sm text-gray-500">
            {product.brand}
            {product.description ? ` · ${product.description}` : ''}
          </p>
          {onOrder ? (
            <p
              data-testid="product-on-order-badge"
              className="mt-1.5 inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-700"
            >
              ⏳ Под заказ · {product.order_days} дн.
            </p>
          ) : null}
        </div>
      </div>

      <div className="mt-auto flex items-end justify-between gap-3">
        <div>
          <div className="flex items-baseline gap-2">
            <span className="text-lg font-bold text-gray-900">
              {formatPrice(product.price)}
            </span>
            {product.old_price && discount ? (
              <span className="text-sm text-gray-400 line-through">
                {formatPrice(product.old_price)}
              </span>
            ) : null}
          </div>
          {discount ? (
            <span className="mt-0.5 inline-block rounded-full bg-orange-50 px-2 py-0.5 text-xs font-semibold text-accent-strong">
              −{discount}%
            </span>
          ) : null}
          {onOrder ? (
            <span className="mt-0.5 block text-[11px] leading-tight text-gray-400">
              Закажем у поставщика, срок ≈ {product.order_days} дн.
            </span>
          ) : null}
        </div>

        {product.in_stock || onOrder ? (
          qty > 0 ? (
            <div
              data-testid="qty-stepper"
              className="flex items-center gap-1 rounded-xl border border-gray-200 bg-gray-50 p-1"
            >
              <button
                type="button"
                onClick={() => onDecrement(product.id)}
                className="h-8 w-8 rounded-lg text-lg font-bold text-gray-600 transition hover:bg-white"
                aria-label={`Убрать один ${product.name}`}
              >
                −
              </button>
              <span
                data-testid="qty-value"
                className="min-w-[1.5rem] text-center text-sm font-semibold text-gray-900"
              >
                {qty}
              </span>
              <button
                type="button"
                onClick={() => onIncrement(product.id)}
                className="h-8 w-8 rounded-lg text-lg font-bold text-accent-strong transition hover:bg-white"
                aria-label={`Добавить ещё ${product.name}`}
              >
                +
              </button>
            </div>
          ) : (
            <button
              type="button"
              data-testid="add-to-cart"
              onClick={() => onAdd(product.id)}
              className="btn-secondary whitespace-nowrap"
            >
              {onOrder ? 'Под заказ' : 'В корзину'}
            </button>
          )
        ) : (
          <span className="rounded-full bg-gray-100 px-3 py-1.5 text-xs font-medium text-gray-500">
            Нет в наличии
          </span>
        )}
      </div>
    </article>
  )
}
