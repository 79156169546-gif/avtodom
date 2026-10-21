// Тонкий клиент к FastAPI-бэкенду.
// В dev-режиме Vite проксирует /api на http://127.0.0.1:8000 (vite.config.js).

const API_BASE = import.meta.env.VITE_API_BASE || ''

const TOKEN_KEY = 'autodom.token'

export function getToken() {
  try {
    return localStorage.getItem(TOKEN_KEY) || ''
  } catch {
    return ''
  }
}

export function setToken(token) {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token)
    else localStorage.removeItem(TOKEN_KEY)
  } catch {
    /* приватный режим браузера — работаем без персиста */
  }
}

async function request(path, options = {}) {
  const { method = 'GET', body, auth = true } = options
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  const token = getToken()
  if (auth && token) headers.Authorization = `Bearer ${token}`

  const response = await fetch(`${API_BASE}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  })

  if (response.status === 204) return null

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const parsed = await response.json()
      if (typeof parsed?.detail === 'string') {
        detail = parsed.detail
      } else if (Array.isArray(parsed?.detail)) {
        detail = parsed.detail.map((item) => item.msg).join('; ')
      }
    } catch {
      /* тело не JSON — оставляем HTTP-код */
    }
    const error = new Error(detail)
    error.status = response.status
    throw error
  }

  const text = await response.text()
  return text ? JSON.parse(text) : null
}

// --- каталог ---------------------------------------------------------------

export function fetchProducts() {
  return request('/api/products', { auth: false })
}

export function fetchHealth() {
  return request('/api/health', { auth: false })
}

// --- справочник авто и режим работы ---------------------------------------

export function fetchCarMakes(query = '', limit = 40) {
  const params = new URLSearchParams({ q: query, limit: String(limit) })
  return request(`/api/cars/makes?${params.toString()}`, {
    auth: false,
  })
}

export function fetchCarModels(make, query = '') {
  const params = new URLSearchParams({ make: make || '', q: query })
  return request(`/api/cars/models?${params.toString()}`, { auth: false })
}

export function fetchCarYears(make = '', model = '') {
  const params = new URLSearchParams({ make: make || '', model: model || '' })
  return request(`/api/cars/years?${params.toString()}`, { auth: false })
}

export function fetchCarVin(vin) {
  return request(`/api/cars/vin?vin=${encodeURIComponent(vin || '')}`, {
    auth: false,
  })
}

export function fetchStoreInfo() {
  return request('/api/store', { auth: false })
}

// --- аккаунты --------------------------------------------------------------

export function register(payload) {
  return request('/api/auth/register', { method: 'POST', body: payload, auth: false })
}

export function login(payload) {
  return request('/api/auth/login', { method: 'POST', body: payload, auth: false })
}

export function logout() {
  return request('/api/auth/logout', { method: 'POST' })
}

export function fetchMe() {
  return request('/api/auth/me')
}

// --- заказы ----------------------------------------------------------------

export function submitOrder(payload) {
  return request('/api/orders', { method: 'POST', body: payload })
}

export function fetchOrder(orderNumber, phone) {
  const query = phone ? `?phone=${encodeURIComponent(phone)}` : ''
  return request(`/api/orders/${orderNumber}${query}`)
}

// --- кабинет клиента -------------------------------------------------------

export function fetchMyOrders() {
  return request('/api/cabinet/orders')
}

export function fetchMyOrder(orderNumber) {
  return request(`/api/cabinet/orders/${orderNumber}`)
}

// Ссылка-подписка на уведомления о заказе в Telegram.
export function fetchOrderTelegramLink(orderNumber) {
  return request(`/api/orders/${orderNumber}/telegram-link`)
}

// --- кабинет владельца -----------------------------------------------------

export function fetchAdminOrders(filters = {}) {
  const params = new URLSearchParams()
  if (filters.status) params.set('order_status', filters.status)
  if (filters.dateFrom) params.set('date_from', filters.dateFrom)
  if (filters.dateTo) params.set('date_to', filters.dateTo)
  if (filters.query) params.set('query', filters.query)
  if (filters.nightOnly) params.set('night_only', 'true')
  if (filters.sort) params.set('sort', filters.sort)
  if (filters.limit) params.set('limit', String(filters.limit))
  const query = params.toString()
  return request(`/api/admin/orders${query ? `?${query}` : ''}`)
}

export function updateAdminOrder(orderId, payload) {
  return request(`/api/admin/orders/${orderId}`, { method: 'PATCH', body: payload })
}

export function fetchAdminProducts() {
  return request('/api/admin/products')
}

export function createAdminProduct(payload) {
  return request('/api/admin/products', { method: 'POST', body: payload })
}

export function updateAdminProduct(productId, payload) {
  return request(`/api/admin/products/${productId}`, { method: 'PATCH', body: payload })
}

export function deleteAdminProduct(productId, restore = false) {
  return request(`/api/admin/products/${productId}?restore=${restore}`, {
    method: 'DELETE',
  })
}

export function fetchAdminStats() {
  return request('/api/admin/stats')
}
