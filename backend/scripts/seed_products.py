"""Заполнение каталога products тестовыми данными (idempotent).

Запуск:  python backend/scripts/seed_products.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR.parent))

from backend import db  # noqa: E402

PRODUCTS = [
    (
        "BRK-001",
        "Тормозные колодки, комплект",
        "Brembo",
        "Тормоза",
        4890,
        5490,
        True,
        "Комплект передних колодок, 4 шт.",
    ),
    (
        "OIL-002",
        "Моторное масло 5W-30, 4 л",
        "Shell Helix",
        "Масло и жидкости",
        2450,
        None,
        True,
        "Синтетика API SP, канистра 4 литра.",
    ),
    (
        "FLT-003",
        "Масляный фильтр",
        "MANN",
        "Фильтры",
        450,
        520,
        True,
        "Для бензиновых двигателей 1.6-2.0 л.",
    ),
    (
        "FLT-004",
        "Воздушный фильтр",
        "Bosch",
        "Фильтры",
        780,
        None,
        True,
        "Повышенной очистки.",
    ),
    (
        "SPK-005",
        "Свечи зажигания, комплект 4 шт.",
        "NGK",
        "Свечи",
        1360,
        1590,
        True,
        "Никель-молибден, зазор 1.1 мм.",
    ),
    (
        "BAT-006",
        "Аккумулятор 60 Ач",
        "Varta",
        "Электро",
        5600,
        None,
        True,
        "Кальциевый, 600 А CCA.",
    ),
    (
        "BEL-007",
        "Ремень ГРМ, комплект",
        "Gates",
        "Двигатель",
        3280,
        None,
        True,
        "Ремень и ролики, для 1.6 л.",
    ),
    (
        "WPR-008",
        "Комплект дворников",
        "Bosch",
        "Кузов",
        890,
        None,
        True,
        "Два дворника, 600/450 мм.",
    ),
    (
        "SHT-009",
        "Тормозные диски, комплект",
        "TRW",
        "Тормоза",
        5640,
        6290,
        True,
        "Вентилируемые, 280 мм.",
    ),
    (
        "SUS-010",
        "Стойка стабилизатора, пара",
        "Lemforder",
        "Подвеска",
        4720,
        None,
        False,
        "Передние, с опорными втулками.",
    ),
]


def _discount_percent(price: float | None, old_price: float | None) -> int:
    """Процент скидки от старой цены (округление вниз)."""
    if not old_price or not price or old_price <= price:
        return 0
    return int((1 - price / old_price) * 100)


async def main() -> int:
    pool = await db.get_pool()
    async with pool.acquire() as conn:
        await conn.executemany(
            """
            INSERT INTO products
                (sku, name, brand, category, price, old_price, discount_percent,
                 in_stock, is_active, description)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            ON CONFLICT (sku) DO UPDATE SET
                name = EXCLUDED.name,
                brand = EXCLUDED.brand,
                category = EXCLUDED.category,
                price = EXCLUDED.price,
                old_price = EXCLUDED.old_price,
                discount_percent = EXCLUDED.discount_percent,
                in_stock = EXCLUDED.in_stock,
                is_active = EXCLUDED.is_active,
                description = EXCLUDED.description,
                updated_at = now()
            """,
            [
                (
                    sku,
                    name,
                    brand,
                    category,
                    price,
                    old_price,
                    _discount_percent(price, old_price),
                    in_stock,
                    True,
                    description,
                )
                for sku, name, brand, category, price, old_price, in_stock, description
                in PRODUCTS
            ],
        )
        count = await conn.fetchval("SELECT count(*) FROM products")
    await db.close_pool()
    print(f"Каталог готов: {count} товаров")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
