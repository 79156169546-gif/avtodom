"""Схемы запросов/ответов API (pydantic v2)."""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field, field_validator

# Способ получения. Магазин работает только на самовывозе, но в базе остаются
# исторические заказы с доставкой — поэтому в ответе тип шире, чем во вводе.
PickupMethod = Literal["pickup", "delivery"]
PickupMethodIn = Literal["pickup"]

_PHONE_DIGITS_RE = re.compile(r"\D")


def normalize_phone(value: str) -> str:
    """Оставляет в телефоне только цифры и плюс (для сравнения и хранения)."""
    cleaned = value.strip()
    prefix = "+" if cleaned.startswith("+") else ""
    digits = _PHONE_DIGITS_RE.sub("", cleaned)
    return f"{prefix}{digits}"


def phone_is_valid(value: str) -> bool:
    """Проверка телефона: реальный номер, а не заглушка вида 111111111.

    Требования: 10–15 цифр, номер не состоит из одной повторяющейся цифры.
    """
    digits = _PHONE_DIGITS_RE.sub("", value)
    if not 10 <= len(digits) <= 15:
        return False
    if len(set(digits)) == 1:
        return False
    # Отсекаем «placeholder»-номера вроде 1234567890 / 0123456789.
    if digits in {
        "1234567890",
        "0123456789",
        "0987654321",
        "1111111111",
        "0000000000",
        "1231231231",
    }:
        return False
    return True

# Жизненный цикл заказа:
#   new → accepted → in_progress → ready → completed
#   в любой момент → rejected / cancelled
OrderStatus = Literal[
    "new",
    "accepted",
    "in_progress",
    "ready",
    "completed",
    "rejected",
    "cancelled",
]

ORDER_STATUSES: tuple[str, ...] = (
    "new",
    "accepted",
    "in_progress",
    "ready",
    "completed",
    "rejected",
    "cancelled",
)

ORDER_STATUS_LABELS: dict[str, str] = {
    "new": "Новый",
    "accepted": "Принят",
    "in_progress": "В работе",
    "ready": "Готов к выдаче",
    "completed": "Выполнен",
    "rejected": "Отклонён",
    "cancelled": "Отменён",
}


# ---------------------------------------------------------------------------
# Каталог
# ---------------------------------------------------------------------------


class CompatibilityIn(BaseModel):
    """Совместимость детали с автомобилем — ввод владельцем."""

    make: str = Field(min_length=1, max_length=80)
    model: str | None = Field(default=None, max_length=80)
    year_from: int | None = Field(default=None, ge=1900, le=2100)
    year_to: int | None = Field(default=None, ge=1900, le=2100)

    @field_validator("make")
    @classmethod
    def _clean_make(cls, value: str) -> str:
        cleaned = value.strip().upper()
        if not cleaned:
            raise ValueError("Укажите марку автомобиля")
        return cleaned

    @field_validator("model")
    @classmethod
    def _clean_model(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class CompatibilityOut(CompatibilityIn):
    id: int


class ProductOut(BaseModel):
    id: int
    sku: str
    name: str
    brand: str | None = None
    category: str | None = None
    price: Decimal
    old_price: Decimal | None = None
    discount_percent: int = 0
    image_url: str | None = None
    in_stock: bool = True
    is_active: bool = True
    is_on_order: bool = False
    order_days: int = 0
    description: str | None = None
    # С какими автомобилями совместима деталь (пусто — подходит ко всем).
    compatibility: list[CompatibilityOut] = []


class ProductIn(BaseModel):
    """Создание/редактирование товара — только владелец."""

    sku: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=100)
    category: str | None = Field(default=None, max_length=100)
    price: Decimal = Field(ge=0, max_digits=12, decimal_places=2)
    old_price: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=2)
    discount_percent: int = Field(default=0, ge=0, le=90)
    in_stock: bool = True
    is_active: bool = True
    is_on_order: bool = False
    order_days: int = Field(default=3, ge=0, le=365)
    description: str | None = Field(default=None, max_length=1000)
    # С какими автомобилями совместима деталь.
    # None — совместимость не передана (не трогаем её);
    # [] — подходит ко всем; список — заменяем целиком.
    compatibility: list[CompatibilityIn] | None = None

    @field_validator("sku")
    @classmethod
    def _upper_sku(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("name")
    @classmethod
    def _clean_name(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Название товара обязательно")
        return cleaned

    @field_validator("order_days")
    @classmethod
    def _check_order_days(cls, value: int, info) -> int:
        # Деталь под заказ без срока поставки бессмысленна — ставим 3 дня.
        if value == 0 and info.data.get("is_on_order"):
            return 3
        return value


# ---------------------------------------------------------------------------
# Заказ
# ---------------------------------------------------------------------------


class OrderItemIn(BaseModel):
    product_id: int
    qty: int = Field(default=1, ge=1, le=99)


class OrderIn(BaseModel):
    items: list[OrderItemIn] = Field(min_length=1)

    # Шаг 1 — авто (необязательно)
    car_make: str | None = Field(default=None, max_length=80)
    car_model: str | None = Field(default=None, max_length=80)
    vin: str | None = Field(default=None, max_length=17)

    # Шаг 3 — получение. Магазин работает только на самовывозе.
    pickup_method: PickupMethodIn = "pickup"
    address: str | None = Field(default=None, max_length=400)

    # Шаг 4 — данные клиента. Имя и телефон обязательны.
    customer_name: str = Field(min_length=2, max_length=120)
    phone: str = Field(min_length=6, max_length=40)
    telegram: str | None = Field(default=None, max_length=80)
    comment: str | None = Field(default=None, max_length=1000)

    @field_validator("customer_name")
    @classmethod
    def _strip_name(cls, value: str) -> str:
        cleaned = value.strip()
        if len(cleaned) < 2:
            raise ValueError("Укажите имя (минимум 2 символа)")
        return cleaned

    @field_validator("vin")
    @classmethod
    def _clean_vin(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip().upper()
        return cleaned or None

    @field_validator("phone")
    @classmethod
    def _clean_phone(cls, value: str) -> str:
        cleaned = normalize_phone(value)
        if not cleaned:
            raise ValueError("Укажите телефон для связи")
        if not phone_is_valid(cleaned):
            raise ValueError(
                "Телефон указан неверно. Введите полный номер, например +7 900 123-45-67"
            )
        return cleaned

    @field_validator("telegram")
    @classmethod
    def _clean_telegram(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        if not cleaned:
            return None
        # Клиент пишет @username — приводим к каноническому виду без @.
        return cleaned.lstrip("@").strip() or None


class OrderItemOut(BaseModel):
    product_id: int | None = None
    product_name: str
    price: Decimal
    qty: int
    line_total: Decimal
    is_on_order: bool = False
    order_days: int = 0


class OrderEventOut(BaseModel):
    id: int
    status: str
    status_label: str
    note: str | None = None
    actor: str
    created_at: datetime


class OrderOut(BaseModel):
    id: int
    order_number: str
    total: Decimal
    pickup_method: PickupMethod
    is_night_order: bool
    has_on_order: bool = False
    status: str
    status_label: str
    # Момент выполнения заказа. По нему начисляется выручка:
    # пока заказ не completed, его сумма в выручку не входит.
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    customer_name: str
    phone: str | None = None
    telegram: str | None = None
    car_make: str | None = None
    car_model: str | None = None
    vin: str | None = None
    address: str | None = None
    comment: str | None = None
    items: list[OrderItemOut]
    events: list[OrderEventOut] = []
    telegram_sent: bool = False
    telegram_delivery: str = ""


class OrderStatusUpdate(BaseModel):
    """Смена статуса заказа — владелец."""

    status: OrderStatus
    note: str | None = Field(default=None, max_length=500)


# ---------------------------------------------------------------------------
# Аккаунты
# ---------------------------------------------------------------------------


class RegisterIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=6, max_length=200)
    full_name: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=40)
    telegram: str | None = Field(default=None, max_length=80)

    @field_validator("email")
    @classmethod
    def _clean_email(cls, value: str) -> str:
        cleaned = value.strip().lower()
        if "@" not in cleaned or "." not in cleaned.split("@")[-1]:
            raise ValueError("Некорректный e-mail")
        return cleaned

    @field_validator("full_name", "phone", "telegram")
    @classmethod
    def _strip(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class LoginIn(BaseModel):
    email: str
    password: str


class UserOut(BaseModel):
    id: int
    email: str
    full_name: str | None = None
    phone: str | None = None
    telegram: str | None = None
    role: str
    created_at: datetime


class AuthOut(BaseModel):
    token: str
    user: UserOut
