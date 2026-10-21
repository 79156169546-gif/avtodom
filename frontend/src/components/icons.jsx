// Векторные иконки каталога.
//
// В карточках нет фотографий товаров, поэтому иконка категории — это
// единственный визуальный якорь. Поэтому рисуем её линиями (stroke),
// а не эмодзи: эмодзи зависят от шрифта системы и ломают «премиальный» вид.

const base = {
  fill: 'none',
  stroke: 'currentColor',
  strokeWidth: 1.6,
  strokeLinecap: 'round',
  strokeLinejoin: 'round',
}

function Svg({ children, className = 'h-5 w-5', viewBox = '0 0 24 24' }) {
  return (
    <svg
      viewBox={viewBox}
      className={className}
      aria-hidden="true"
      focusable="false"
      {...base}
    >
      {children}
    </svg>
  )
}

// --- иконки категорий ------------------------------------------------------

export function IconEngine(props) {
  return (
    <Svg {...props}>
      <path d="M3 10.5h18v7.5H3z" />
      <path d="M7 10.5V7.5h4.5v3" />
      <path d="M2 14h1.5M20.5 14H22" />
      <path d="M7 14h2M11 14h2" />
    </Svg>
  )
}

export function IconBrake(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <circle cx="12" cy="12" r="3" />
      <path d="M12 6.5v2M12 15.5v2M6.5 12h2M15.5 12h2" />
    </Svg>
  )
}

export function IconFilter(props) {
  return (
    <Svg {...props}>
      <path d="M3.5 5h17l-6.5 7.5V19l-4 2v-8.5z" />
    </Svg>
  )
}

export function IconSpark(props) {
  return (
    <Svg {...props}>
      <path d="M13.5 2.5 5 13.5h5.5L9 21.5 19 10h-6z" />
    </Svg>
  )
}

export function IconBattery(props) {
  return (
    <Svg {...props}>
      <rect x="2.5" y="7.5" width="15" height="9" rx="1.5" />
      <path d="M17.5 10.5h3.5v3h-3.5" />
      <path d="M6.5 10.5v3M10 10.5v3" />
    </Svg>
  )
}

export function IconOil(props) {
  return (
    <Svg {...props}>
      <path d="M12 3.2s6 6.6 6 10.4A6 6 0 0 1 6 13.6C6 9.8 12 3.2 12 3.2z" />
      <path d="M9.5 14.2a2.6 2.6 0 0 0 2.5 2.4" />
    </Svg>
  )
}

export function IconBody(props) {
  return (
    <Svg {...props}>
      <path d="M3 13.5 4.6 9a2 2 0 0 1 1.9-1.4h11a2 2 0 0 1 1.9 1.4l1.6 4.5" />
      <path d="M3 13.5h18V18H3z" />
      <circle cx="7.5" cy="18" r="1.9" />
      <circle cx="16.5" cy="18" r="1.9" />
    </Svg>
  )
}

export function IconSuspension(props) {
  return (
    <Svg {...props}>
      <path d="M12 2.5v3" />
      <path d="M8 5.5h8" />
      <path d="M9 5.5c3 1.6 3 2.9 0 4.5s-3 2.9 0 4.5 3 2.9 0 4.5" />
      <path d="M15 5.5c-3 1.6-3 2.9 0 4.5s3 2.9 0 4.5-3 2.9 0 4.5" />
    </Svg>
  )
}

// Справочник: категория из БД -> иконка. Ключи совпадают с products.category.
export const CATEGORY_ICONS = {
  'Двигатель': IconEngine,
  'Тормозная система': IconBrake,
  'Фильтры': IconFilter,
  'Электрика': IconBattery,
  'Масла и жидкости': IconOil,
  'Кузовные детали': IconBody,
  'Подвеска': IconSuspension,
  // Старые названия — товары могли остаться в базе после смены номенклатуры.
  'Тормоза': IconBrake,
  'Свечи': IconSpark,
  'Электро': IconBattery,
  'Масло и жидкости': IconOil,
  'Кузов': IconBody,
}

export const CATEGORY_FALLBACK = IconFilter

export function categoryIcon(category) {
  return CATEGORY_ICONS[category] ?? CATEGORY_FALLBACK
}

// --- служебные иконки ------------------------------------------------------

export function IconSearch(props) {
  return (
    <Svg {...props}>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m15.5 15.5 4.5 4.5" />
    </Svg>
  )
}

export function IconCar(props) {
  return (
    <Svg {...props}>
      <path d="M3.5 13.5 5 9.2A2 2 0 0 1 6.9 8h10.2A2 2 0 0 1 19 9.2l1.5 4.3" />
      <path d="M3.5 13.5h17V18h-17z" />
      <circle cx="7.5" cy="18" r="1.8" />
      <circle cx="16.5" cy="18" r="1.8" />
    </Svg>
  )
}

export function IconChevron(props) {
  return (
    <Svg {...props}>
      <path d="m6 9.5 6 6 6-6" />
    </Svg>
  )
}

export function IconCheck(props) {
  return (
    <Svg {...props}>
      <path d="m4.5 12.5 5 5 10-11" />
    </Svg>
  )
}

export function IconClose(props) {
  return (
    <Svg {...props}>
      <path d="m6 6 12 12M18 6 6 18" />
    </Svg>
  )
}

export function IconSliders(props) {
  return (
    <Svg {...props}>
      <path d="M4 7h10M18 7h2M4 17h4M12 17h8" />
      <circle cx="16" cy="7" r="2" />
      <circle cx="10" cy="17" r="2" />
    </Svg>
  )
}

export function IconTag(props) {
  return (
    <Svg {...props}>
      <path d="M11 3.5H20.5V13l-9 9-9.5-9.5z" />
      <circle cx="16.5" cy="7.5" r="1.4" />
    </Svg>
  )
}

export function IconClock(props) {
  return (
    <Svg {...props}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M12 7.5V12l3 2" />
    </Svg>
  )
}

export function IconPlus(props) {
  return (
    <Svg {...props}>
      <path d="M12 5v14M5 12h14" />
    </Svg>
  )
}

export function IconMinus(props) {
  return (
    <Svg {...props}>
      <path d="M5 12h14" />
    </Svg>
  )
}

export function IconReset(props) {
  return (
    <Svg {...props}>
      <path d="M4 5v5h5" />
      <path d="M4.8 10a7.5 7.5 0 1 1 .6 6.4" />
    </Svg>
  )
}

export function IconBox(props) {
  return (
    <Svg {...props}>
      <path d="M3.5 7.5 12 3.5l8.5 4v9L12 20.5 3.5 16.5z" />
      <path d="M3.5 7.5 12 11.5l8.5-4M12 11.5v9" />
    </Svg>
  )
}

// --- иконки админки -------------------------------------------------------

export function IconPhone(props) {
  return (
    <Svg {...props}>
      <path d="M5 3.5h3.5l1.5 4-2 1.5a12 12 0 0 0 5 5l1.5-2 4 1.5V18a2 2 0 0 1-2 2A15 15 0 0 1 3 5.5a2 2 0 0 1 2-2z" />
    </Svg>
  )
}

export function IconMore(props) {
  return (
    <Svg {...props}>
      <rect x="3.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="3.5" width="7" height="7" rx="1.5" />
      <rect x="3.5" y="13.5" width="7" height="7" rx="1.5" />
      <rect x="13.5" y="13.5" width="7" height="7" rx="1.5" />
    </Svg>
  )
}

export function IconPencil(props) {
  return (
    <Svg {...props}>
      <path d="M4 20h4L19 9a2.1 2.1 0 0 0-3-3L5 17z" />
      <path d="M14.5 6.5 17.5 9.5" />
    </Svg>
  )
}

export function IconEye(props) {
  return (
    <Svg {...props}>
      <path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12z" />
      <circle cx="12" cy="12" r="3" />
    </Svg>
  )
}

export function IconEyeOff(props) {
  return (
    <Svg {...props}>
      <path d="M4 4l16 16" />
      <path d="M9.5 5.9A9.6 9.6 0 0 1 12 5.5c6 0 9.5 6.5 9.5 6.5a17 17 0 0 1-3.4 4.2" />
      <path d="M6.3 7.8A16.7 16.7 0 0 0 2.5 12S6 18.5 12 18.5c1.3 0 2.4-.3 3.4-.8" />
    </Svg>
  )
}

export function IconMoney(props) {
  return (
    <Svg {...props}>
      <rect x="2.5" y="6" width="19" height="12" rx="2" />
      <circle cx="12" cy="12" r="2.5" />
      <path d="M6 9.5v5M18 9.5v5" />
    </Svg>
  )
}

export function IconList(props) {
  return (
    <Svg {...props}>
      <path d="M8 6.5h12M8 12h12M8 17.5h12" />
      <path d="M4 6.5h.01M4 12h.01M4 17.5h.01" />
    </Svg>
  )
}

export function IconArrowRight(props) {
  return (
    <Svg {...props}>
      <path d="M4 12h15" />
      <path d="m13 6 6 6-6 6" />
    </Svg>
  )
}
