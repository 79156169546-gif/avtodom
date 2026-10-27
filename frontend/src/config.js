// ═════════════════════════════════════════════════════════════════════════
//  ЕДИНАЯ КОНФИГУРАЦИЯ МАГАЗИНА (white-label шаблон)
// ═════════════════════════════════════════════════════════════════════════
//  Весь бренд и контакты конкретного магазина — здесь.
//
//  Как переключить магазин на нового клиента:
//    1) Поменять значения ниже (или задать переменные окружения Vite
//       VITE_STORE_* перед сборкой — они имеют приоритет),
//    2) Пересобрать фронтенд:  npm run build
//
//  Приоритет источников данных магазина:
//    бэкенд /api/store (рантайм, правится из «Кабинета владельца»)
//      → этот конфиг (сборка)
//      → значения по умолчанию ниже.
//  То есть если бэкенд доступен — он имеет приоритет; если фронтенд
//  развёрнут отдельно от бэкенда — работает этот конфиг.
// ═════════════════════════════════════════════════════════════════════════

const env = import.meta.env || {}

function pick(envKey, fallback) {
  const v = env[envKey]
  return typeof v === 'string' && v.trim().length > 0 ? v.trim() : fallback
}

// Режим работы строкой для вывода (например, «09:00–20:00»).
// Часы разбираются в helper'е ниже — они же используются для индикатора
// «открыто/закрыто», когда бэкенд недоступен.
export const STORE_WORK_HOURS = pick('VITE_STORE_WORK_HOURS', '08:00–20:00')

export const storeConfig = {
  name: pick('VITE_STORE_NAME', 'Автомагазин'),
  slogan: pick('VITE_STORE_SLOGAN', 'Запчасти для вашего авто'),
  city: pick('VITE_STORE_CITY', 'Ваш город'),
  phone: pick('VITE_STORE_PHONE', '+7 (999) 000-00-00'),
  phoneHref: pick('VITE_STORE_PHONE_HREF', 'tel:+79990000000'),
  address: pick('VITE_STORE_ADDRESS', 'Ваш город, ул. Примерная, 1'),
  mapsUrl: pick('VITE_STORE_MAPS_URL', '#'),
  workHours: STORE_WORK_HOURS,
  // URL/путь к логотипу. Пусто — выводится круг с первой буквой названия.
  logo: pick('VITE_STORE_LOGO', ''),
  // Часы работы для офлайн-индикатора (когда бэкенд не отвечает).
  openHour: Number(pick('VITE_STORE_OPEN_HOUR', '8')),
  closeHour: Number(pick('VITE_STORE_CLOSE_HOUR', '20')),
}

// Разбирает строку «09:00–20:00» / «09:00-20:00» / «09:00 20:00» в {open, close}.
export function parseWorkHours(range = STORE_WORK_HOURS) {
  const m = String(range).match(/(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})/)
  if (!m) return { open: storeConfig.openHour, close: storeConfig.closeHour }
  return { open: Number(m[1]), close: Number(m[3]) }
}

// Первая заглавная буква названия — для буквенного логотипа.
export function firstLetter(name = storeConfig.name) {
  return (name || '?').trim().charAt(0).toUpperCase()
}

// Открыто ли сейчас (по локальному времени браузера). Используется только
// когда бэкенд недоступен; при наличии /api/store берётся его is_open.
export function isStoreOpen(range = STORE_WORK_HOURS, now = new Date()) {
  const { open, close } = parseWorkHours(range)
  const hour = now.getHours()
  return hour >= open && hour < close
}

export default storeConfig
