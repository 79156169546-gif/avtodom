import { useEffect, useMemo, useRef, useState } from 'react'

/**
 * Поле с автодополнением: клиент начинает вводить — снизу появляется
 * список подходящих значений. Работает как нативный select, но с поиском.
 *
 * options: массив строк-подсказок.
 * onPick вызывается при выборе из списка.
 */
export default function Combobox({
  id,
  value,
  onChange,
  options,
  placeholder,
  testId,
  emptyText = 'Ничего не найдено',
  disabled = false,
  required = false,
}) {
  const [open, setOpen] = useState(false)
  const [highlight, setHighlight] = useState(0)
  const boxRef = useRef(null)

  const visible = useMemo(() => options.slice(0, 12), [options])

  useEffect(() => {
    if (!open) return undefined
    const onPointerDown = (event) => {
      if (boxRef.current && !boxRef.current.contains(event.target)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onPointerDown)
    return () => document.removeEventListener('mousedown', onPointerDown)
  }, [open])

  useEffect(() => {
    setHighlight(0)
  }, [options])

  const pick = (option) => {
    onChange(option)
    setOpen(false)
  }

  const onKeyDown = (event) => {
    if (event.key === 'ArrowDown') {
      event.preventDefault()
      if (!open) {
        setOpen(true)
        return
      }
      setHighlight((index) => Math.min(index + 1, visible.length - 1))
      return
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault()
      setHighlight((index) => Math.max(index - 1, 0))
      return
    }
    if (event.key === 'Enter') {
      if (open && visible[highlight]) {
        event.preventDefault()
        pick(visible[highlight])
      }
      return
    }
    if (event.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <div className="relative" ref={boxRef}>
      <input
        id={id}
        data-testid={testId}
        className="field"
        value={value}
        placeholder={placeholder}
        autoComplete="off"
        role="combobox"
        aria-expanded={open}
        aria-autocomplete="list"
        aria-controls={id ? `${id}-listbox` : undefined}
        disabled={disabled}
        required={required}
        onChange={(event) => {
          onChange(event.target.value)
          setOpen(true)
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={onKeyDown}
      />
      {open && !disabled ? (
        <ul
          id={id ? `${id}-listbox` : undefined}
          role="listbox"
          data-testid={testId ? `${testId}-list` : undefined}
          className="absolute z-30 mt-1 max-h-56 w-full overflow-y-auto rounded-xl border border-gray-200 bg-white py-1 shadow-lg"
        >
          {visible.length === 0 ? (
            <li className="px-4 py-2.5 text-sm text-gray-400">{emptyText}</li>
          ) : null}
          {visible.map((option, index) => (
            <li key={option}>
              <button
                type="button"
                role="option"
                aria-selected={index === highlight}
                data-testid={testId ? `${testId}-option-${option}` : undefined}
                className={`flex w-full items-center justify-between gap-2 px-4 py-2 text-left text-sm transition ${
                  index === highlight
                    ? 'bg-accent-soft font-semibold text-accent-strong'
                    : 'text-gray-700 hover:bg-gray-50'
                }`}
                onMouseEnter={() => setHighlight(index)}
                onClick={() => pick(option)}
              >
                <span>{option}</span>
                {value === option ? (
                  <span className="text-xs text-accent-strong">✓</span>
                ) : null}
              </button>
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  )
}
