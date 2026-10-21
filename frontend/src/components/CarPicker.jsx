import { useEffect, useMemo, useState } from 'react'
import { fetchCarMakes, fetchCarModels, fetchCarYears } from '../api.js'
import { IconCar, IconChevron, IconClose, IconReset } from './icons.jsx'

const CAR_KEY = 'autodom.car'

// Выбранный автомобиль живёт в localStorage: клиент не выбирает его заново
// при каждом визите в магазин.
function loadCar() {
  try {
    const raw = localStorage.getItem(CAR_KEY)
    if (!raw) return { make: '', model: '', year: '' }
    const parsed = JSON.parse(raw)
    return {
      make: parsed?.make ?? '',
      model: parsed?.model ?? '',
      year: parsed?.year ?? '',
    }
  } catch {
    return { make: '', model: '', year: '' }
  }
}

function saveCar(car) {
  try {
    localStorage.setItem(CAR_KEY, JSON.stringify(car))
  } catch {
    /* приватный режим — работаем без персиста */
  }
}

// Блок «Мой автомобиль»: Марка -> Модель -> Год.
// Выбранное авто подставляется в фильтр каталога.
export default function CarPicker({ car, onChange }) {
  const [makes, setMakes] = useState([])
  const [models, setModels] = useState([])
  const [years, setYears] = useState([])
  const [open, setOpen] = useState(false)

  useEffect(() => {
    let cancelled = false
    fetchCarMakes('')
      .then((data) => {
        if (!cancelled) setMakes(data?.makes ?? [])
      })
      .catch(() => setMakes([]))
    return () => {
      cancelled = true
    }
  }, [])

  // Модели — только для выбранной марки.
  useEffect(() => {
    if (!car.make) {
      setModels([])
      return undefined
    }
    let cancelled = false
    fetchCarModels(car.make, '')
      .then((data) => {
        if (!cancelled) setModels(data?.models ?? [])
      })
      .catch(() => setModels([]))
    return () => {
      cancelled = true
    }
  }, [car.make])

  // Годы выпуска — те, для которых в каталоге есть детали.
  useEffect(() => {
    if (!car.make) {
      setYears([])
      return undefined
    }
    let cancelled = false
    fetchCarYears(car.make, car.model)
      .then((data) => {
        if (!cancelled) setYears(data?.years ?? [])
      })
      .catch(() => setYears([]))
    return () => {
      cancelled = true
    }
  }, [car.make, car.model])

  const set = (patch) => {
    const next = { ...car, ...patch }
    // Смена марки сбрасывает модель и год — иначе получим «KIA + Polo».
    if (patch.make !== undefined && patch.make !== car.make) {
      next.model = ''
      next.year = ''
    }
    if (patch.model !== undefined && patch.model !== car.model) {
      next.year = ''
    }
    saveCar(next)
    onChange(next)
  }

  const label = useMemo(() => {
    if (!car.make) return 'Выберите авто'
    const parts = [car.make, car.model, car.year].filter(Boolean)
    return parts.join(' ')
  }, [car])

  const hasCar = Boolean(car.make)

  return (
    <div className="card overflow-hidden">
      <button
        type="button"
        data-testid="car-picker-toggle"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center gap-3 p-3.5 text-left transition hover:bg-gray-50"
      >
        <span
          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-xl ${
            hasCar ? 'bg-accent text-white' : 'bg-accent-soft text-accent-strong'
          }`}
        >
          <IconCar className="h-5 w-5" />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[11px] font-semibold uppercase tracking-wider text-gray-400">
            Мой автомобиль
          </span>
          <span
            data-testid="car-picker-label"
            className={`block truncate text-sm font-semibold ${
              hasCar ? 'text-gray-900' : 'text-accent-strong'
            }`}
          >
            {label}
          </span>
        </span>
        {hasCar ? (
          <span
            role="button"
            tabIndex={0}
            data-testid="car-picker-reset"
            onClick={(event) => {
              event.stopPropagation()
              const cleared = { make: '', model: '', year: '' }
              saveCar(cleared)
              onChange(cleared)
            }}
            onKeyDown={(event) => {
              if (event.key !== 'Enter' && event.key !== ' ') return
              event.stopPropagation()
              const cleared = { make: '', model: '', year: '' }
              saveCar(cleared)
              onChange(cleared)
            }}
            className="shrink-0 rounded-lg p-1.5 text-gray-400 transition hover:bg-gray-100 hover:text-gray-600"
            aria-label="Сбросить выбранный автомобиль"
          >
            <IconClose className="h-4 w-4" />
          </span>
        ) : null}
        <IconChevron
          className={`h-4 w-4 shrink-0 text-gray-400 transition ${open ? 'rotate-180' : ''}`}
        />
      </button>

      {open ? (
        <div
          data-testid="car-picker-panel"
          className="border-t border-gray-100 bg-gray-50/60 p-3.5"
        >
          <div className="grid gap-2.5 sm:grid-cols-3">
            <div>
              <label className="label" htmlFor="car-make">
                Марка
              </label>
              <select
                id="car-make"
                data-testid="car-make"
                value={car.make}
                onChange={(event) => set({ make: event.target.value })}
                className="field py-2.5 text-sm"
              >
                <option value="">Любая марка</option>
                {makes.map((make) => (
                  <option key={make} value={make}>
                    {make}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="car-model">
                Модель
              </label>
              <select
                id="car-model"
                data-testid="car-model"
                value={car.model}
                onChange={(event) => set({ model: event.target.value })}
                disabled={!car.make}
                className="field py-2.5 text-sm disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400"
              >
                <option value="">
                  {car.make ? 'Любая модель' : 'Сначала марка'}
                </option>
                {models.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label" htmlFor="car-year">
                Год
              </label>
              <select
                id="car-year"
                data-testid="car-year"
                value={car.year}
                onChange={(event) => set({ year: event.target.value })}
                disabled={!car.make}
                className="field py-2.5 text-sm disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400"
              >
                <option value="">Любой год</option>
                {years.map((year) => (
                  <option key={year} value={String(year)}>
                    {year}
                  </option>
                ))}
              </select>
            </div>
          </div>

          {car.make ? (
            <p className="mt-2.5 flex items-center gap-1.5 text-[11px] text-gray-500">
              <IconReset className="h-3.5 w-3.5" />
              Показаны только детали, совместимые с выбранным авто
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
