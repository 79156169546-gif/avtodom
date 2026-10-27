"""FastAPI-приложение: витрина заказов 24/7 для автомагазина.

Эндпоинты:
    GET  /api/health              — живость
    GET  /api/products            — каталог (публично)
    POST /api/orders              — оформить заказ (публично, но можно с сессией)
    GET  /api/orders/{number}     — заказ по номеру (владелец/свой/по телефону)
    POST /api/auth/register       — регистрация клиента
    POST /api/auth/login          — вход
    POST /api/auth/logout         — выход
    GET  /api/auth/me             — текущий пользователь
    GET  /api/cabinet/orders      — мои заказы (кабинет клиента)
    GET  /api/cabinet/orders/{n}  — заказ с таймлайном
    GET  /api/admin/orders        — все заказы (владелец)
    PATCH /api/admin/orders/{id}  — смена статуса (владелец)
    GET  /api/admin/products      — каталог + скрытые (владелец)
    POST /api/admin/products      — добавить товар (владелец)
    PATCH /api/admin/products/{id} — изменить товар/скидку (владелец)
    DELETE /api/admin/products/{id} — скрыть/восстановить товар (владелец)
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware

try:  # пакетный импорт (uvicorn backend.main:app)
    from . import auth, cars, db, order_status, settings
    from . import vin as vin_parser
    from .models import (
        ORDER_STATUS_LABELS,
        AuthOut,
        CompatibilityIn,
        CompatibilityOut,
        LoginIn,
        OrderEventOut,
        OrderIn,
        OrderItemOut,
        OrderOut,
        OrderStatusUpdate,
        ProductIn,
        ProductOut,
        RegisterIn,
        StoreSettingsIn,
        UserOut,
    )
    from .telegram import is_night_order, notifier
except ImportError:  # запуск как top-level модуль (uvicorn main:app, root dir = backend)
    import auth  # type: ignore[no-redef]
    import cars  # type: ignore[no-redef]
    import order_status  # type: ignore[no-redef]
    import vin as vin_parser  # type: ignore[no-redef]
    import db  # type: ignore[no-redef]
    import settings  # type: ignore[no-redef]
    from models import (  # type: ignore[no-redef]
        ORDER_STATUS_LABELS,
        AuthOut,
        CompatibilityIn,
        CompatibilityOut,
        LoginIn,
        OrderEventOut,
        OrderIn,
        OrderItemOut,
        OrderOut,
        OrderStatusUpdate,
        ProductIn,
        ProductOut,
        RegisterIn,
        StoreSettingsIn,
        UserOut,
    )
    from telegram import is_night_order, notifier  # type: ignore[no-redef]

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
# httpx на INFO печатает полный URL — в нём токен бота. Гасим.
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("autodom")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.validate()
    await notifier.start()
    try:
        yield
    finally:
        await notifier.stop()
        await db.close_pool()


app = FastAPI(
    title="Витрина заказов 24/7 — API",
    version="2.0.0",
    lifespan=lifespan,
)

_cors_all = "*" in settings.CORS_ORIGINS

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    # При allow_origins=["*"] браузер запрещает credentials — иначе CORS- preflight падает.
    allow_credentials=not _cors_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

PICKUP_LABELS = {"pickup": "Самовывоз", "delivery": "Доставка"}

# Ключи настроек магазина, которые владелец может править из кабинета.
# Держим в синхроне с моделью StoreSettingsIn — единый источник истины.
STORE_SETTINGS_KEYS: tuple[str, ...] = tuple(StoreSettingsIn.model_fields)


# ---------------------------------------------------------------------------
# Вспомогательное
# ---------------------------------------------------------------------------


def _status_label(value: str) -> str:
    return ORDER_STATUS_LABELS.get(value, value)


def _user_out(row: dict) -> UserOut:
    return UserOut(
        id=row["id"],
        email=row["email"],
        full_name=row.get("full_name"),
        phone=row.get("phone"),
        telegram=row.get("telegram"),
        role=row["role"],
        created_at=row["created_at"],
    )


async def _load_order_events(order_id: int) -> list[OrderEventOut]:
    rows = await db.fetch(
        """
        SELECT id, status, note, actor, created_at
        FROM order_events WHERE order_id = $1 ORDER BY id
        """,
        order_id,
    )
    return [
        OrderEventOut(
            id=row["id"],
            status=row["status"],
            status_label=_status_label(row["status"]),
            note=row["note"],
            actor=row["actor"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


async def _load_order_items(order_id: int) -> list[OrderItemOut]:
    rows = await db.fetch(
        """
        SELECT product_id, product_name, price, qty, line_total,
               is_on_order, order_days
        FROM order_items WHERE order_id = $1 ORDER BY id
        """,
        order_id,
    )
    return [
        OrderItemOut(
            product_id=row["product_id"],
            product_name=row["product_name"],
            price=row["price"],
            qty=row["qty"],
            line_total=row["line_total"],
            is_on_order=row["is_on_order"],
            order_days=row["order_days"],
        )
        for row in rows
    ]


async def _load_order_items_bulk(order_ids: list[int]) -> dict[int, list[OrderItemOut]]:
    """Позиции всех заказов одним запросом (иначе N+1 и долгая загрузка)."""
    if not order_ids:
        return {}
    rows = await db.fetch(
        """
        SELECT order_id, product_id, product_name, price, qty, line_total,
               is_on_order, order_days
        FROM order_items WHERE order_id = ANY($1::int[]) ORDER BY id
        """,
        order_ids,
    )
    grouped: dict[int, list[OrderItemOut]] = {}
    for row in rows:
        grouped.setdefault(row["order_id"], []).append(
            OrderItemOut(
                product_id=row["product_id"],
                product_name=row["product_name"],
                price=row["price"],
                qty=row["qty"],
                line_total=row["line_total"],
                is_on_order=row["is_on_order"],
                order_days=row["order_days"],
            )
        )
    return grouped


async def _load_order_events_bulk(order_ids: list[int]) -> dict[int, list[OrderEventOut]]:
    """История всех заказов одним запросом (иначе N+1 и долгая загрузка)."""
    if not order_ids:
        return {}
    rows = await db.fetch(
        """
        SELECT id, order_id, status, note, actor, created_at
        FROM order_events WHERE order_id = ANY($1::int[]) ORDER BY id
        """,
        order_ids,
    )
    grouped: dict[int, list[OrderEventOut]] = {}
    for row in rows:
        grouped.setdefault(row["order_id"], []).append(
            OrderEventOut(
                id=row["id"],
                status=row["status"],
                status_label=_status_label(row["status"]),
                note=row["note"],
                actor=row["actor"],
                created_at=row["created_at"],
            )
        )
    return grouped


async def _build_order_out(
    row,
    *,
    telegram_sent: bool,
    delivery: str,
    items: list[OrderItemOut] | None = None,
    events: list[OrderEventOut] | None = None,
) -> OrderOut:
    """Собрать заказ из строки БД.

    Позиции и события можно передать готовыми: для списка заказов они
    загружаются одним запросом на все заказы, а не по одному (N+1).
    """
    if items is None:
        items = await _load_order_items(row["id"])
    if events is None:
        events = await _load_order_events(row["id"])
    return OrderOut(
        id=row["id"],
        order_number=row["order_number"],
        total=row["total"],
        pickup_method=row["pickup_method"],
        is_night_order=row["is_night_order"],
        has_on_order=row.get("has_on_order", False),
        status=row["status"],
        status_label=_status_label(row["status"]),
        completed_at=row.get("completed_at"),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        customer_name=row["customer_name"],
        phone=row["phone"],
        telegram=row["telegram"],
        car_make=row["car_make"],
        car_model=row["car_model"],
        vin=row["vin"],
        address=row["address"],
        comment=row["comment"],
        items=items,
        events=events,
        telegram_sent=telegram_sent,
        telegram_delivery=delivery,
    )


# ---------------------------------------------------------------------------
# Базовые
# ---------------------------------------------------------------------------


@app.get("/api/health")
async def health() -> dict[str, str]:
    """Проверка живости API, соединения с БД и готовности Telegram.

    Статус Telegram отражает фактическую готовность отправлять
    уведомления: MCP недоступен (нет `uvx` на хостинге) — не значит,
    что Telegram сломан, потому что работает резервный Bot API.
    """
    try:
        await db.fetchval("SELECT 1")
        db_status = "ok"
    except Exception as exc:  # noqa: BLE001
        db_status = f"error: {exc}"

    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        telegram_status = "ready"
    else:
        telegram_status = "disabled"

    return {
        "status": "ok",
        "database": db_status,
        "telegram": telegram_status,
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


async def _load_compatibility(product_ids: list[int]) -> dict[int, list[CompatibilityOut]]:
    """Совместимость деталей с авто: product_id -> список записей."""
    if not product_ids:
        return {}
    rows = await db.fetch(
        """
        SELECT id, product_id, make, model, year_from, year_to
        FROM product_compatibility
        WHERE product_id = ANY($1::int[])
        ORDER BY make, model NULLS FIRST, year_from NULLS FIRST
        """,
        product_ids,
    )
    grouped: dict[int, list[CompatibilityOut]] = {}
    for row in rows:
        grouped.setdefault(row["product_id"], []).append(
            CompatibilityOut(
                id=row["id"],
                make=row["make"],
                model=row["model"],
                year_from=row["year_from"],
                year_to=row["year_to"],
            )
        )
    return grouped


def _fits_car(
    compatibility: list[CompatibilityOut],
    make: str | None,
    model: str | None,
    year: int | None,
) -> bool:
    """Подходит ли деталь к выбранному автомобилю.

    Деталь без записей совместимости считается универсальной — подходит
    к любому авто. Если записи есть, марка/модель/год должны совпасть.
    """
    if not compatibility:
        return True
    wanted_make = (make or "").strip().upper()
    wanted_model = (model or "").strip().upper()
    for item in compatibility:
        if wanted_make and item.make.upper() != wanted_make:
            continue
        if wanted_model:
            item_model = (item.model or "").upper()
            if item_model and item_model != wanted_model:
                continue
        if year is not None:
            if item.year_from is not None and year < item.year_from:
                continue
            if item.year_to is not None and year > item.year_to:
                continue
        return True
    return False


@app.get("/api/products", response_model=list[ProductOut])
async def list_products(
    on_order_only: bool = False,
    in_stock_only: bool = False,
    car_make: str | None = None,
    car_model: str | None = None,
    car_year: int | None = None,
) -> list[ProductOut]:
    """Каталог витрины.

    Показываем и детали в наличии, и детали под заказ — клиент должен видеть,
    что можно заказать. Товары «нет в наличии и не под заказ» скрыты.

    car_make / car_model / car_year — фильтр по выбранному автомобилю.
    """
    rows = await db.fetch(
        """
        SELECT id, sku, name, brand, category, price, old_price, discount_percent,
               image_url, in_stock, is_active, is_on_order, order_days, description
        FROM products
        WHERE is_active = TRUE
          AND (in_stock OR is_on_order)
        ORDER BY in_stock DESC, is_on_order ASC, category, price
        """
    )
    products = [ProductOut(**dict(row)) for row in rows]

    compatibility_map = await _load_compatibility([item.id for item in products])
    for item in products:
        item.compatibility = compatibility_map.get(item.id, [])

    # Флаги «в наличии» и «под заказ» — одно измерение, поэтому
    # одновременно дают объединение, а не пустое пересечение.
    if on_order_only or in_stock_only:
        products = [
            item
            for item in products
            if (in_stock_only and item.in_stock)
            or (on_order_only and item.is_on_order and not item.in_stock)
        ]
    if car_make or car_model or car_year:
        products = [
            item
            for item in products
            if _fits_car(item.compatibility, car_make, car_model, car_year)
        ]
    return products


@app.get("/api/cars/makes")
async def car_makes(q: str = "", limit: int = 12) -> dict[str, object]:
    """Подсказки по маркам: по первым буквам названия или русскому синониму."""
    matches = cars.search_makes(q, limit=max(1, min(limit, 40)))
    return {
        "query": q,
        "makes": matches,
        "total": len(cars.CAR_MAKES),
    }


@app.get("/api/cars/models")
async def car_models(
    make: str = "", q: str = "", limit: int = 20
) -> dict[str, object]:
    """Подсказки по моделям выбранной марки."""
    canonical = cars.resolve_make(make) or ""
    matches = cars.search_models(canonical, q, limit=max(1, min(limit, 60)))
    return {
        "make": canonical,
        "query": q,
        "models": matches,
        "total": len(cars.CAR_CATALOG.get(canonical, [])),
    }


@app.get("/api/cars/years")
async def car_years(make: str = "", model: str = "") -> dict[str, object]:
    """Годы выпуска, для которых есть детали в каталоге.

    Пустой список — значит под выбранную марку/модель деталей пока нет,
    клиент всё равно может выбрать год вручную из общего диапазона.
    """
    canonical = cars.resolve_make(make) or ""
    params: list[object] = [canonical]
    query = "SELECT DISTINCT year_from, year_to FROM product_compatibility WHERE make = $1"
    if model.strip():
        params.append(model.strip())
        query += " AND model = $2"
    query += " ORDER BY year_from NULLS FIRST"

    rows = await db.fetch(query, *params)
    years: set[int] = set()
    for row in rows:
        start = row["year_from"]
        end = row["year_to"]
        if start is None and end is None:
            continue
        low = start if start is not None else end
        high = end if end is not None else start
        years.update(range(int(low), int(high) + 1))
    return {
        "make": canonical,
        "model": model.strip(),
        "years": sorted(years, reverse=True),
    }


@app.get("/api/cars/vin")
async def car_vin(vin: str = "") -> dict[str, object]:
    """Разбор VIN: марка (WMI) и год выпуска (позиция 10)."""
    return vin_parser.decode_vin(vin)


async def _store_overrides() -> dict[str, str]:
    """Все настройки магазина из БД (таблица store_settings).

    Значения здесь имеют приоритет над дефолтами из settings.py (которые,
    в свою очередь, берутся из .env). Так владелец правит магазин из кабинета.
    """
    rows = await db.fetch("SELECT key, value FROM store_settings")
    return {r["key"]: r["value"] for r in rows if r["key"] is not None}


def _parse_hour(value: str | None, default: int) -> int:
    """Целочасовой переопределитель: пусто/пусто → дефолт из настроек."""
    if value is None or str(value).strip() == "":
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _work_hours_from_overrides(ov: dict[str, str]) -> tuple[int, int, str]:
    """Возвращает (open_hour, close_hour, work_hours_str) для отображения.

    Приоритет: явные open_hour/close_hour → разбор work_hours («09:00–20:00»)
    → дефолты настроек.
    """
    if "work_hours" in ov and str(ov["work_hours"]).strip():
        import re

        m = re.match(
            r"\s*(\d{1,2}):(\d{2})\s*[-–—]\s*(\d{1,2}):(\d{2})",
            str(ov["work_hours"]),
        )
        if m:
            open_h, _, close_h = int(m.group(1)), m.group(2), int(m.group(4))
            return open_h, close_h, str(ov["work_hours"]).strip()
    open_h = _parse_hour(ov.get("open_hour"), settings.STORE_OPEN_HOUR)
    close_h = _parse_hour(ov.get("close_hour"), settings.STORE_CLOSE_HOUR)
    wh = f"{open_h:02d}:00–{close_h:02d}:00"
    return open_h, close_h, wh


@app.get("/api/store")
async def store_info() -> dict[str, object]:
    """Режим работы и контакты магазина — фронтенд показывает их клиенту.

    Приоритет источников: настройки в БД (store_settings) > переменные
    окружения (.env) > вшитые дефолты. Поэтому один и тот же код работает
    для любого клиента — достаточно правки настроек.
    """
    ov = await _store_overrides()
    name = ov.get("name") or settings.STORE_NAME
    slogan = ov.get("slogan") or settings.STORE_SLOGAN
    city = ov.get("city") or settings.STORE_CITY
    phone = ov.get("phone") or settings.STORE_PHONE
    phone_href = ov.get("phone_href") or settings.STORE_PHONE_HREF
    address = ov.get("address") or settings.STORE_ADDRESS
    maps_url = ov.get("maps_url") or settings.STORE_MAPS_URL
    logo = ov.get("logo") or settings.STORE_LOGO
    open_hour, close_hour, work_hours = _work_hours_from_overrides(ov)

    store_tz = timezone(timedelta(hours=settings.STORE_UTC_OFFSET_HOURS))
    now = datetime.now(store_tz)
    is_open = open_hour <= now.hour < close_hour
    return {
        "name": name,
        "slogan": slogan,
        "city": city,
        "phone": phone,
        "phone_href": phone_href,
        "address": address,
        "maps_url": maps_url,
        "logo": logo,
        "lat": settings.STORE_LAT,
        "lon": settings.STORE_LON,
        "rating": settings.STORE_RATING,
        "rating_count": settings.STORE_RATING_COUNT,
        "open_hour": open_hour,
        "close_hour": close_hour,
        "work_hours": work_hours,
        "is_open": is_open,
        "local_time": now.isoformat(timespec="minutes"),
        "night_start_hour": settings.NIGHT_ORDER_START_HOUR,
        "night_end_hour": settings.NIGHT_ORDER_END_HOUR,
        "pickup_only": True,
    }


# ---------------------------------------------------------------------------
# Аккаунты
# ---------------------------------------------------------------------------


@app.post("/api/auth/register", response_model=AuthOut, status_code=201)
async def register(payload: RegisterIn) -> AuthOut:
    """Регистрация клиента в личном кабинете."""
    existing = await db.fetchval(
        "SELECT 1 FROM users WHERE email = $1", payload.email
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Пользователь с таким e-mail уже зарегистрирован",
        )
    row = await db.fetchrow(
        """
        INSERT INTO users (email, password_hash, full_name, phone, telegram)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id, email, full_name, phone, telegram, role, created_at
        """,
        payload.email,
        auth.hash_password(payload.password),
        payload.full_name,
        payload.phone,
        payload.telegram,
    )
    token = await auth.create_session(row["id"])
    return AuthOut(token=token, user=_user_out(dict(row)))


@app.post("/api/auth/login", response_model=AuthOut)
async def login(payload: LoginIn) -> AuthOut:
    """Вход по e-mail и паролю."""
    row = await db.fetchrow(
        """
        SELECT id, email, password_hash, full_name, phone, telegram, role, created_at
        FROM users WHERE email = $1
        """,
        payload.email.strip().lower(),
    )
    if row is None or not auth.verify_password(
        payload.password, row["password_hash"]
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный e-mail или пароль",
        )
    token = await auth.create_session(row["id"])
    return AuthOut(token=token, user=_user_out(dict(row)))


@app.post("/api/auth/logout", status_code=204)
async def logout(request: Request) -> None:
    """Выход — сессия удаляется."""
    token = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if token:
        await auth.drop_session(token)


@app.get("/api/auth/me", response_model=UserOut)
async def me(user: dict = Depends(auth.current_user_optional)) -> UserOut:
    """Текущий пользователь или 401."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Не авторизован"
        )
    return _user_out(user)


# ---------------------------------------------------------------------------
# Заказы
# ---------------------------------------------------------------------------


def _format_order_number(moment: datetime, sequence_value: int) -> str:
    """Человекочитаемый номер заказа: A-YYMMDD-0001."""
    return f"A-{moment.strftime('%y%m%d')}-{sequence_value:04d}"


def _parse_date(value: str) -> date:
    """Разбирает дату ГГГГ-ММ-ДД. asyncpg требует объект date, не строку."""
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail=f"Некорректная дата: {value}"
        ) from exc


@app.post("/api/orders", response_model=OrderOut, status_code=201)
async def create_order(
    payload: OrderIn,
    user: dict | None = Depends(auth.current_user_optional),
) -> OrderOut:
    """Оформить заказ: сохранить в PostgreSQL и отправить в Telegram."""
    if payload.pickup_method != "pickup":
        raise HTTPException(
            status_code=422, detail="Доставка недоступна — только самовывоз"
        )
    if not payload.phone:
        raise HTTPException(status_code=422, detail="Укажите телефон для связи")

    # Сверяем позиции с каталогом — цены берём из БД, не из клиента.
    product_ids = sorted({item.product_id for item in payload.items})
    rows = await db.fetch(
        """
        SELECT id, name, price, in_stock, is_active, is_on_order, order_days
        FROM products WHERE id = ANY($1::int[])
        """,
        product_ids,
    )
    catalog = {row["id"]: row for row in rows}
    missing = [pid for pid in product_ids if pid not in catalog]
    if missing:
        raise HTTPException(
            status_code=422, detail=f"Товары не найдены в каталоге: {missing}"
        )
    # Деталь под заказ заказать можно — она приедет от поставщика.
    unavailable = [
        catalog[pid]["name"]
        for pid in product_ids
        if not catalog[pid]["is_on_order"]
        and (not catalog[pid]["in_stock"] or not catalog[pid]["is_active"])
    ]
    if unavailable:
        raise HTTPException(
            status_code=422,
            detail=f"Нет в наличии: {', '.join(unavailable)}",
        )

    items: list[tuple[str, int, Decimal, bool, int]] = []
    for item in payload.items:
        product = catalog[item.product_id]
        items.append(
            (
                product["name"],
                item.qty,
                product["price"],
                product["is_on_order"],
                product["order_days"] if product["is_on_order"] else 0,
            )
        )
    total = sum((price * qty for _, qty, price, _, _ in items), start=Decimal("0"))
    has_on_order = any(on_order for _, _, _, on_order, _ in items)
    max_order_days = max((days for _, _, _, _, days in items), default=0)

    store_tz = timezone(timedelta(hours=settings.STORE_UTC_OFFSET_HOURS))
    created_at = datetime.now(store_tz)
    night = is_night_order(created_at)

    sequence_value = await db.fetchval("SELECT nextval('order_num_seq')")
    order_number = _format_order_number(created_at, int(sequence_value))

    car_parts = [payload.car_make, payload.car_model]
    car_info = " ".join(part.strip() for part in car_parts if part and part.strip())
    if payload.vin:
        car_info = f"{car_info} (VIN {payload.vin})".strip()

    # Марку приводим к каноническому виду справочника (KIA, а не «Киа»).
    car_make = cars.resolve_make(payload.car_make)
    car_model = payload.car_model.strip() if payload.car_model else None

    user_id = user["id"] if user else None

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            order_row = await conn.fetchrow(
                """
                INSERT INTO orders (
                    order_number, user_id, customer_name, phone, telegram,
                    car_make, car_model, vin, pickup_method, address,
                    comment, total, is_night_order, has_on_order, status, created_at
                )
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,'new',$15)
                RETURNING id, order_number, total, pickup_method,
                              is_night_order, has_on_order, status, completed_at,
                              created_at, updated_at, customer_name, phone, telegram,
                              car_make, car_model, vin, address, comment
                """,
                order_number,
                user_id,
                payload.customer_name,
                payload.phone,
                payload.telegram,
                car_make,
                car_model,
                payload.vin,
                payload.pickup_method,
                payload.address,
                payload.comment,
                total,
                night,
                has_on_order,
                created_at,
            )
            for item, (name, qty, price, on_order, order_days) in zip(
                payload.items, items
            ):
                await conn.execute(
                    """
                    INSERT INTO order_items (
                        order_id, product_id, product_name, price, qty,
                        line_total, is_on_order, order_days
                    )
                    VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
                    """,
                    order_row["id"],
                    item.product_id,
                    name,
                    price,
                    qty,
                    price * qty,
                    on_order,
                    order_days,
                )
            await conn.execute(
                """
                INSERT INTO order_events (order_id, status, note, actor)
                VALUES ($1, 'new', $2, $3)
                """,
                order_row["id"],
                "Заказ оформлен на витрине"
                + (
                    f"; есть позиции под заказ (до {max_order_days} дн.)"
                    if has_on_order
                    else ""
                ),
                "customer" if user_id else "guest",
            )

    logger.info(
        "Заказ %s создан, сумма %s (user_id=%s)", order_number, total, user_id
    )

    sent, channel = await notifier.send_order_notification(
        order_id=order_row["id"],
        order_number=order_number,
        customer_name=payload.customer_name,
        phone=payload.phone,
        telegram=payload.telegram,
        car_info=car_info or None,
        pickup_label=PICKUP_LABELS[payload.pickup_method],
        address=payload.address,
        items=[
            (name, qty, float(price), on_order, order_days)
            for name, qty, price, on_order, order_days in items
        ],
        total=float(total),
        comment=payload.comment,
        created_at=created_at,
        is_night=night,
    )
    if not sent:
        logger.error("Заказ %s сохранён, но Telegram-уведомление не ушло", order_number)

    return await _build_order_out(
        order_row, telegram_sent=sent, delivery=channel
    )


@app.get("/api/orders/{order_number}", response_model=OrderOut)
async def get_order(
    order_number: str,
    phone: str | None = None,
    user: dict | None = Depends(auth.current_user_optional),
) -> OrderOut:
    """Заказ по номеру.

    Доступ: владелец магазина, сам клиент (если заказ привязан к аккаунту)
    или любой, кто знает номер и телефон клиента (для гостевого заказа).
    """
    order_row = await db.fetchrow(
        """
        SELECT id, order_number, user_id, customer_name, phone, telegram,
               car_make, car_model, vin, pickup_method, address, comment,
               total, is_night_order, has_on_order, status, completed_at,
               created_at, updated_at
        FROM orders WHERE order_number = $1
        """,
        order_number,
    )
    if order_row is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    is_owner = user is not None and user["role"] == "owner"
    is_owner_of_order = (
        user is not None
        and order_row["user_id"] is not None
        and order_row["user_id"] == user["id"]
    )
    phone_matches = bool(phone) and phone.strip() == (order_row["phone"] or "").strip()

    if not (is_owner or is_owner_of_order or phone_matches):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нужен вход в кабинет или телефон клиента из заказа",
        )

    return await _build_order_out(order_row, telegram_sent=True, delivery="stored")


# ---------------------------------------------------------------------------
# Кабинет клиента
# ---------------------------------------------------------------------------


@app.get("/api/cabinet/orders", response_model=list[OrderOut])
async def my_orders(user: dict = Depends(auth.current_user)) -> list[OrderOut]:
    """Все заказы клиента — с таймлайном статусов."""
    rows = await db.fetch(
        """
        SELECT id, order_number, total, pickup_method, is_night_order,
               has_on_order, status, completed_at,
               created_at, updated_at, customer_name, phone, telegram,
               car_make, car_model, vin, address, comment
        FROM orders
        WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        user["id"],
    )
    order_ids = [row["id"] for row in rows]
    # Позиции и события грузим параллельно: к Neon идёт два раунд-tripа
    # вместо трёх последовательных.
    items_map, events_map = await asyncio.gather(
        _load_order_items_bulk(order_ids),
        _load_order_events_bulk(order_ids),
    )
    return [
        await _build_order_out(
            row,
            telegram_sent=True,
            delivery="stored",
            items=items_map.get(row["id"], []),
            events=events_map.get(row["id"], []),
        )
        for row in rows
    ]


@app.get("/api/orders/{order_number}/telegram-link")
async def order_telegram_link(
    order_number: str,
    user: dict | None = Depends(auth.current_user_optional),
) -> dict[str, object]:
    """Ссылка для подписки клиента на уведомления о заказе.

    Клиент открывает t.me/<bot>?start=<номер заказа> — бот запоминает его
    chat_id и дальше присылает сообщения о смене статуса.

    Доступ: владелец заказа, заказ по номеру с телефоном или любой
    авторизованный пользователь с совпадающим telegram.
    """
    row = await db.fetchrow(
        """
        SELECT id, order_number, user_id, customer_name, phone, telegram,
               telegram_chat_id
        FROM orders WHERE order_number = $1
        """,
        order_number,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    is_owner = user is not None and user["role"] == "owner"
    is_owner_of_order = (
        user is not None
        and row["user_id"] is not None
        and row["user_id"] == user["id"]
    )
    phone_matches = bool(user) and (
        (user.get("phone") or "").strip() == (row["phone"] or "").strip()
        and (row["phone"] or "").strip() != ""
    )
    if not (is_owner or is_owner_of_order or phone_matches):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Нужен вход или телефон клиента из этого заказа",
        )

    bot_username = settings.TELEGRAM_BOT_USERNAME
    link = (
        f"https://t.me/{bot_username}?start={order_number}"
        if bot_username
        else ""
    )
    return {
        "order_number": order_number,
        "bot_username": bot_username,
        "link": link,
        "subscribed": row["telegram_chat_id"] is not None,
    }


@app.get("/api/cabinet/orders/{order_number}", response_model=OrderOut)
async def my_order(
    order_number: str, user: dict = Depends(auth.current_user)
) -> OrderOut:
    """Один заказ клиента с подробностями и таймлайном."""
    row = await db.fetchrow(
        """
        SELECT id, order_number, total, pickup_method, is_night_order,
               has_on_order, status, completed_at,
               created_at, updated_at, customer_name, phone, telegram,
               car_make, car_model, vin, address, comment
        FROM orders
        WHERE order_number = $1 AND (user_id = $2 OR $3 = 'owner')
        """,
        order_number,
        user["id"],
        user["role"],
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    return await _build_order_out(row, telegram_sent=True, delivery="stored")


# ---------------------------------------------------------------------------
# Кабинет владельца
# ---------------------------------------------------------------------------


@app.get("/api/admin/orders", response_model=list[OrderOut])
async def admin_orders(
    order_status: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    query: str | None = None,
    night_only: bool = False,
    sort: str = "newest",
    limit: int = 200,
    user: dict = Depends(auth.current_owner),
) -> list[OrderOut]:
    """Заказы магазина (владелец) с фильтрами.

    Фильтры:
      order_status — конкретный статус;
      date_from / date_to — период по дате оформления (ГГГГ-ММ-ДД);
      query — поиск по номеру заказа, имени, телефону или Telegram;
      night_only — только приоритетные заказы (20:00–08:00);
      sort — newest | oldest | night_first.
    """
    limit = max(1, min(limit, 500))

    conditions: list[str] = []
    params: list[object] = []

    if order_status:
        params.append(order_status)
        conditions.append(f"status = ${len(params)}")
    if date_from:
        params.append(_parse_date(date_from))
        conditions.append(f"created_at >= ${len(params)}::date")
    if date_to:
        params.append(_parse_date(date_to))
        conditions.append(f"created_at < (${len(params)}::date + interval '1 day')")
    if query:
        params.append(f"%{query.strip()}%")
        idx = len(params)
        conditions.append(
            "(order_number ILIKE $"
            f"{idx} OR customer_name ILIKE $"
            f"{idx} OR COALESCE(phone, '') ILIKE $"
            f"{idx} OR COALESCE(telegram, '') ILIKE $"
            f"{idx} OR COALESCE(car_make, '') ILIKE $"
            f"{idx} OR COALESCE(car_model, '') ILIKE $"
            f"{idx})"
        )
    if night_only:
        conditions.append("is_night_order = TRUE")

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    order_by = {
        "newest": "created_at DESC",
        "oldest": "created_at ASC",
        "night_first": "is_night_order DESC, created_at DESC",
    }.get(sort, "created_at DESC")

    params.append(limit)
    rows = await db.fetch(
        f"""
        SELECT id, order_number, total, pickup_method, is_night_order,
               has_on_order, status, completed_at,
               created_at, updated_at, customer_name, phone, telegram,
               car_make, car_model, vin, address, comment
        FROM orders {where}
        ORDER BY {order_by}
        LIMIT ${len(params)}
        """,
        *params,
    )
    # Позиции и события всех заказов — одним запросом каждый.
    # Иначе на каждый заказ уходят отдельные запросы, и список грузится
    # десятки секунд (N+1).
    order_ids = [row["id"] for row in rows]
    items_map, events_map = await asyncio.gather(
        _load_order_items_bulk(order_ids),
        _load_order_events_bulk(order_ids),
    )
    return [
        await _build_order_out(
            row,
            telegram_sent=True,
            delivery="stored",
            items=items_map.get(row["id"], []),
            events=events_map.get(row["id"], []),
        )
        for row in rows
    ]


@app.patch("/api/admin/orders/{order_id}", response_model=OrderOut)
async def admin_update_order(
    order_id: int,
    payload: OrderStatusUpdate,
    user: dict = Depends(auth.current_owner),
) -> OrderOut:
    """Сменить статус заказа и записать событие в таймлайн."""
    row = await db.fetchrow(
        "SELECT id FROM orders WHERE id = $1", order_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Заказ не найден")

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await order_status.apply_order_status(
                conn,
                order_id,
                payload.status,
                note=payload.note,
                status_label=_status_label(payload.status),
            )

    updated = await db.fetchrow(
        """
        SELECT id, order_number, total, pickup_method, is_night_order,
               has_on_order, status, completed_at,
               created_at, updated_at, customer_name, phone, telegram,
               telegram_chat_id,
               car_make, car_model, vin, address, comment
        FROM orders WHERE id = $1
        """,
        order_id,
    )
    logger.info(
        "Статус заказа %s изменён на %s", updated["order_number"], payload.status
    )
    # Клиенту сообщаем о смене статуса — по подписке в Telegram.
    await notifier.notify_client_status(
        order_number=updated["order_number"],
        status=payload.status,
        chat_id=updated.get("telegram_chat_id"),
        telegram_username=updated.get("telegram"),
        address=updated.get("address"),
        phone=updated.get("phone"),
    )
    return await _build_order_out(updated, telegram_sent=True, delivery="stored")


async def _replace_compatibility(
    product_id: int, items: list[CompatibilityIn] | None
) -> None:
    """Полностью перезаписать список совместимости товара.

    None — совместимость не передана, ничего не трогаем.
    Замена выполняется одной транзакцией: иначе при ошибке товар остался бы
    без совместимости или с дублями.
    """
    if items is None:
        return

    # Дубли не нужны: одна и та же марка/модель/год — одна строка.
    unique: list[tuple[str, str | None, int | None, int | None]] = []
    seen: set[tuple[str, str | None, int | None, int | None]] = set()
    for item in items:
        key = (item.make, item.model, item.year_from, item.year_to)
        if key in seen:
            continue
        seen.add(key)
        unique.append(key)

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                "DELETE FROM product_compatibility WHERE product_id = $1", product_id
            )
            if unique:
                await conn.executemany(
                    """
                    INSERT INTO product_compatibility
                        (product_id, make, model, year_from, year_to)
                    VALUES ($1,$2,$3,$4,$5)
                    """,
                    [
                        (product_id, make, model, year_from, year_to)
                        for make, model, year_from, year_to in unique
                    ],
                )


@app.get("/api/admin/products", response_model=list[ProductOut])
async def admin_products(user: dict = Depends(auth.current_owner)) -> list[ProductOut]:
    """Полный каталог, включая скрытые и отсутствующие в наличии."""
    rows = await db.fetch(
        """
        SELECT id, sku, name, brand, category, price, old_price, discount_percent,
               image_url, in_stock, is_active, is_on_order, order_days, description
        FROM products ORDER BY id
        """
    )
    products = [ProductOut(**dict(row)) for row in rows]
    compatibility_map = await _load_compatibility([item.id for item in products])
    for item in products:
        item.compatibility = compatibility_map.get(item.id, [])
    return products


@app.post("/api/admin/products", response_model=ProductOut, status_code=201)
async def admin_create_product(
    payload: ProductIn, user: dict = Depends(auth.current_owner)
) -> ProductOut:
    """Добавить товар в каталог."""
    existing = await db.fetchval(
        "SELECT 1 FROM products WHERE sku = $1", payload.sku
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Товар с артикулом {payload.sku} уже есть",
        )
    row = await db.fetchrow(
        """
        INSERT INTO products
            (sku, name, brand, category, price, old_price, discount_percent,
             in_stock, is_active, is_on_order, order_days, description)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        RETURNING id, sku, name, brand, category, price, old_price,
                  discount_percent, image_url, in_stock, is_active,
                  is_on_order, order_days, description
        """,
        payload.sku,
        payload.name,
        payload.brand,
        payload.category,
        payload.price,
        payload.old_price,
        payload.discount_percent,
        payload.in_stock,
        payload.is_active,
        payload.is_on_order,
        payload.order_days,
        payload.description,
    )
    await _replace_compatibility(row["id"], payload.compatibility)
    logger.info("Добавлен товар %s (%s)", payload.sku, payload.name)
    product = ProductOut(**dict(row))
    stored = await _load_compatibility([row["id"]])
    product.compatibility = stored.get(row["id"], [])
    return product


@app.patch("/api/admin/products/{product_id}", response_model=ProductOut)
async def admin_update_product(
    product_id: int,
    payload: ProductIn,
    user: dict = Depends(auth.current_owner),
) -> ProductOut:
    """Изменить товар: цена, скидка, наличие, статус «под заказ»."""
    exists = await db.fetchval(
        "SELECT 1 FROM products WHERE id = $1", product_id
    )
    if not exists:
        raise HTTPException(status_code=404, detail="Товар не найден")

    duplicate = await db.fetchval(
        "SELECT 1 FROM products WHERE sku = $1 AND id <> $2",
        payload.sku,
        product_id,
    )
    if duplicate:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Артикул {payload.sku} уже занят другим товаром",
        )

    row = await db.fetchrow(
        """
        UPDATE products SET
            sku = $1, name = $2, brand = $3, category = $4, price = $5,
            old_price = $6, discount_percent = $7, in_stock = $8,
            is_active = $9, is_on_order = $10, order_days = $11,
            description = $12, updated_at = now()
        WHERE id = $13
        RETURNING id, sku, name, brand, category, price, old_price,
                  discount_percent, image_url, in_stock, is_active,
                  is_on_order, order_days, description
        """,
        payload.sku,
        payload.name,
        payload.brand,
        payload.category,
        payload.price,
        payload.old_price,
        payload.discount_percent,
        payload.in_stock,
        payload.is_active,
        payload.is_on_order,
        payload.order_days,
        payload.description,
        product_id,
    )
    await _replace_compatibility(product_id, payload.compatibility)
    logger.info(
        "Товар %s обновлён: цена %s, скидка %s%%, под заказ=%s",
        payload.sku,
        payload.price,
        payload.discount_percent,
        payload.is_on_order,
    )
    product = ProductOut(**dict(row))
    # Отдаём фактически сохранённую совместимость: входной список мог
    # содержать дубли, а в базе они схлопываются.
    stored = await _load_compatibility([product_id])
    product.compatibility = stored.get(product_id, [])
    return product


@app.delete("/api/admin/products/{product_id}")
async def admin_delete_product(
    product_id: int,
    restore: bool = False,
    user: dict = Depends(auth.current_owner),
) -> dict[str, object]:
    """Скрыть товар с витрины (мягкое удаление) или восстановить его.

    Позиции уже оформленных заказов не удаляются — у них есть ссылка на
    товар, а история заказа должна оставаться цельной.
    """
    row = await db.fetchrow(
        "SELECT id, sku FROM products WHERE id = $1", product_id
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Товар не найден")
    await db.execute(
        "UPDATE products SET is_active = $1, updated_at = now() WHERE id = $2",
        restore,
        product_id,
    )
    logger.info(
        "Товар %s %s", row["sku"], "восстановлен" if restore else "скрыт"
    )
    return {
        "id": product_id,
        "sku": row["sku"],
        "is_active": restore,
    }


@app.get("/api/admin/stats")
async def admin_stats(user: dict = Depends(auth.current_owner)) -> dict[str, object]:
    """Сводка для дашборда владельца."""
    totals = await db.fetchrow(
        """
        SELECT
            (SELECT count(*) FROM orders) AS orders_total,
            (SELECT count(*) FROM orders WHERE status = 'new') AS orders_new,
            (SELECT count(*) FROM orders WHERE created_at::date = current_date)
                AS orders_today,
            -- Выручка — только по выполненным заказам. Заказ пришёл, но ещё
            -- в работе (new/accepted/in_progress/ready) — деньги не получены,
            -- поэтому в выручку не входит. Статус completed — сумма добавилась.
            -- «Сегодня» считается по часовому поясу магазина, а не по UTC.
            (SELECT COALESCE(sum(total), 0) FROM orders
                WHERE status = 'completed') AS revenue_total,
            (SELECT COALESCE(sum(total), 0) FROM orders
                WHERE status = 'completed'
                    AND (completed_at + make_interval(hours => $1))::date
                        = (now() + make_interval(hours => $1))::date
                ) AS revenue_today,
            -- В работе: заказы, которые ещё не выданы и не отменены.
            -- Показывает, сколько денег пока не получено.
            (SELECT COALESCE(sum(total), 0) FROM orders
                WHERE status IN ('new', 'accepted', 'in_progress', 'ready')
                ) AS revenue_pending,
            (SELECT count(*) FROM orders WHERE status = 'completed')
                AS orders_completed,
            (SELECT count(*) FROM products WHERE is_active) AS products_active,
            (SELECT count(*) FROM products WHERE NOT is_active) AS products_hidden,
            (SELECT count(*) FROM products WHERE in_stock AND is_active)
                AS products_in_stock,
            (SELECT count(*) FROM users WHERE role = 'customer') AS customers
        """,
        settings.STORE_UTC_OFFSET_HOURS,
    )
    by_status = await db.fetch(
        "SELECT status, count(*) AS cnt FROM orders GROUP BY status"
    )
    return {
        "totals": dict(totals),
        "by_status": {row["status"]: row["cnt"] for row in by_status},
        "statuses": ORDER_STATUS_LABELS,
    }


# ---------------------------------------------------------------------------
# Настройки магазина (white-label) — кабинет владельца
# ---------------------------------------------------------------------------


@app.get("/api/admin/store-settings")
async def admin_get_store_settings(
    user: dict = Depends(auth.current_owner),
) -> dict[str, object]:
    """Текущие editable-настройки магазина (то, что лежит в БД).

    None = переопределения нет → на витрине берётся дефолт из .env.
    Фронтенд подставляет дефолты, чтобы форма не была пустой.
    """
    ov = await _store_overrides()
    return {key: (ov.get(key) if key in ov else None) for key in STORE_SETTINGS_KEYS}


@app.put("/api/admin/store-settings")
async def admin_update_store_settings(
    payload: StoreSettingsIn,
    user: dict = Depends(auth.current_owner),
) -> dict[str, object]:
    """Сохранить настройки магазина. Только владелец.

    Учитываются только переданные поля. Непустое значение — переопределяет
    дефолт; пустая строка / None — снимает переопределение (возврат к .env).
    """
    changes = {
        key: value
        for key, value in payload.model_dump(exclude_unset=True).items()
        if key in STORE_SETTINGS_KEYS
    }
    saved: list[str] = []
    cleared: list[str] = []
    async with db.transaction() as conn:
        for key, value in changes.items():
            if value is None or str(value).strip() == "":
                await conn.execute("DELETE FROM store_settings WHERE key = $1", key)
                cleared.append(key)
            else:
                await conn.execute(
                    """
                    INSERT INTO store_settings (key, value) VALUES ($1, $2)
                    ON CONFLICT (key) DO UPDATE
                    SET value = EXCLUDED.value, updated_at = now()
                    """,
                    key,
                    str(value),
                )
                saved.append(key)
    logger.info(
        "Настройки магазина обновлены (%s): изменены=%s, сняты=%s",
        user.get("email"),
        saved,
        cleared,
    )
    ov = await _store_overrides()
    return {key: (ov.get(key) if key in ov else None) for key in STORE_SETTINGS_KEYS}
