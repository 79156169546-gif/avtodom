import { useMemo, useState } from 'react'
import { formatPrice } from '../lib/format.js'
import {
  IconCheck,
  IconChevron,
  IconReset,
  IconSearch,
  IconSliders,
} from './icons.jsx'

// Блок фильтров каталога: аккордеоны «Марка», «Модель», «Бренд», «Цена»,
// «Наличие».
//
// Один и тот же блок используется и в боковой колонке на десктопе,
// и в выезжающей шторке на мобильных.
//
// Списки марок и моделей длинные, поэтому каждый ограничен по высоте
// (max-h-60 + скролл) и имеет поле поиска: клиент печатает «KIA»
// и не листает весь перечень.

// Сколько строк помещается в прокручиваемый список.
const LIST_MAX_HEIGHT = 'max-h-60'

// Поле поиска внутри списка.
function ListSearch({ value, onChange, placeholder, testid }) {
  return (
    <div className="relative mb-2">
      <span
        aria-hidden="true"
        className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400"
      >
        <IconSearch className="h-3.5 w-3.5" />
      </span>
      <input
        type="search"
        data-testid={testid}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        aria-label={placeholder}
        className="w-full rounded-lg border border-gray-200 bg-white py-1.5 pl-8 pr-2 text-xs text-gray-900 outline-none transition placeholder:text-gray-400 focus:border-accent focus:ring-1 focus:ring-orange-500"
      />
    </div>
  )
}

// Прокручиваемый список с чекбоксами.
function CheckList({ items, selected, onToggle, testidPrefix, emptyText }) {
  if (items.length === 0) {
    return (
      <p className="px-1 py-2 text-xs text-gray-400">
        {emptyText ?? 'Ничего не найдено'}
      </p>
    )
  }
  return (
    <div className={`${LIST_MAX_HEIGHT} overflow-y-auto pr-1`}>
      {items.map(([name, amount]) => {
        const checked = selected.includes(name)
        return (
          <label
            key={name}
            className="flex cursor-pointer items-center gap-2.5 rounded-lg px-1.5 py-1.5 transition hover:bg-gray-50"
          >
            <span
              className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border transition ${
                checked
                  ? 'border-accent-strong bg-accent-strong text-white'
                  : 'border-gray-300 bg-white'
              }`}
            >
              {checked ? <IconCheck className="h-3 w-3" /> : null}
            </span>
            <input
              type="checkbox"
              data-testid={`${testidPrefix}-${name}`}
              checked={checked}
              onChange={() => onToggle(name)}
              className="sr-only"
            />
            <span className="min-w-0 flex-1 truncate text-sm text-gray-700">
              {name}
            </span>
            {amount != null ? (
              <span className="shrink-0 text-xs text-gray-400">
                {amount > 0 ? amount : '—'}
              </span>
            ) : null}
          </label>
        )
      })}
    </div>
  )
}

export default function FilterPanel({
  makes,
  selectedMakes,
  onMakesChange,
  models,
  selectedModels,
  onModelsChange,
  brands,
  selectedBrands,
  onBrandsChange,
  price,
  onPriceChange,
  bounds,
  inStockOnly,
  onInStockChange,
  onOrderOnly,
  onOnOrderChange,
  onReset,
  activeCount,
  className = '',
}) {
  // Марка и Модель открыты сразу: клиент приходит за подбором по авто,
  // и списки прокручиваются, а не занимают всю страницу.
  const [openSections, setOpenSections] = useState(
    () => new Set(['make', 'model', 'brand', 'price', 'stock']),
  )
  const [makeQuery, setMakeQuery] = useState('')
  const [modelQuery, setModelQuery] = useState('')
  const [brandQuery, setBrandQuery] = useState('')

  const toggleSection = (id) =>
    setOpenSections((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  // Поиск по маркам и моделям — без учёта регистра и пробелов.
  const filteredMakes = useMemo(() => {
    const needle = makeQuery.trim().toLowerCase()
    if (!needle) return makes
    return makes.filter(([name]) => name.toLowerCase().includes(needle))
  }, [makes, makeQuery])

  const filteredBrands = useMemo(() => {
    const needle = brandQuery.trim().toLowerCase()
    if (!needle) return brands
    return brands.filter(([name]) => name.toLowerCase().includes(needle))
  }, [brands, brandQuery])

  const filteredModels = useMemo(() => {
    const needle = modelQuery.trim().toLowerCase()
    if (!needle) return models
    return models.filter(([name]) => name.toLowerCase().includes(needle))
  }, [models, modelQuery])

  const toggle = (list, onChange) => (name) => {
    const next = list.includes(name)
      ? list.filter((item) => item !== name)
      : [...list, name]
    onChange(next)
  }

  const section = (id, title, content, badge = null) => {
    const isOpen = openSections.has(id)
    return (
      <div className="border-b border-gray-100 last:border-b-0">
        <button
          type="button"
          data-testid={`filter-section-${id}`}
          aria-expanded={isOpen}
          onClick={() => toggleSection(id)}
          className="flex w-full items-center justify-between gap-2 py-3 text-left"
        >
          <span className="flex items-center gap-2 text-sm font-semibold text-gray-900">
            {title}
            {badge ? (
              <span className="rounded-full bg-accent-soft px-1.5 py-0.5 text-[10px] font-bold text-accent-strong">
                {badge}
              </span>
            ) : null}
          </span>
          <IconChevron
            className={`h-4 w-4 shrink-0 text-gray-400 transition ${
              isOpen ? 'rotate-180' : ''
            }`}
          />
        </button>
        {isOpen ? <div className="pb-3.5">{content}</div> : null}
      </div>
    )
  }

  const pricePercent = (value) => {
    const span = bounds.max - bounds.min
    if (span <= 0) return 0
    return Math.min(100, Math.max(0, ((value - bounds.min) / span) * 100))
  }

  return (
    <div data-testid="catalog-filters" className={`card p-4 ${className}`}>
      <div className="mb-1 flex items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm font-semibold text-gray-900">
          <IconSliders className="h-4 w-4 text-gray-400" />
          Фильтры
        </p>
        {activeCount > 0 ? (
          <button
            type="button"
            data-testid="catalog-filters-reset"
            onClick={onReset}
            className="flex items-center gap-1 text-xs font-semibold text-accent-strong hover:underline"
          >
            <IconReset className="h-3.5 w-3.5" />
            Сбросить ({activeCount})
          </button>
        ) : null}
      </div>

      {section(
        'make',
        'Марка',
        <div>
          <ListSearch
            value={makeQuery}
            onChange={setMakeQuery}
            placeholder="Найти марку"
            testid="catalog-make-search"
          />
          <CheckList
            items={filteredMakes}
            selected={selectedMakes}
            onToggle={toggle(selectedMakes, onMakesChange)}
            testidPrefix="catalog-make"
            emptyText="Марки не найдены"
          />
        </div>,
        selectedMakes.length || null,
      )}

      {section(
        'model',
        'Модель',
        <div>
          <ListSearch
            value={modelQuery}
            onChange={setModelQuery}
            placeholder="Найти модель"
            testid="catalog-model-search"
          />
          <CheckList
            items={filteredModels}
            selected={selectedModels}
            onToggle={toggle(selectedModels, onModelsChange)}
            testidPrefix="catalog-model"
            emptyText={
              selectedMakes.length === 0
                ? 'Сначала выберите марку — покажем её модели'
                : 'Модели не найдены'
            }
          />
        </div>,
        selectedModels.length || null,
      )}

      {section(
        'brand',
        'Бренд',
        <div>
          <ListSearch
            value={brandQuery}
            onChange={setBrandQuery}
            placeholder="Найти бренд"
            testid="catalog-brand-search"
          />
          <CheckList
            items={filteredBrands}
            selected={selectedBrands}
            onToggle={toggle(selectedBrands, onBrandsChange)}
            testidPrefix="catalog-brand"
            emptyText="Бренды не найдены"
          />
        </div>,
        selectedBrands.length || null,
      )}

      {section(
        'price',
        'Цена',
        <div>
          <div className="mb-2 flex items-center justify-between text-xs text-gray-500">
            <span data-testid="catalog-price-min-label">
              {formatPrice(price.min)}
            </span>
            <span data-testid="catalog-price-max-label">
              {formatPrice(price.max)}
            </span>
          </div>
          <div className="relative h-6">
            <div className="absolute inset-x-0 top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-gray-200" />
            <div
              className="absolute top-1/2 h-1.5 -translate-y-1/2 rounded-full bg-accent-strong"
              style={{
                left: `${pricePercent(price.min)}%`,
                right: `${100 - pricePercent(price.max)}%`,
              }}
            />
            <input
              type="range"
              data-testid="catalog-price-min"
              min={bounds.min}
              max={bounds.max}
              step={bounds.step}
              value={price.min}
              onChange={(event) => {
                const value = Math.min(Number(event.target.value), price.max)
                onPriceChange({ ...price, min: value })
              }}
              className="range-slider absolute inset-x-0 top-1/2 h-6 w-full -translate-y-1/2"
              aria-label="Цена от"
            />
            <input
              type="range"
              data-testid="catalog-price-max"
              min={bounds.min}
              max={bounds.max}
              step={bounds.step}
              value={price.max}
              onChange={(event) => {
                const value = Math.max(Number(event.target.value), price.min)
                onPriceChange({ ...price, max: value })
              }}
              className="range-slider absolute inset-x-0 top-1/2 h-6 w-full -translate-y-1/2"
              aria-label="Цена до"
            />
          </div>
        </div>,
        price.min > bounds.min || price.max < bounds.max ? '•' : null,
      )}

      {section(
        'stock',
        'Наличие',
        <div className="space-y-1.5">
          <Toggle
            id="catalog-filter-stock"
            label="В наличии"
            checked={inStockOnly}
            onChange={onInStockChange}
          />
          <Toggle
            id="catalog-filter-order"
            label="Под заказ"
            checked={onOrderOnly}
            onChange={onOnOrderChange}
          />
        </div>,
        inStockOnly || onOrderOnly ? '•' : null,
      )}
    </div>
  )
}

function Toggle({ id, label, checked, onChange }) {
  return (
    // Без htmlFor: input уже вложен в label, иначе клик по самому
    // input'у переключает его дважды (label перенаправляет активацию).
    <label className="flex cursor-pointer items-center justify-between gap-3 rounded-lg px-1.5 py-1.5 transition hover:bg-gray-50">
      <span className="text-sm text-gray-700">{label}</span>
      <span className="relative inline-flex">
        <input
          id={id}
          type="checkbox"
          data-testid={id}
          checked={checked}
          onChange={(event) => onChange(event.target.checked)}
          className="peer sr-only"
        />
        <span className="h-5 w-9 rounded-full bg-gray-200 transition peer-checked:bg-accent-strong peer-focus-visible:ring-2 peer-focus-visible:ring-orange-500" />
        <span className="absolute left-0.5 top-0.5 h-4 w-4 rounded-full bg-white shadow transition peer-checked:translate-x-4" />
      </span>
    </label>
  )
}
