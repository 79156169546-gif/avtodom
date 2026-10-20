import { useEffect, useMemo, useState } from 'react'
import Combobox from './Combobox.jsx'
import { fetchCarMakes, fetchCarModels } from '../api.js'
import { formatPrice } from '../lib/format.js'

const STEPS = [
  { id: 1, title: 'Авто', hint: 'Марка и модель — подскажем по первым буквам' },
  { id: 2, title: 'Запчасти', hint: 'Проверьте состав заказа' },
  { id: 3, title: 'Получение', hint: 'Самовывоз из магазина' },
  { id: 4, title: 'Данные клиента', hint: 'Имя и телефон обязательны' },
  { id: 5, title: 'Подтверждение', hint: 'Проверьте и оформите' },
]

const EMPTY_FORM = {
  car_make: '',
  car_model: '',
  vin: '',
  pickup_method: 'pickup',
  customer_name: '',
  phone: '',
  telegram: '',
  comment: '',
}

// Режим работы магазина. Бэкенд отдаёт актуальные значения в /api/store,
// здесь — копия по умолчанию, чтобы форма не зависела от загрузки.
const STORE_OPEN_HOUR = 8
const STORE_CLOSE_HOUR = 20
const NIGHT_START_HOUR = 20
const NIGHT_END_HOUR = 8

// Телефон: 10–15 цифр, не одна повторяющаяся цифра, не «placeholder».
const PLACEHOLDER_PHONES = new Set([
  '1234567890',
  '0123456789',
  '0987654321',
  '1111111111',
  '0000000000',
  '1231231231',
])

export function phoneDigits(value) {
  return (value || '').replace(/\D/g, '')
}

export function validatePhone(value) {
  const digits = phoneDigits(value)
  if (!digits) return 'Укажите телефон для связи'
  if (digits.length < 10) return 'Слишком короткий номер — нужно 10–15 цифр'
  if (digits.length > 15) return 'Слишком длинный номер — нужно 10–15 цифр'
  if (new Set(digits).size === 1) return 'Номер не может состоять из одной цифры'
  if (PLACEHOLDER_PHONES.has(digits)) {
    return 'Введите настоящий номер, например +7 900 123-45-67'
  }
  return ''
}

export default function CheckoutSheet({
  open,
  items,
  total,
  user,
  submitting,
  error,
  onClose,
  onSubmit,
}) {
  const [step, setStep] = useState(1)
  const [form, setForm] = useState(EMPTY_FORM)
  const [makeOptions, setMakeOptions] = useState([])
  const [modelOptions, setModelOptions] = useState([])
  const [touched, setTouched] = useState({})

  useEffect(() => {
    if (open) {
      setStep(1)
      setTouched({})
      setForm({
        ...EMPTY_FORM,
        // Данные из аккаунта подставляем автоматически.
        customer_name: user?.full_name ?? '',
        phone: user?.phone ?? '',
        telegram: user?.telegram ?? '',
      })
    }
  }, [open, user])

  // Подсказки по маркам — подгружаем при открытии и по первым буквам.
  useEffect(() => {
    if (!open) return undefined
    let alive = true
    const load = async () => {
      try {
        const data = await fetchCarMakes(form.car_make)
        if (alive) setMakeOptions(data.makes || [])
      } catch {
        if (alive) setMakeOptions([])
      }
    }
    load()
    return () => {
      alive = false
    }
  }, [open, form.car_make])

  // Подсказки по моделям — только для выбранной марки.
  useEffect(() => {
    if (!open || !form.car_make.trim()) {
      setModelOptions([])
      return undefined
    }
    let alive = true
    const load = async () => {
      try {
        const data = await fetchCarModels(form.car_make, form.car_model)
        if (alive) setModelOptions(data.models || [])
      } catch {
        if (alive) setModelOptions([])
      }
    }
    load()
    return () => {
      alive = false
    }
  }, [open, form.car_make, form.car_model])

  const update = (field) => (event) => {
    const { value } = event.target
    setForm((prev) => ({ ...prev, [field]: value }))
  }

  const nameError = useMemo(() => {
    if (!touched.customer_name && !form.customer_name.trim()) return ''
    if (form.customer_name.trim().length < 2) {
      return 'Укажите имя (минимум 2 символа)'
    }
    return ''
  }, [form.customer_name, touched.customer_name])

  const phoneError = useMemo(
    () => (touched.phone ? validatePhone(form.phone) : ''),
    [form.phone, touched.phone],
  )

  const canContinue = useMemo(() => {
    if (step === 4) {
      const hasName = form.customer_name.trim().length >= 2
      const hasPhone = validatePhone(form.phone) === ''
      return hasName && hasPhone
    }
    return true
  }, [step, form])

  if (!open) return null

  const submit = () => {
    const payload = {
      items: items.map((item) => ({ product_id: item.id, qty: item.qty })),
      car_make: form.car_make.trim() || null,
      car_model: form.car_model.trim() || null,
      vin: form.vin.trim() || null,
      pickup_method: 'pickup',
      customer_name: form.customer_name.trim(),
      phone: form.phone.trim(),
      telegram: form.telegram.trim().replace(/^@/, '') || null,
      comment: form.comment.trim() || null,
    }
    onSubmit(payload)
  }

  const hoursLabel = `${STORE_OPEN_HOUR}:00–${String(STORE_CLOSE_HOUR).padStart(2, '0')}:00`
  const nightLabel = `${String(NIGHT_START_HOUR).padStart(2, '0')}:00–${String(NIGHT_END_HOUR).padStart(2, '0')}:00`

  return (
    <div className="fixed inset-0 z-40 flex items-end justify-center sm:items-center">
      <button
        type="button"
        aria-label="Закрыть"
        onClick={onClose}
        className="absolute inset-0 bg-gray-900/40"
      />
      <div
        data-testid="checkout-sheet"
        className="relative flex max-h-[92vh] w-full max-w-lg flex-col overflow-hidden rounded-t-2xl bg-gray-50 shadow-xl sm:rounded-2xl"
      >
        <header className="border-b border-gray-200 bg-white px-5 py-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-bold text-gray-900">Оформление заказа</h2>
              <p className="mt-0.5 text-sm text-gray-500">
                Шаг {step} из {STEPS.length} · {STEPS[step - 1].hint}
              </p>
            </div>
            <button
              type="button"
              onClick={onClose}
              className="rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
              aria-label="Закрыть оформление"
            >
              ✕
            </button>
          </div>

          <ol className="mt-3 flex items-center gap-1.5" aria-label="Шаги заказа">
            {STEPS.map((item) => (
              <li key={item.id} className="flex flex-1 items-center gap-1.5">
                <span
                  className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-sm font-bold transition ${
                    item.id === step
                      ? 'bg-accent-soft text-accent-strong ring-2 ring-orange-500'
                      : item.id < step
                        ? 'bg-accent-strong text-white'
                        : 'bg-gray-100 text-gray-400'
                  }`}
                >
                  {item.id}
                </span>
                {item.id < STEPS.length ? (
                  <span
                    className={`h-0.5 flex-1 rounded ${
                      item.id < step ? 'bg-accent-strong' : 'bg-gray-200'
                    }`}
                  />
                ) : null}
              </li>
            ))}
          </ol>
        </header>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {step === 1 ? (
            <section className="space-y-4">
              <div className="flex items-center gap-2.5">
                <span className="step-badge">1</span>
                <h3 className="text-[15px] font-semibold text-gray-900">
                  Марка, модель и VIN
                </h3>
              </div>
              <p className="text-sm text-gray-500">
                Начните вводить марку — покажем варианты. Модель подскажем по
                выбранной марке.
              </p>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <label className="label" htmlFor="car_make">
                    Марка
                  </label>
                  <Combobox
                    id="car_make"
                    testId="car-make"
                    value={form.car_make}
                    placeholder="Начните вводить, например K"
                    options={makeOptions}
                    emptyText="Марка не найдена — введите вручную"
                    onChange={(value) =>
                      setForm((prev) => ({
                        ...prev,
                        car_make: value,
                        // Модель другой марки сбрасываем.
                        car_model: '',
                      }))
                    }
                  />
                </div>
                <div>
                  <label className="label" htmlFor="car_model">
                    Модель
                  </label>
                  <Combobox
                    id="car_model"
                    testId="car-model"
                    value={form.car_model}
                    placeholder={
                      form.car_make.trim()
                        ? 'Начните вводить модель'
                        : 'Сначала выберите марку'
                    }
                    options={modelOptions}
                    disabled={!form.car_make.trim()}
                    emptyText="Модель не найдена — введите вручную"
                    onChange={(value) =>
                      setForm((prev) => ({ ...prev, car_model: value }))
                    }
                  />
                </div>
              </div>

              <div>
                <label className="label" htmlFor="vin">
                  VIN
                  <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500">
                    необязательно
                  </span>
                </label>
                <input
                  id="vin"
                  data-testid="vin"
                  className="field uppercase"
                  placeholder="Z94CB41AAER123456"
                  maxLength={17}
                  value={form.vin}
                  onChange={update('vin')}
                />
                <p className="mt-1.5 text-xs leading-relaxed text-gray-400">
                  VIN — это 17-символьный номер кузова. Если он указан, мы
                  проверим совместимость детали и подтвердим заказ точнее. Не
                  знаете VIN? Пропустите поле — менеджер уточнит детали по
                  телефону.
                </p>
              </div>
            </section>
          ) : null}

          {step === 2 ? (
            <section className="space-y-4">
              <div className="flex items-center gap-2.5">
                <span className="step-badge">2</span>
                <h3 className="text-[15px] font-semibold text-gray-900">Запчасти</h3>
              </div>
              <ul className="space-y-2">
                {items.map((item) => (
                  <li
                    key={item.id}
                    data-testid="checkout-item"
                    className="card flex items-center justify-between gap-3 p-3"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-gray-900">
                        {item.name}
                      </p>
                      <p className="text-xs text-gray-500">
                        {formatPrice(item.price)} × {item.qty}
                      </p>
                      {item.is_on_order && !item.in_stock ? (
                        <p
                          data-testid="checkout-item-on-order"
                          className="mt-1 inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-700"
                        >
                          ⏳ Под заказ · {item.order_days} дн.
                        </p>
                      ) : null}
                    </div>
                    <span className="shrink-0 text-sm font-semibold text-gray-900">
                      {formatPrice(Number(item.price) * item.qty)}
                    </span>
                  </li>
                ))}
              </ul>
              {items.some((item) => item.is_on_order && !item.in_stock) ? (
                <p className="rounded-xl bg-blue-50 px-4 py-3 text-xs leading-relaxed text-blue-800">
                  Позиции «под заказ» мы закажем у поставщика после
                  подтверждения заказа. Срок поставки указан у каждой детали —
                  менеджер сообщит точные даты.
                </p>
              ) : null}
            </section>
          ) : null}

          {step === 3 ? (
            <section className="space-y-4">
              <div className="flex items-center gap-2.5">
                <span className="step-badge">3</span>
                <h3 className="text-[15px] font-semibold text-gray-900">Получение</h3>
              </div>

              <div
                data-testid="pickup-pickup"
                className="card flex items-start gap-3 p-4 ring-2 ring-orange-500"
              >
                <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-accent-strong text-[11px] font-bold text-white">
                  ✓
                </span>
                <span>
                  <span className="block text-sm font-semibold text-gray-900">
                    Самовывоз из магазина
                  </span>
                  <span className="mt-0.5 block text-xs text-gray-500">
                    Магазин работает ежедневно {hoursLabel}. Заберите заказ в
                    рабочее время — мы позвоним и подтвердим готовность.
                  </span>
                </span>
              </div>

              <div className="card flex items-start gap-3 bg-orange-50 p-4">
                <span className="text-lg leading-none">🌙</span>
                <span>
                  <span className="block text-sm font-semibold text-gray-900">
                    Заказы с {nightLabel} — в приоритете
                  </span>
                  <span className="mt-0.5 block text-xs text-gray-600">
                    Магазин в это время закрыт, но заказ всё равно принимаем и
                    ставим в работу первой очередью. Менеджер свяжется с вами
                    утром.
                  </span>
                </span>
              </div>
            </section>
          ) : null}

          {step === 4 ? (
            <section className="space-y-4">
              <div className="flex items-center gap-2.5">
                <span className="step-badge">4</span>
                <h3 className="text-[15px] font-semibold text-gray-900">
                  Данные клиента
                </h3>
              </div>

              <div>
                <label className="label" htmlFor="customer_name">
                  Имя
                  <span className="ml-1 text-accent-strong">*</span>
                </label>
                <input
                  id="customer_name"
                  data-testid="customer-name"
                  className={`field ${nameError ? 'border-red-300 ring-1 ring-red-200' : ''}`}
                  placeholder="Иван"
                  value={form.customer_name}
                  onBlur={() =>
                    setTouched((prev) => ({ ...prev, customer_name: true }))
                  }
                  onChange={update('customer_name')}
                />
                {nameError ? (
                  <p className="mt-1.5 text-xs text-red-600">{nameError}</p>
                ) : null}
              </div>

              <div>
                <label className="label" htmlFor="phone">
                  Телефон
                  <span className="ml-1 text-accent-strong">*</span>
                </label>
                <input
                  id="phone"
                  data-testid="phone"
                  type="tel"
                  inputMode="tel"
                  autoComplete="tel"
                  className={`field ${phoneError ? 'border-red-300 ring-1 ring-red-200' : ''}`}
                  placeholder="+7 900 123-45-67"
                  value={form.phone}
                  onBlur={() => setTouched((prev) => ({ ...prev, phone: true }))}
                  onChange={update('phone')}
                />
                {phoneError ? (
                  <p className="mt-1.5 text-xs text-red-600">{phoneError}</p>
                ) : (
                  <p className="mt-1.5 text-xs text-gray-400">
                    По этому номеру мы подтвердим заказ и сообщим о готовности.
                  </p>
                )}
              </div>

              <div>
                <label className="label" htmlFor="telegram">
                  Telegram
                  <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500">
                    необязательно
                  </span>
                </label>
                <input
                  id="telegram"
                  data-testid="telegram"
                  className="field"
                  placeholder="@username"
                  value={form.telegram}
                  onChange={update('telegram')}
                />
                <p className="mt-1.5 text-xs leading-relaxed text-gray-400">
                  Укажите Telegram, если хотите получать уведомления о статусе
                  заказа прямо в чате бота. Телефон нужен в любом случае.
                </p>
              </div>

              <div>
                <label className="label" htmlFor="comment">
                  Комментарий
                  <span className="ml-2 rounded-full bg-gray-100 px-2 py-0.5 text-[11px] font-medium text-gray-500">
                    необязательно
                  </span>
                </label>
                <textarea
                  id="comment"
                  data-testid="comment"
                  rows={3}
                  className="field resize-none"
                  placeholder="Нужны заказанные позиции до 18:00"
                  value={form.comment}
                  onChange={update('comment')}
                />
              </div>
            </section>
          ) : null}

          {step === 5 ? (
            <section className="space-y-4">
              <div className="flex items-center gap-2.5">
                <span className="step-badge">5</span>
                <h3 className="text-[15px] font-semibold text-gray-900">
                  Подтверждение
                </h3>
              </div>
              <dl className="card space-y-2 p-4 text-sm">
                <div className="flex justify-between gap-4">
                  <dt className="text-gray-500">Авто</dt>
                  <dd className="text-right font-medium text-gray-900">
                    {[form.car_make, form.car_model].filter(Boolean).join(' ') ||
                      'не указан'}
                    {form.vin ? ` · VIN ${form.vin}` : ''}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-gray-500">Получение</dt>
                  <dd className="text-right font-medium text-gray-900">
                    Самовывоз · {hoursLabel}
                  </dd>
                </div>
                <div className="flex justify-between gap-4">
                  <dt className="text-gray-500">Клиент</dt>
                  <dd className="text-right font-medium text-gray-900">
                    {form.customer_name}
                    <br />
                    {form.phone}
                    {form.telegram
                      ? ` · @${form.telegram.replace(/^@/, '')}`
                      : ''}
                  </dd>
                </div>
                {form.comment ? (
                  <div className="flex justify-between gap-4">
                    <dt className="text-gray-500">Комментарий</dt>
                    <dd className="text-right font-medium text-gray-900">
                      {form.comment}
                    </dd>
                  </div>
                ) : null}
                <div className="flex justify-between gap-4 border-t border-gray-100 pt-2">
                  <dt className="text-gray-500">Товаров</dt>
                  <dd className="text-right font-medium text-gray-900">
                    {items.length}
                  </dd>
                </div>
              </dl>
              <div className="card flex items-center justify-between p-4">
                <span className="text-sm font-medium text-gray-500">К оплате</span>
                <span
                  data-testid="checkout-total"
                  className="text-xl font-bold text-gray-900"
                >
                  {formatPrice(total)}
                </span>
              </div>
              <p className="text-xs leading-relaxed text-gray-400">
                Заказ уйдёт менеджеру в Telegram — он свяжется с вами для
                подтверждения. Заказы с {nightLabel} (когда магазин закрыт)
                обрабатываются в приоритетном порядке.
              </p>
            </section>
          ) : null}

          {error ? (
            <p
              data-testid="checkout-error"
              className="mt-4 rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700"
            >
              {error}
            </p>
          ) : null}
        </div>

        <footer className="border-t border-gray-200 bg-white px-5 py-3 pb-safe">
          <div className="flex gap-2">
            {step > 1 ? (
              <button
                type="button"
                data-testid="step-back"
                onClick={() => setStep((s) => Math.max(1, s - 1))}
                className="btn-secondary"
                disabled={submitting}
              >
                Назад
              </button>
            ) : null}
            {step < STEPS.length ? (
              <button
                type="button"
                data-testid="step-next"
                onClick={() => setStep((s) => Math.min(STEPS.length, s + 1))}
                className="btn-primary flex-1"
                disabled={!canContinue}
              >
                Далее
              </button>
            ) : (
              <button
                type="button"
                data-testid="submit-order"
                onClick={submit}
                className="btn-primary flex-1"
                disabled={submitting}
              >
                {submitting ? 'Отправляем…' : 'Оформить заказ'}
              </button>
            )}
          </div>
        </footer>
      </div>
    </div>
  )
}
