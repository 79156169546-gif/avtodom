import { useEffect, useMemo, useRef, useState } from 'react'
import { fetchCarMakes, fetchCarModels } from '../api.js'
import { IconCar, IconCheck, IconChevron, IconClose, IconSearch } from './icons.jsx'

// Мульти-селект «Подходит для авто».
//
// Владелец выбирает марку и модель из справочника, а не вписывает строки
// руками: так нельзя опечататься в названии модели и так подбор по авто
// на витрине работает честно.
//
// Выбранные автомобили показываются бейджами с крестиком.

const YEAR_MIN = 1990
const YEAR_MAX = new Date().getFullYear() + 1

// Ключ бейджа: марка + модель + диапазон лет.
function fitKey(item) {
  return `${item.make}|${item.model ?? ''}|${item.year_from ?? ''}|${item.year_to ?? ''}`
}

export function formatFit(item) {
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

export default function CompatibilityPicker({ value = [], onChange, testId }) {
  const [makes, setMakes] = useState([])
  const [models, setModels] = useState([])
  const [make, setMake] = useState('')
  const [model, setModel] = useState('')
  const [yearFrom, setYearFrom] = useState('')
  const [yearTo, setYearTo] = useState('')
  const [makeOpen, setMakeOpen] = useState(false)
  const [modelOpen, setModelOpen] = useState(false)
  const [makeQuery, setMakeQuery] = useState('')
  const [modelQuery, setModelQuery] = useState('')
  const makeRef = useRef(null)
  const modelRef = useRef(null)

  useEffect(() => {
    let cancelled = false
    fetchCarMakes('', 40)
      .then((data) => {
        if (!cancelled) setMakes(data?.makes ?? [])
      })
      .catch(() => setMakes([]))
    return () => {
      cancelled = true
    }
  }, [])

  // Модели подгружаются под выбранную марку.
  useEffect(() => {
    if (!make) {
      setModels([])
      return undefined
    }
    let cancelled = false
    fetchCarModels(make, '')
      .then((data) => {
        if (!cancelled) setModels(data?.models ?? [])
      })
      .catch(() => setModels([]))
    return () => {
      cancelled = true
    }
  }, [make])

  // Закрываем выпадающие списки по клику вне.
  useEffect(() => {
    const onClick = (event) => {
      if (makeRef.current && !makeRef.current.contains(event.target)) {
        setMakeOpen(false)
      }
      if (modelRef.current && !modelRef.current.contains(event.target)) {
        setModelOpen(false)
      }
    }
    document.addEventListener('mousedown', onClick)
    return () => document.removeEventListener('mousedown', onClick)
  }, [])

  const filteredMakes = useMemo(() => {
    const needle = makeQuery.trim().toLowerCase()
    if (!needle) return makes
    return makes.filter((name) => name.toLowerCase().includes(needle))
  }, [makes, makeQuery])

  const filteredModels = useMemo(() => {
    const needle = modelQuery.trim().toLowerCase()
    if (!needle) return models
    return models.filter((name) => name.toLowerCase().includes(needle))
  }, [models, modelQuery])

  const add = () => {
    if (!make) return
    const item = {
      make,
      model: model || null,
      year_from: yearFrom ? Number(yearFrom) : null,
      year_to: yearTo ? Number(yearTo) : null,
    }
    // Дубли не добавляем — подбор по одному и тому же авто дважды
    // ничего не меняет, но список засоряется.
    const exists = value.some((entry) => fitKey(entry) === fitKey(item))
    if (!exists) onChange([...value, item])
    setModel('')
    setYearFrom('')
    setYearTo('')
    setModelQuery('')
    setModelOpen(false)
  }

  const remove = (item) => {
    onChange(value.filter((entry) => fitKey(entry) !== fitKey(item)))
  }

  const years = []
  for (let year = YEAR_MIN; year <= YEAR_MAX; year += 1) years.push(year)

  return (
    <div data-testid={testId}>
      {/* Выбранные автомобили */}
      {value.length > 0 ? (
        <div className="mb-2 flex flex-wrap gap-1.5" data-testid="compatibility-badges">
          {value.map((item) => (
            <span
              key={fitKey(item)}
              className="inline-flex items-center gap-1.5 rounded-full bg-accent-soft px-2.5 py-1 text-xs font-semibold text-accent-strong"
            >
              {formatFit(item)}
              <button
                type="button"
                data-testid={`compatibility-remove-${item.make}-${item.model ?? ''}`}
                onClick={() => remove(item)}
                className="rounded-full p-0.5 transition hover:bg-orange-200"
                aria-label={`Убрать ${formatFit(item)}`}
              >
                <IconClose className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        {/* Марка */}
        <div className="relative" ref={makeRef}>
          <span className="label">Марка</span>
          <button
            type="button"
            data-testid="compatibility-make-button"
            onClick={() => {
              setMakeOpen((value) => !value)
              setModelOpen(false)
            }}
            className="field flex items-center justify-between text-left"
          >
            <span className={make ? 'text-gray-900' : 'text-gray-400'}>
              {make || 'Выберите марку'}
            </span>
            <IconChevron
              className={`h-4 w-4 shrink-0 text-gray-400 transition ${
                makeOpen ? 'rotate-180' : ''
              }`}
            />
          </button>
          {makeOpen ? (
            <div className="absolute z-20 mt-1 w-full rounded-xl border border-gray-200 bg-white p-2 shadow-lg">
              <div className="relative mb-1.5">
                <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400">
                  <IconSearch className="h-3.5 w-3.5" />
                </span>
                <input
                  type="search"
                  data-testid="compatibility-make-search"
                  value={makeQuery}
                  onChange={(event) => setMakeQuery(event.target.value)}
                  placeholder="Найти марку"
                  className="w-full rounded-lg border border-gray-200 py-1.5 pl-8 pr-2 text-xs outline-none focus:border-accent"
                />
              </div>
              <div className="max-h-48 overflow-y-auto">
                {filteredMakes.map((name) => (
                  <button
                    key={name}
                    type="button"
                    data-testid={`compatibility-make-${name}`}
                    onClick={() => {
                      setMake(name)
                      setModel('')
                      setMakeOpen(false)
                      setMakeQuery('')
                    }}
                    className="block w-full rounded-lg px-2.5 py-1.5 text-left text-sm text-gray-700 transition hover:bg-gray-50"
                  >
                    {name}
                  </button>
                ))}
                {filteredMakes.length === 0 ? (
                  <p className="px-2.5 py-2 text-xs text-gray-400">Ничего не найдено</p>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>

        {/* Модель */}
        <div className="relative" ref={modelRef}>
          <span className="label">Модель</span>
          <button
            type="button"
            data-testid="compatibility-model-button"
            disabled={!make}
            onClick={() => {
              setModelOpen((value) => !value)
              setMakeOpen(false)
            }}
            className="field flex items-center justify-between text-left disabled:cursor-not-allowed disabled:bg-gray-100 disabled:text-gray-400"
          >
            <span className={model ? 'text-gray-900' : 'text-gray-400'}>
              {model || (make ? 'Любая модель' : 'Сначала марка')}
            </span>
            <IconChevron
              className={`h-4 w-4 shrink-0 text-gray-400 transition ${
                modelOpen ? 'rotate-180' : ''
              }`}
            />
          </button>
          {modelOpen ? (
            <div className="absolute z-20 mt-1 w-full rounded-xl border border-gray-200 bg-white p-2 shadow-lg">
              <div className="relative mb-1.5">
                <span className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-gray-400">
                  <IconSearch className="h-3.5 w-3.5" />
                </span>
                <input
                  type="search"
                  data-testid="compatibility-model-search"
                  value={modelQuery}
                  onChange={(event) => setModelQuery(event.target.value)}
                  placeholder="Найти модель"
                  className="w-full rounded-lg border border-gray-200 py-1.5 pl-8 pr-2 text-xs outline-none focus:border-accent"
                />
              </div>
              <div className="max-h-48 overflow-y-auto">
                {filteredModels.map((name) => (
                  <button
                    key={name}
                    type="button"
                    data-testid={`compatibility-model-${name}`}
                    onClick={() => {
                      setModel(name)
                      setModelOpen(false)
                      setModelQuery('')
                    }}
                    className="block w-full rounded-lg px-2.5 py-1.5 text-left text-sm text-gray-700 transition hover:bg-gray-50"
                  >
                    {name}
                  </button>
                ))}
                {filteredModels.length === 0 ? (
                  <p className="px-2.5 py-2 text-xs text-gray-400">Ничего не найдено</p>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>

        {/* Годы */}
        <div className="grid grid-cols-2 gap-2 sm:col-span-2">
          <div>
            <label className="label" htmlFor="compatibility-year-from">
              Год с
            </label>
            <select
              id="compatibility-year-from"
              data-testid="compatibility-year-from"
              value={yearFrom}
              onChange={(event) => setYearFrom(event.target.value)}
              className="field py-2.5 text-sm"
            >
              <option value="">—</option>
              {years.map((year) => (
                <option key={year} value={String(year)}>
                  {year}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="label" htmlFor="compatibility-year-to">
              Год по
            </label>
            <select
              id="compatibility-year-to"
              data-testid="compatibility-year-to"
              value={yearTo}
              onChange={(event) => setYearTo(event.target.value)}
              className="field py-2.5 text-sm"
            >
              <option value="">—</option>
              {years.map((year) => (
                <option key={year} value={String(year)}>
                  {year}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <button
        type="button"
        data-testid="compatibility-add"
        onClick={add}
        disabled={!make}
        className="btn-secondary mt-2 w-full disabled:cursor-not-allowed disabled:opacity-50"
      >
        <IconCar className="h-4 w-4" />
        Добавить автомобиль
      </button>

      {value.length === 0 ? (
        <p className="mt-1.5 text-xs text-gray-400">
          Пусто — деталь подходит к любому авто.
        </p>
      ) : (
        <p className="mt-1.5 flex items-center gap-1.5 text-xs text-gray-400">
          <IconCheck className="h-3.5 w-3.5" />
          Выбрано автомобилей: {value.length}
        </p>
      )}
    </div>
  )
}
