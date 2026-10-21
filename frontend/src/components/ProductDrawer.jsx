import { useEffect, useState } from 'react'
import { formatPrice } from '../lib/format.js'
import CompatibilityPicker from './CompatibilityPicker.jsx'
import Switch from './Switch.jsx'
import { IconBox, IconClose, IconEye, IconPencil, IconPlus } from './icons.jsx'

// Форма товара: добавление и редактирование.
//
// Лежит в боковой выезжающей панели, чтобы не занимать весь экран:
// в каталоге важна таблица, а форма — редкая операция.

export const EMPTY_PRODUCT = {
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
  compatibility: [],
}

// Приводим товар из API к состоянию формы.
export function productToForm(product) {
  if (!product) return EMPTY_PRODUCT
  return {
    sku: product.sku ?? '',
    name: product.name ?? '',
    brand: product.brand ?? '',
    category: product.category ?? '',
    price: String(product.price ?? ''),
    old_price: product.old_price ? String(product.old_price) : '',
    discount_percent: product.discount_percent ?? 0,
    in_stock: Boolean(product.in_stock),
    is_active: Boolean(product.is_active),
    is_on_order: Boolean(product.is_on_order),
    order_days: product.order_days ?? 3,
    description: product.description ?? '',
    compatibility: (product.compatibility ?? []).map((item) => ({
      make: item.make,
      model: item.model ?? null,
      year_from: item.year_from ?? null,
      year_to: item.year_to ?? null,
    })),
  }
}

// Форма -> payload для API.
export function formToPayload(form) {
  return {
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
    compatibility: form.compatibility ?? [],
  }
}

export default function ProductDrawer({ open, product, busy, onClose, onSubmit }) {
  const [form, setForm] = useState(EMPTY_PRODUCT)

  useEffect(() => {
    if (open) setForm(productToForm(product))
  }, [open, product])

  // Esc закрывает панель — привычно для владельца.
  useEffect(() => {
    if (!open) return undefined
    const onKey = (event) => {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  const set = (patch) => setForm((prev) => ({ ...prev, ...patch }))

  if (!open) return null

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true">
      <button
        type="button"
        aria-label="Закрыть форму"
        data-testid="product-drawer-backdrop"
        onClick={onClose}
        className="absolute inset-0 bg-gray-900/40"
      />
      <div
        data-testid="product-drawer"
        className="absolute inset-y-0 right-0 flex w-full max-w-lg flex-col bg-gray-50 shadow-2xl"
      >
        <div className="flex items-center justify-between border-b border-gray-200 bg-white px-4 py-3">
          <h2 className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            {product ? (
              <IconPencil className="h-4 w-4 text-gray-400" />
            ) : (
              <IconPlus className="h-4 w-4 text-gray-400" />
            )}
            {product ? `Редактирование: ${product.sku}` : 'Новый товар'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Закрыть"
            className="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
          >
            <IconClose className="h-5 w-5" />
          </button>
        </div>

        <form
          onSubmit={(event) => {
            event.preventDefault()
            onSubmit(formToPayload(form))
          }}
          className="flex-1 space-y-4 overflow-y-auto p-4"
        >
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Артикул</label>
              <input
                data-testid="product-sku"
                required
                className="field"
                value={form.sku}
                onChange={(event) => set({ sku: event.target.value })}
              />
            </div>
            <div>
              <label className="label">Название</label>
              <input
                data-testid="product-name"
                required
                className="field"
                value={form.name}
                onChange={(event) => set({ name: event.target.value })}
              />
            </div>
            <div>
              <label className="label">Бренд</label>
              <input
                className="field"
                value={form.brand}
                onChange={(event) => set({ brand: event.target.value })}
              />
            </div>
            <div>
              <label className="label">Категория</label>
              <input
                className="field"
                value={form.category}
                onChange={(event) => set({ category: event.target.value })}
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
                onChange={(event) => set({ price: event.target.value })}
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
                onChange={(event) => set({ old_price: event.target.value })}
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
                onChange={(event) => set({ discount_percent: event.target.value })}
              />
            </div>
          </div>

          <div className="space-y-2 rounded-xl border border-gray-200 bg-white p-3">
            <Switch
              testId="product-in-stock"
              label="В наличии"
              checked={form.in_stock}
              onChange={(value) =>
                // Деталь в наличии не может быть «под заказ».
                set({ in_stock: value, is_on_order: value ? false : form.is_on_order })
              }
            />
            <Switch
              testId="product-on-order"
              label="Под заказ"
              checked={form.is_on_order}
              onChange={(value) =>
                // Под заказ — значит в наличии её нет.
                set({ is_on_order: value, in_stock: value ? false : form.in_stock })
              }
            />
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
                  onChange={(event) => set({ order_days: event.target.value })}
                />
                <p className="mt-1.5 text-xs text-gray-400">
                  Покажем клиенту на витрине и в подтверждении заказа.
                </p>
              </div>
            ) : null}
            <Switch
              testId="product-is-active"
              label="Показывать на витрине"
              checked={form.is_active}
              onChange={(value) => set({ is_active: value })}
            />
          </div>

          <div>
            <label className="label">Описание</label>
            <textarea
              rows={2}
              className="field resize-none"
              value={form.description}
              onChange={(event) => set({ description: event.target.value })}
            />
          </div>

          <div>
            <span className="label">Подходит для авто</span>
            <CompatibilityPicker
              testId="product-compatibility"
              value={form.compatibility}
              onChange={(value) => set({ compatibility: value })}
            />
          </div>

          <div className="sticky bottom-0 -mx-4 border-t border-gray-200 bg-white px-4 py-3">
            <button
              type="submit"
              data-testid="product-save"
              className="btn-primary w-full"
              disabled={busy}
            >
              {product ? 'Сохранить изменения' : 'Добавить товар'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Строка таблицы каталога.
export function ProductRow({ product, busy, onToggleStock, onToggleOnOrder, onDaysChange, onEdit, onToggleActive }) {
  return (
    <tr
      data-testid="admin-product"
      data-sku={product.sku}
      className={`border-b border-gray-100 last:border-b-0 ${
        product.is_active ? '' : 'opacity-60'
      }`}
    >
      <td className="px-3 py-2.5">
        <p className="truncate text-sm font-semibold text-gray-900">
          {product.name}
        </p>
        <p className="mt-0.5 flex items-center gap-2 text-xs text-gray-400">
          <span className="font-mono">{product.sku}</span>
          {product.brand ? <span>{product.brand}</span> : null}
          {product.category ? (
            <span className="rounded-full bg-gray-100 px-1.5 py-0.5">
              {product.category}
            </span>
          ) : null}
          {!product.is_active ? (
            <span className="rounded-full bg-gray-100 px-1.5 py-0.5 font-medium text-gray-500">
              скрыт
            </span>
          ) : null}
        </p>
      </td>
      <td className="whitespace-nowrap px-3 py-2.5">
        <span className="text-sm font-bold text-gray-900">
          {formatPrice(product.price)}
        </span>
        {product.old_price ? (
          <span className="ml-1.5 text-xs text-gray-400 line-through">
            {formatPrice(product.old_price)}
          </span>
        ) : null}
        {product.discount_percent ? (
          <span className="ml-1.5 rounded-full bg-red-50 px-1.5 py-0.5 text-[10px] font-bold text-red-600">
            −{product.discount_percent}%
          </span>
        ) : null}
      </td>
      <td className="px-3 py-2.5">
        <Switch
          size="sm"
          testId={`product-stock-${product.sku}`}
          checked={product.in_stock}
          disabled={busy}
          onChange={(value) => onToggleStock(product, value)}
        />
      </td>
      <td className="px-3 py-2.5">
        <div className="flex items-center gap-2">
          <Switch
            size="sm"
            tone="blue"
            testId={`product-onorder-${product.sku}`}
            checked={product.is_on_order}
            disabled={busy}
            onChange={(value) => onToggleOnOrder(product, value)}
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
                if (days !== product.order_days) onDaysChange(product, days)
              }}
              className="w-16 rounded-lg border border-gray-200 px-2 py-1 text-xs outline-none focus:border-accent"
              aria-label="Срок поставки в днях"
            />
          ) : null}
        </div>
      </td>
      <td className="whitespace-nowrap px-3 py-2.5">
        <div className="flex items-center gap-1.5">
          <button
            type="button"
            data-testid={`product-edit-${product.sku}`}
            onClick={() => onEdit(product)}
            className="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700"
            aria-label={`Редактировать ${product.name}`}
          >
            <IconPencil className="h-4 w-4" />
          </button>
          <button
            type="button"
            data-testid={`product-active-${product.sku}`}
            onClick={() => onToggleActive(product)}
            disabled={busy}
            className="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-700 disabled:opacity-50"
            aria-label={product.is_active ? 'Скрыть товар' : 'Показать товар'}
            title={product.is_active ? 'Скрыть' : 'Показать'}
          >
            {product.is_active ? (
              <IconEye className="h-4 w-4" />
            ) : (
              <IconBox className="h-4 w-4" />
            )}
          </button>
        </div>
      </td>
    </tr>
  )
}
