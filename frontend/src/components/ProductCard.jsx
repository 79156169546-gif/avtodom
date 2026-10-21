import { discountFor, formatPrice, pluralize } from '../lib/format.js'
import { fitmentSummary, formatSku } from '../lib/catalog.js'
import {
  IconCar,
  IconCheck,
  IconMinus,
  IconPlus,
  IconTag,
  categoryIcon,
} from './icons.jsx'

// Каталог живёт без фотографий товаров, поэтому карточка строится на тексте
// и векторной иконке категории. Порядок блоков: что это (категория, название,
// бренд) -> подойдёт ли (совместимость, артикул, наличие) -> цена и действие.

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
  const Icon = categoryIcon(product.category)
  const discount = discountFor(product)
  // Деталь под заказ: её заказываем у поставщика, ждём order_days дней.
  const onOrder = product.is_on_order && !product.in_stock
  const fit = fitmentSummary(product.compatibility)
  const days = Number(product.order_days) || 0

  return (
    <article
      data-testid="product-card"
      data-sku={product.sku}
      data-on-order={onOrder ? 'true' : 'false'}
      className="card flex scroll-mb-28 flex-col gap-3 p-4 transition hover:shadow-md"
    >
      {/* Категория: иконка в светло-оранжевом квадрате + подпись */}
      <div className="flex items-center gap-2.5">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent-soft text-accent-strong">
          <Icon className="h-5 w-5" />
        </span>
        <span className="truncate text-[11px] font-semibold uppercase tracking-wider text-gray-400">
          {product.category ?? 'Запчасть'}
        </span>
      </div>

      {/* Название — до двух строк */}
      <h3 className="line-clamp-2 text-[15px] font-bold leading-snug text-gray-900">
        {product.name}
      </h3>

      {/* Бренд и совместимость */}
      <div className="space-y-1">
        {product.brand ? (
          <p className="text-sm font-medium text-gray-500">{product.brand}</p>
        ) : null}
        <p className="flex items-start gap-1.5 text-xs leading-snug text-gray-500">
          <IconCar className="mt-px h-3.5 w-3.5 shrink-0 text-gray-400" />
          <span>
            Подходит для:{' '}
            <span className="font-medium text-gray-700">{fit.text}</span>
            {fit.extra > 0 ? (
              <span className="text-gray-400"> и ещё {fit.extra}</span>
            ) : null}
          </span>
        </p>
        {product.sku ? (
          <p className="flex items-center gap-1.5 text-[11px] text-gray-400">
            <IconTag className="h-3 w-3 shrink-0" />
            {formatSku(product.sku)}
          </p>
        ) : null}
      </div>

      {/* Наличие */}
      {onOrder ? (
        <span
          data-testid="product-on-order-badge"
          className="inline-flex w-fit items-center gap-1.5 rounded-full bg-orange-50 px-2.5 py-1 text-[11px] font-semibold text-orange-700"
        >
          Под заказ ({days} {pluralize(days, 'день', 'дня', 'дней')})
        </span>
      ) : product.in_stock ? (
        <span className="inline-flex w-fit items-center gap-1.5 rounded-full bg-emerald-50 px-2.5 py-1 text-[11px] font-semibold text-emerald-700">
          <IconCheck className="h-3.5 w-3.5" />
          В наличии
        </span>
      ) : (
        <span className="inline-flex w-fit items-center rounded-full bg-gray-100 px-2.5 py-1 text-[11px] font-semibold text-gray-500">
          Нет в наличии
        </span>
      )}

      {/* Цена и действие — прижаты к низу карточки */}
      <div className="mt-auto space-y-3 pt-1">
        <div className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
          <span className="text-xl font-bold text-gray-900">
            {formatPrice(product.price)}
          </span>
          {product.old_price && discount ? (
            <span className="text-sm text-gray-400 line-through">
              {formatPrice(product.old_price)}
            </span>
          ) : null}
          {discount ? (
            <span className="rounded-full bg-red-50 px-2 py-0.5 text-xs font-bold text-red-600">
              −{discount}%
            </span>
          ) : null}
        </div>

        {product.in_stock || onOrder ? (
          qty > 0 ? (
            <div
              data-testid="qty-stepper"
              className="flex items-center justify-between rounded-xl border border-gray-200 bg-gray-50 p-1"
            >
              <button
                type="button"
                onClick={() => onDecrement(product.id)}
                className="flex h-9 w-9 items-center justify-center rounded-lg text-gray-600 transition hover:bg-white"
                aria-label={`Убрать один ${product.name}`}
              >
                <IconMinus className="h-4 w-4" />
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
                className="flex h-9 w-9 items-center justify-center rounded-lg text-accent-strong transition hover:bg-white"
                aria-label={`Добавить ещё ${product.name}`}
              >
                <IconPlus className="h-4 w-4" />
              </button>
            </div>
          ) : (
            <button
              type="button"
              data-testid="add-to-cart"
              onClick={() => onAdd(product.id)}
              className={
                onOrder
                  ? 'w-full rounded-xl border-2 border-accent bg-white px-4 py-2.5 text-sm font-semibold text-accent-strong transition hover:bg-orange-50 focus:outline-none focus:ring-2 focus:ring-orange-500'
                  : 'btn-primary w-full'
              }
            >
              {onOrder ? 'Заказать' : 'В корзину'}
            </button>
          )
        ) : null}
      </div>
    </article>
  )
}
