// Кликабельная карточка метрики.
//
// Метрика не только показывает число, но и переключает фильтр заказов:
// «Новых» сразу открывает заказы в статусе «Новый», «Заказов всего»
// снимает фильтр по статусу, «Выручка за сегодня» оставляет только
// сегодняшние заказы, «Товаров» переключает на вкладку каталога.

import { IconBox, IconMoney } from './icons.jsx'

export default function StatCard({
  label,
  value,
  active = false,
  onClick,
  hint,
  icon,
  testId,
}) {
  const Icon = icon

  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      aria-pressed={active}
      className={`card p-4 text-left transition ${
        active
          ? 'border-2 border-accent-strong bg-orange-50/60 shadow-card'
          : 'hover:border-gray-300 hover:shadow-md'
      }`}
    >
      <span className="flex items-center justify-between gap-2">
        <span className="text-xs font-medium uppercase tracking-wide text-gray-400">
          {label}
        </span>
        {Icon ? (
          <Icon
            className={`h-4 w-4 shrink-0 ${
              active ? 'text-accent-strong' : 'text-gray-300'
            }`}
          />
        ) : null}
      </span>
      <span className="mt-1 block text-xl font-bold text-gray-900">{value}</span>
      {hint ? (
        <span
          className={`mt-0.5 block text-[11px] ${
            active ? 'text-accent-strong' : 'text-gray-400'
          }`}
        >
          {hint}
        </span>
      ) : null}
    </button>
  )
}

export const STAT_ICONS = {
  orders: IconBox,
  money: IconMoney,
}
