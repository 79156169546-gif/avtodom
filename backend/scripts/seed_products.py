"""Наполнение каталога товарами и совместимостью с автомобилями (idempotent).

Скрипт создаёт 60-80 деталей по категориям, с реалистичными названиями,
брендами, ценами и артикулами. Каждой детали назначается совместимость
с 25 автомобилями из справочника backend/cars.py — именно она делает
подбор по «Моему автомобилю» и по VIN рабочим, а не декоративным.

Наличие и статус «под заказ» распределяются случайно, но детерминированно
(фиксированный seed) — повторный запуск даёт тот же каталог.

Запуск:  python backend/scripts/seed_products.py
"""

from __future__ import annotations

import asyncio
import random
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR.parent))

from backend import cars, db  # noqa: E402

SEED = 20241021
# Квота на категорию: 11 позиций на каждую из 7 категорий = 77 товаров.
# Квота нужна, чтобы ни одна категория не осталась пустой.
PER_CATEGORY_COUNT = 11
COMPATIBILITY_PER_PRODUCT = 25

# Категории каталога. Названия совпадают с ключами иконок в
# frontend/src/components/icons.jsx.
CATEGORIES = [
    "Масла и жидкости",
    "Тормозная система",
    "Фильтры",
    "Двигатель",
    "Подвеска",
    "Электрика",
    "Кузовные детали",
]

# Шаблоны деталей: (название, бренд, базовая цена, варианты комплектации).
# Варианты дают разные артикулы и названия внутри одной позиции.
TEMPLATES: dict[str, list[tuple[str, str, int, list[str]]]] = {
    "Масла и жидкости": [
        ("Моторное масло 5W-30, синтетика", "Shell Helix", 2450,
         ["4 л", "4 л + масляный фильтр"]),
        ("Моторное масло 5W-40", "Mobil Super", 2890, ["4 л", "1 л"]),
        ("Моторное масло 0W-20", "Liqui Moly", 2150, ["4 л", "5 л"]),
        ("Моторное масло 5W-30", "Лукойл", 1980, ["4 л", "5 л"]),
        ("Трансмиссионное масло ATF", "Castrol Magnatec", 1650, ["1 л", "4 л"]),
        ("Масло в гидроусилитель", "Mannol", 890, ["1 л", "2 л"]),
        ("Масло для цепи", "Liqui Moly", 1390, ["0,2 л", "1 л"]),
        ("Охлаждающая жидкость G12++", "Felix", 760, ["1 л", "5 л"]),
        ("Тормозная жидкость DOT 4", "ATE", 690, ["0,5 л", "1 л"]),
        ("Масло для двигателей 1.6", "Total", 1950, ["4 л", "5 л"]),
    ],
    "Тормозная система": [
        ("Тормозные колодки, комплект", "Brembo", 4890,
         ["передние", "задние", "передние + задние"]),
        ("Тормозные колодки", "TRW", 2340, ["передние", "задние"]),
        ("Тормозные диски, комплект", "Brembo", 5640, ["280 мм", "300 мм"]),
        ("Тормозные диски", "TRW", 3980, ["260 мм", "280 мм"]),
        ("Тормозной шланг", "ATE", 890, ["310 мм", "345 мм"]),
        ("Тормозной суппорт", "TRW", 3200, ["левый", "правый"]),
        ("Ремень тормозной", "Contitech", 1150, ["1,6 л", "1,8 л"]),
        ("Колодки тормозные барабанные", "Ferodo", 1790, ["задние"]),
        ("Тормозной цилиндр", "ATE", 1420, ["1,5 л", "1,8 л"]),
        ("Комплект тормозных колодок с дисками", "Brembo", 8990,
         ["передний", "задний"]),
    ],
    "Фильтры": [
        ("Масляный фильтр", "MANN", 450, ["для 1.4-1.6", "для 1.8-2.0"]),
        ("Воздушный фильтр", "Bosch", 780, ["стандарт", "спорт"]),
        ("Фильтр салона", "Filtron", 520, ["угольный", "обычный"]),
        ("Топливный фильтр", "Bosch", 1290, ["бензин", "дизель"]),
        ("Масляный фильтр", "Filtron", 620, ["для 1.6", "для 2.0"]),
        ("Воздушный фильтр", "MANN", 910, ["для 1.4-1.6", "для 1.8"]),
        ("Фильтр-сепаратор топлива", "MANN", 2450, ["дизель", "бакт-топливо"]),
        ("Фильтр АКБ", "Filtron", 890, ["под 60 Ач", "под 70 Ач"]),
        ("Фильтр гидроусилителя", "Bosch", 1150, ["стандарт"]),
        ("Комплект фильтров", "MANN", 1890, ["полный набор"]),
    ],
    "Двигатель": [
        ("Ремень ГРМ, комплект", "Gates", 3280, ["1.4", "1.6", "1.8"]),
        ("Свечи зажигания", "NGK", 1360, ["4 шт", "1 шт", "8 шт"]),
        ("Свечи зажигания", "DENSO", 1580, ["4 шт", "1 шт"]),
        ("Прокладка ГБЦ", "Victor Reinz", 2150, ["1.4", "1.6", "2.0"]),
        ("Помпа охлаждения", "Gates", 2480, ["1.4", "1.6", "1.8"]),
        ("Термостат", "Wahler", 1890, ["1.4", "1.6", "2.0"]),
        ("Ремень генератора", "Contitech", 890, ["6PK1370", "6PK1110"]),
        ("Сальники коленвала", "SKF", 2150, ["1.6", "2.0"]),
        ("Крышка клапанов", "Elring", 760, ["пластик", "металл"]),
        ("Шатун двигателя", "Ford", 9800, ["1.4", "1.6"]),
        ("Вкладыши двигателя", "NPR", 13500, ["1.6", "2.0"]),
        ("Турбина турбо", "IHI", 21500, ["1.6 TSI", "2.0 TSI"]),
    ],
    "Подвеска": [
        ("Стойка стабилизатора, пара", "Lemforder", 4720, ["передние", "задние"]),
        ("Амортизатор", "KYB", 2890, ["передний", "задний"]),
        ("Амортизатор", "Sachs", 3450, ["передний", "задний"]),
        ("Пружина подвески", "Lesjöfors", 2380, ["передняя", "задняя"]),
        ("Опора двигателя", "Meyle", 1390, ["правая", "левая", "комплект"]),
        ("Сайлентблок рычага", "CTR", 850, ["передний", "задний"]),
        ("Шаровая опора", "TRW", 1890, ["левая", "правая"]),
        ("Стойка двигателя", "Febi", 1650, ["правая", "левая"]),
        ("Подшипник опорный", "SKF", 980, ["без ABS", "с ABS"]),
        ("Рычаг подвески", "Lemforder", 3200, ["левый", "правый", "комплект"]),
        ("Подушка двигателя", "Febi", 1150, ["верхняя", "нижняя"]),
        ("Стабилизатор поперечной устойчивости", "TRW", 4250, ["передний", "задний"]),
    ],
    "Электрика": [
        ("Аккумулятор 60 Ач", "Varta", 5600, ["обратная полярность", "прямая"]),
        ("Аккумулятор 70 Ач", "Bosch", 7500, ["обратная полярность", "прямая"]),
        ("Стартер", "Bosch", 9800, ["1.4", "1.6", "1.8"]),
        ("Генератор", "Bosch", 16500, ["1.4", "1.6", "2.0"]),
        ("Катушка зажигания", "Valeo", 2100, ["1 шт", "комплект 3 шт"]),
        ("Регулятор напряжения", "Bosch", 2350, ["с щётками", "без щёток"]),
        ("Подушка двигателя электрическая", "Febi", 1150, ["1.6", "2.0"]),
        ("Датчик кислорода", "Bosch", 4250, ["верхний", "нижний"]),
        ("Свеча накаливания", "Bosch", 1890, ["4 шт", "комплект"]),
        ("Пусковое реле", "Valeo", 1350, ["12 В", "1.4 кВт"]),
        ("Клемма аккумулятора", "Varta", 890, ["+", "-", "комплект"]),
        ("Датчик ABS", "TRW", 3200, ["передний", "задний"]),
    ],
    "Кузовные детали": [
        ("Комплект дворников", "Bosch", 890, ["600/450 мм", "650/500 мм"]),
        ("Дворники", "Teyes", 690, ["600/450 мм", "700/500 мм"]),
        ("Бампер передний", "Plymouth", 9800, ["с ПТФ", "без ПТФ"]),
        ("Крыло переднее", "Dura", 4500, ["левое", "правое"]),
        ("Фара", "Depo", 3200, ["левая", "правая"]),
        ("Крыло зеркала", "Avtozvuk", 1650, ["левое", "правое"]),
        ("Решётка радиатора", "Dora", 980, ["1", "2"]),
        ("Капот", "Plymouth", 7500, ["1.4", "1.6"]),
        ("Крышка багажника", "Dura", 1450, ["с камерой", "без камеры"]),
        ("Пороги", "Euler", 2150, ["комплект 4 шт", "комплект 2 шт"]),
        ("Фонарь задний", "Depo", 1980, ["левый", "правый"]),
        ("Крышка двигателя", "Elring", 1320, ["1.4", "1.6"]),
    ],
}

# Модели, чаще всего встречающиеся в РФ: к ним детали подходят чаще.
POPULAR_MODELS = [
    ("LADA", "Granta"), ("LADA", "Vesta"), ("LADA", "Kalina"),
    ("LADA", "Priora"), ("LADA", "Largus"), ("LADA", "Niva"),
    ("KIA", "Rio"), ("KIA", "Ceed"), ("KIA", "Sportage"), ("KIA", "Cerato"),
    ("KIA", "Sorento"), ("KIA", "Soul"), ("KIA", "Rio X"),
    ("HYUNDAI", "Solaris"), ("HYUNDAI", "Accent"), ("HYUNDAI", "Creta"),
    ("HYUNDAI", "Elantra"), ("HYUNDAI", "Santa Fe"), ("HYUNDAI", "i30"),
    ("TOYOTA", "Camry"), ("TOYOTA", "Corolla"), ("TOYOTA", "RAV4"),
    ("TOYOTA", "Avensis"), ("TOYOTA", "Land Cruiser"),
    ("RENAULT", "Logan"), ("RENAULT", "Sandero"), ("RENAULT", "Duster"),
    ("RENAULT", "Megane"), ("RENAULT", "Clio"),
    ("SKODA", "Octavia"), ("SKODA", "Rapid"), ("SKODA", "Fabia"),
    ("SKODA", "Yeti"), ("SKODA", "Kodiaq"),
    ("VOLKSWAGEN", "Polo"), ("VOLKSWAGEN", "Golf"), ("VOLKSWAGEN", "Tiguan"),
    ("VOLKSWAGEN", "Passat"), ("VOLKSWAGEN", "Jetta"),
    ("NISSAN", "Qashqai"), ("NISSAN", "X-Trail"), ("NISSAN", "Almera"),
    ("NISSAN", "Juke"), ("NISSAN", "Sentra"),
    ("FORD", "Focus"), ("FORD", "Fiesta"), ("FORD", "Fusion"),
    ("FORD", "Mondeo"), ("FORD", "EcoSport"),
    ("CHEVROLET", "Cruze"), ("CHEVROLET", "Aveo"), ("CHEVROLET", "Cobalt"),
    ("CHEVROLET", "Lacetti"),
    ("MAZDA", "3"), ("MAZDA", "6"), ("MAZDA", "2"),
    ("MITSUBISHI", "Lancer"), ("MITSUBISHI", "Outlander"),
    ("MITSUBISHI", "ASX"), ("MITSUBISHI", "Pajero"),
    ("CHERY", "Tiggo 4"), ("CHERY", "Tiggo 7"),
    ("GEELY", "Coolray"), ("GEELY", "Emgrand"),
    ("VOLKSWAGEN", "Passat CC"), ("AUDI", "A4"), ("AUDI", "A6"),
    ("BMW", "3 серия"), ("BMW", "X5"), ("VOLVO", "V60"),
    ("SUBARU", "Forester"), ("SUZUKI", "SX4"), ("MITSUBISHI", "Space Star"),
]

# Категории, к которым подходят почти все модели, и более узкие.
UNIVERSAL_CATEGORIES = {"Масла и жидкости", "Фильтры", "Тормозная система"}


def build_products(rng: random.Random) -> list[dict[str, object]]:
    """Собираем список товаров: шаблоны разворачиваются в варианты.

    Каждая категория получает PER_CATEGORY_COUNT позиций, и шаблоны внутри
    неё чередуются по кругу — иначе первая категория «съела» бы весь лимит.
    """
    products: list[dict[str, object]] = []
    counters: dict[str, int] = {}

    for category in CATEGORIES:
        templates = TEMPLATES[category]
        # По одному варианту из каждого шаблона, затем второй — так в категории
        # представлены все бренды, а не только первые.
        # Начинаем с самых дорогих шаблонов: при квоте 11 из 12 позиций
        # категории именно так в каталог попадает турбина и стартер.
        templates = sorted(templates, key=lambda item: item[2], reverse=True)
        rounds: list[tuple[str, str, int, str]] = []
        max_variants = max(len(item[3]) for item in templates)
        for variant_index in range(max_variants):
            for name, brand, base_price, variants in templates:
                if variant_index < len(variants):
                    rounds.append((name, brand, base_price, variants[variant_index]))

        for name, brand, base_price, variant in rounds[:PER_CATEGORY_COUNT]:
            prefix = {
                "Масла и жидкости": "OIL",
                "Тормозная система": "BRK",
                "Фильтры": "FLT",
                "Двигатель": "ENG",
                "Подвеска": "SUS",
                "Электрика": "ELE",
                "Кузовные детали": "BDY",
            }[category]
            counters[prefix] = counters.get(prefix, 0) + 1
            sku = f"{prefix}-{counters[prefix]:03d}"

            # Цена: небольшой разброс от базовой, в пределах 300..25000.
            # У дорогих позиций разброс вверх — иначе каталог не дотягивает
            # до верхней границы (турбина, стартер, генератор).
            if base_price >= 9000:
                price = int(base_price * rng.uniform(1.05, 1.32))
            else:
                price = int(base_price * rng.uniform(0.85, 1.2))
            price = max(300, min(25000, price // 10 * 10))

            # Скидка примерно у трети товаров.
            old_price = None
            discount = 0
            if rng.random() < 0.34:
                discount = rng.choice([5, 7, 10, 12, 14, 15, 18, 20])
                old_price = int(price / (1 - discount / 100) // 10 * 10)

            # Наличие: ~62% в наличии, ~26% под заказ, ~12% нет в наличии.
            roll = rng.random()
            if roll < 0.62:
                in_stock, is_on_order = True, False
            elif roll < 0.88:
                in_stock, is_on_order = False, True
            else:
                in_stock, is_on_order = False, False

            products.append({
                "sku": sku,
                "name": f"{name} {variant}" if variant else name,
                "brand": brand,
                "category": category,
                "price": price,
                "old_price": old_price,
                "discount_percent": discount,
                "in_stock": in_stock,
                "is_on_order": is_on_order,
                "order_days": rng.randint(2, 14) if is_on_order else 3,
            })
    return products


def build_compatibility(
    rng: random.Random, category: str
) -> list[tuple[str, str, int, int]]:
    """25 автомобилей, к которым подходит деталь."""
    pool: list[tuple[str, str]] = []
    for make, model in POPULAR_MODELS:
        # Популярные модели встречаются чаще — так список выглядит
        # правдоподобно: одна деталь универсальна, другая под 2-3 модели.
        weight = 3 if category in UNIVERSAL_CATEGORIES else 2
        pool.extend([(make, model)] * weight)

    # Остальные марки справочника — по одной модели от марки.
    for make in cars.CAR_MAKES:
        models = cars.CAR_CATALOG.get(make, [])
        if models:
            pool.append((make, models[0]))

    rng.shuffle(pool)

    chosen: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for item in pool:
        if item in seen:
            continue
        seen.add(item)
        chosen.append(item)
        if len(chosen) >= COMPATIBILITY_PER_PRODUCT:
            break

    result: list[tuple[str, str, int, int]] = []
    for make, model in chosen:
        year_from = rng.randint(2005, 2016)
        year_to = min(2026, year_from + rng.randint(3, 9))
        result.append((make, model, year_from, year_to))
    return result


async def main() -> int:
    rng = random.Random(SEED)
    products = build_products(rng)
    compat_map = {
        str(item["sku"]): build_compatibility(rng, str(item["category"]))
        for item in products
    }

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            # Прячем всё, чего нет в текущем наборе: товары из прежних
            # прогонов со старыми категориями и «сироты» с прежними
            # артикулами. История заказов при этом сохраняется —
            # товар скрыт с витрины, но не удалён.
            our_skus = [str(item["sku"]) for item in products]
            await conn.execute(
                """
                UPDATE products SET is_active = FALSE, updated_at = now()
                WHERE is_active AND NOT (sku = ANY($1::text[]))
                """,
                [our_skus],
            )

            # Пачкой upsert всех товаров — один round-trip вместо 72.
            await conn.executemany(
                """
                INSERT INTO products
                    (sku, name, brand, category, price, old_price,
                     discount_percent, in_stock, is_active, is_on_order,
                     order_days, description)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,TRUE,$9,$10,$11)
                ON CONFLICT (sku) DO UPDATE SET
                    name = EXCLUDED.name,
                    brand = EXCLUDED.brand,
                    category = EXCLUDED.category,
                    price = EXCLUDED.price,
                    old_price = EXCLUDED.old_price,
                    discount_percent = EXCLUDED.discount_percent,
                    in_stock = EXCLUDED.in_stock,
                    is_active = TRUE,
                    is_on_order = EXCLUDED.is_on_order,
                    order_days = EXCLUDED.order_days,
                    updated_at = now()
                """,
                [
                    (
                        str(item["sku"]),
                        str(item["name"]),
                        str(item["brand"]),
                        str(item["category"]),
                        int(item["price"]),
                        item["old_price"],
                        int(item["discount_percent"]),
                        bool(item["in_stock"]),
                        bool(item["is_on_order"]),
                        int(item["order_days"]),
                        f"Артикул {item['sku']}. "
                        f"Подходит на {COMPATIBILITY_PER_PRODUCT} автомобилей.",
                    )
                    for item in products
                ],
            )
            id_rows = await conn.fetch(
                "SELECT id, sku FROM products WHERE sku = ANY($1::text[])",
                [str(item["sku"]) for item in products],
            )
            id_by_sku = {row["sku"]: row["id"] for row in id_rows}

            # Совместимость: чистим по всем нашим SKU и вставляем одним
            # executemany — по сети до Neon поштучные запросы недопустимо
            # медленные.
            await conn.execute(
                """
                DELETE FROM product_compatibility
                WHERE product_id IN (
                    SELECT id FROM products WHERE sku = ANY($1::text[])
                )
                """,
                our_skus,
            )
            compat_rows = [
                (
                    id_by_sku[str(item["sku"])],
                    make,
                    model,
                    year_from,
                    year_to,
                )
                for item in products
                for make, model, year_from, year_to in compat_map[str(item["sku"])]
            ]
            await conn.executemany(
                """
                INSERT INTO product_compatibility
                    (product_id, make, model, year_from, year_to)
                VALUES ($1,$2,$3,$4,$5)
                """,
                compat_rows,
            )

        # Совместимость скрытых товаров больше не нужна.
        await conn.execute(
            """
            DELETE FROM product_compatibility
            WHERE product_id IN (SELECT id FROM products WHERE NOT is_active)
            """
        )

        total = await conn.fetchval("SELECT count(*) FROM products")
        active = await conn.fetchval(
            "SELECT count(*) FROM products WHERE is_active"
        )
        visible = await conn.fetchval(
            """
            SELECT count(*) FROM products
            WHERE is_active AND (in_stock OR is_on_order)
            """
        )
        compat = await conn.fetchval("SELECT count(*) FROM product_compatibility")
        per_category = await conn.fetch(
            """
            SELECT category, count(*) AS n FROM products
            WHERE is_active GROUP BY category ORDER BY category
            """
        )
        prices = await conn.fetchrow(
            "SELECT min(price) AS lo, max(price) AS hi FROM products WHERE is_active"
        )
        stock = await conn.fetchrow(
            """
            SELECT count(*) FILTER (WHERE in_stock) AS in_stock,
                   count(*) FILTER (WHERE is_on_order AND NOT in_stock) AS on_order,
                   count(*) FILTER (WHERE NOT in_stock AND NOT is_on_order) AS missing
            FROM products WHERE is_active
            """
        )

    await db.close_pool()

    print(f"Товаров всего в базе: {total} (активных: {active}, видно на витрине: {visible})")
    print(f"Записей совместимости: {compat} "
          f"(по {COMPATIBILITY_PER_PRODUCT} на товар)")
    print(f"Цены: от {prices['lo']} до {prices['hi']} ₽")
    print("Наличие: в наличии {in_stock}, под заказ {on_order}, нет в наличии {missing}".format(
        **dict(stock)
    ))
    print("Категории: " + ", ".join(
        f"{r['category']} ({r['n']})" for r in per_category
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
