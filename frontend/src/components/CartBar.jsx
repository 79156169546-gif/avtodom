import { formatPrice } from '../lib/format.js'

// Sticky bottom bar: слева «Итого: X», справа большая оранжевая кнопка.
export default function CartBar({ total, count, onCheckout, disabled }) {
  return (
    <div
      data-testid="cart-bar"
      className="fixed inset-x-0 bottom-0 z-30 border-t border-gray-200 bg-white/95 shadow-bar backdrop-blur"
    >
      <div className="mx-auto flex max-w-3xl items-center gap-3 px-4 py-3 pb-safe sm:px-6">
        <div className="min-w-0 flex-1">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-400">
            Итого
          </p>
          <p data-testid="cart-total" className="text-xl font-bold text-gray-900">
            {formatPrice(total)}
          </p>
          {count > 0 ? (
            <p className="truncate text-xs text-gray-500">{count} позиций в корзине</p>
          ) : (
            <p className="truncate text-xs text-gray-400">
              Добавьте товары, чтобы оформить заказ
            </p>
          )}
        </div>
        <button
          type="button"
          data-testid="checkout-button"
          onClick={onCheckout}
          disabled={disabled}
          className="btn-primary h-12 shrink-0 px-6 text-base"
        >
          Оформить заказ
        </button>
      </div>
    </div>
  )
}
