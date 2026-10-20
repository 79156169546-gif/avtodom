// Корзина и пользовательские настройки живут в localStorage:
// страница не сбрасывается при перезагрузке.

const CART_KEY = 'autodom.cart'
const CONTACT_KEY = 'autodom.contact'

function readJson(key, fallback) {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function writeJson(key, value) {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    /* приватный режим — работаем без персиста */
  }
}

export function loadCart() {
  const cart = readJson(CART_KEY, {})
  if (!cart || typeof cart !== 'object') return {}
  // чистим мусор и приводим qty к целым положительным
  return Object.fromEntries(
    Object.entries(cart)
      .map(([id, qty]) => [Number(id), Math.max(0, Math.floor(Number(qty) || 0))])
      .filter(([, qty]) => qty > 0),
  )
}

export function saveCart(cart) {
  writeJson(CART_KEY, cart)
}

export function clearCart() {
  try {
    localStorage.removeItem(CART_KEY)
  } catch {
    /* игнор */
  }
}

export function loadContact() {
  return readJson(CONTACT_KEY, {})
}

export function saveContact(contact) {
  writeJson(CONTACT_KEY, contact)
}
