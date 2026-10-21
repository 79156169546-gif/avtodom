// Логика каталога: фильтры, совместимость с авто, форматирование.
//
// Вынесено отдельно от компонентов, чтобы правила фильтрации можно было
// проверить тестами и переиспользовать в карточке товара.

import { discountFor } from './format.js'

// Нормализация строки для поиска: без пробелов, тире и регистра.
export function normalize(value) {
  return (value ?? '')
    .toLowerCase()
    .replace(/[^a-zа-яё0-9]/gi, '')
}

// Режимы поиска из табов над строкой поиска.
export const SEARCH_MODES = [
  { id: 'name', title: 'По названию', placeholder: 'Название детали, например «колодки»' },
  { id: 'vin', title: 'По VIN', placeholder: 'VIN из 17 символов, например X7LRSM5X4K123456' },
  { id: 'sku', title: 'По артикулу', placeholder: 'Артикул, например BRK-001' },
]

export function matchesQuery(product, query, mode = 'name') {
  const needle = normalize(query)
  if (!needle) return true

  if (mode === 'sku') {
    return normalize(product.sku).includes(needle)
  }

  if (mode === 'vin') {
    // В режиме VIN запрос не текстовый: каталог отбирается по авто,
    // декодированному из самого номера (см. fitsCar).
    return true
  }

  return [product.name, product.brand, product.category, product.description]
    .map(normalize)
    .some((value) => value.includes(needle))
}

// Совместимость детали с выбранным автомобилем.
//
// Пустой список совместимости = деталь универсальная (подходит ко всем).
// Иначе марка, модель и год должны совпасть.
export function fitsCar(compatibility, car) {
  if (!car || (!car.make && !car.model && !car.year)) return true
  const list = compatibility ?? []
  if (list.length === 0) return true

  const wantMake = (car.make ?? '').trim().toUpperCase()
  const wantModel = (car.model ?? '').trim().toUpperCase()
  const wantYear = car.year ? Number(car.year) : null

  return list.some((item) => {
    if (wantMake && (item.make ?? '').toUpperCase() !== wantMake) return false
    if (wantModel) {
      const itemModel = (item.model ?? '').toUpperCase()
      if (itemModel && itemModel !== wantModel) return false
    }
    if (wantYear !== null) {
      if (item.year_from != null && wantYear < item.year_from) return false
      if (item.year_to != null && wantYear > item.year_to) return false
    }
    return true
  })
}

// Подпись совместимости для карточки: «KIA Rio (2011-2017)».
export function formatFitment(item) {
  if (!item) return ''
  const make = item.make ?? ''
  const model = item.model ? ` ${item.model}` : ''
  if (item.year_from && item.year_to) {
    return `${make}${model} (${item.year_from}-${item.year_to})`
  }
  if (item.year_from) return `${make}${model} (с ${item.year_from})`
  if (item.year_to) return `${make}${model} (до ${item.year_to})`
  return `${make}${model}`
}

// Короткий список совместимости для карточки: первая запись + счётчик.
export function fitmentSummary(compatibility) {
  const list = compatibility ?? []
  if (list.length === 0) return { text: 'Подходит для любых авто', extra: 0 }
  return {
    text: formatFitment(list[0]),
    extra: list.length - 1,
  }
}

// Текст «Арт. BR-1234» из артикула.
export function formatSku(sku) {
  if (!sku) return ''
  return `Арт. ${sku}`
}

// Диапазон цен каталога — границы слайдера.
export function priceBounds(products) {
  const prices = products.map((item) => Number(item.price) || 0).filter((value) => value > 0)
  if (prices.length === 0) return { min: 0, max: 0 }
  const min = Math.floor(Math.min(...prices))
  const max = Math.ceil(Math.max(...prices))
  // Круглые границы — слайдер в 0/100/500/1000 шаг выглядит аккуратнее.
  const step = max - min > 2000 ? 1000 : max - min > 500 ? 500 : 100
  return {
    min: Math.floor(min / step) * step,
    max: Math.ceil(max / step) * step,
    step,
  }
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
