// Тумблер вкл/выкл. Используется в таблице каталога и в форме товара.
//
// Внутри input с классом peer: визуальный «язычок» двигается через
// peer-checked, а сам input остаётся настоящим (доступен с клавиатуры
// и читается скринридерами).

export default function Switch({
  checked,
  onChange,
  label,
  disabled = false,
  testId,
  tone = 'accent',
  size = 'md',
}) {
  const width = size === 'sm' ? 'h-4 w-7' : 'h-5 w-9'
  const knob = size === 'sm' ? 'h-3 w-3' : 'h-4 w-4'
  const shift = size === 'sm' ? 'peer-checked:translate-x-3' : 'peer-checked:translate-x-4'
  const on =
    tone === 'blue'
      ? 'peer-checked:bg-blue-600'
      : tone === 'red'
        ? 'peer-checked:bg-red-500'
        : 'peer-checked:bg-accent-strong'

  return (
    <label
      className={`inline-flex items-center gap-2 ${
        disabled ? 'cursor-not-allowed opacity-60' : 'cursor-pointer'
      }`}
    >
      <span className="relative inline-flex">
        <input
          type="checkbox"
          data-testid={testId}
          checked={checked}
          disabled={disabled}
          onChange={(event) => onChange(event.target.checked)}
          className="peer sr-only"
        />
        <span
          data-testid={testId ? `${testId}-track` : undefined}
          className={`${width} ${on} rounded-full bg-gray-200 transition peer-focus-visible:ring-2 peer-focus-visible:ring-orange-500`}
        />
        <span
          className={`${knob} ${shift} absolute left-0.5 top-0.5 rounded-full bg-white shadow transition`}
        />
      </span>
      {label ? <span className="text-sm text-gray-700">{label}</span> : null}
    </label>
  )
}
