// Скелетон карточки товара на время загрузки каталога.
export default function ProductSkeleton() {
  return (
    <div
      data-testid="product-skeleton"
      className="card overflow-hidden p-4"
      aria-hidden="true"
    >
      <div className="flex gap-3">
        <div className="h-16 w-16 shrink-0 animate-pulse rounded-xl bg-gray-200" />
        <div className="min-w-0 flex-1 space-y-2">
          <div className="h-3.5 w-1/3 animate-pulse rounded bg-gray-200" />
          <div className="h-4 w-3/4 animate-pulse rounded bg-gray-200" />
          <div className="h-3 w-1/2 animate-pulse rounded bg-gray-100" />
        </div>
      </div>
      <div className="mt-4 flex items-center justify-between">
        <div className="h-5 w-24 animate-pulse rounded bg-gray-200" />
        <div className="h-9 w-28 animate-pulse rounded-xl bg-gray-100" />
      </div>
    </div>
  )
}
