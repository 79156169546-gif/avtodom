// Скелетон карточки товара на время загрузки каталога.
// Повторяет структуру карточки: иконка категории, название, совместимость,
// наличие, цена и кнопка.
export default function ProductSkeleton() {
  return (
    <div
      data-testid="product-skeleton"
      className="card flex flex-col gap-3 p-4"
      aria-hidden="true"
    >
      <div className="flex items-center gap-2.5">
        <div className="h-10 w-10 shrink-0 animate-pulse rounded-xl bg-gray-200" />
        <div className="h-3 w-24 animate-pulse rounded bg-gray-200" />
      </div>
      <div className="space-y-1.5">
        <div className="h-4 w-full animate-pulse rounded bg-gray-200" />
        <div className="h-4 w-2/3 animate-pulse rounded bg-gray-200" />
      </div>
      <div className="space-y-1.5">
        <div className="h-3 w-1/3 animate-pulse rounded bg-gray-100" />
        <div className="h-3 w-3/4 animate-pulse rounded bg-gray-100" />
        <div className="h-2.5 w-1/2 animate-pulse rounded bg-gray-100" />
      </div>
      <div className="h-5 w-24 animate-pulse rounded-full bg-gray-100" />
      <div className="mt-auto space-y-3">
        <div className="h-6 w-32 animate-pulse rounded bg-gray-200" />
        <div className="h-10 w-full animate-pulse rounded-xl bg-gray-100" />
      </div>
    </div>
  )
}
