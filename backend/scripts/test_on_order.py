"""Проверка системы «под заказ».

Что проверяем:
  * деталь под заказ видна на витрине и помечена;
  * фильтры витрины (в наличии / под заказ);
  * деталь под заказ можно заказать, срок сохраняется в позиции заказа;
  * деталь «нет в наличии и не под заказ» заказать нельзя;
  * админ может поставить деталь под заказ и снять этот статус;
  * уведомление менеджеру помечает позиции под заказ.

Запуск:  python backend/scripts/test_on_order.py
"""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR.parent))

BASE = "http://127.0.0.1:8000"

PASSED: list[str] = []
FAILED: list[str] = []


def call(
    path: str,
    payload: dict | None = None,
    token: str | None = None,
    method: str | None = None,
) -> tuple[int, dict | list | str]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        headers=headers,
        method=method or ("POST" if data else "GET"),
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = response.read().decode("utf-8")
            if not body:
                return response.status, {}
            try:
                return response.status, json.loads(body)
            except json.JSONDecodeError:
                return response.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, body


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"  OK   {name}")
    else:
        FAILED.append(f"{name} — {detail}")
        print(f"  FAIL {name}: {detail}")


def main() -> int:
    import time

    stamp = int(time.time())

    print("\n[1] Витрина: детали под заказ показываются")
    status, products = call("/api/products")
    check("каталог доступен", status == 200, str(status))
    on_order = [p for p in products if p["is_on_order"]]
    in_stock = [p for p in products if p["in_stock"]]
    check(
        "есть детали под заказ на витрине",
        len(on_order) >= 1,
        f"под заказ: {len(on_order)}",
    )
    check(
        "у детали под заказ задан срок",
        all(p["order_days"] > 0 for p in on_order),
        str([(p["sku"], p["order_days"]) for p in on_order]),
    )
    check(
        "деталь под заказ не в наличии",
        all(not p["in_stock"] for p in on_order),
        str([(p["sku"], p["in_stock"]) for p in on_order]),
    )
    check(
        "товары без наличия и без «под заказ» скрыты",
        all(p["in_stock"] or p["is_on_order"] for p in products),
        "на витрине есть недоступные позиции",
    )
    check("в наличии тоже есть", len(in_stock) >= 5, f"в наличии: {len(in_stock)}")

    print("\n[2] Фильтры витрины")
    status, only_order = call("/api/products?on_order_only=true")
    check(
        "фильтр «только под заказ»",
        status == 200
        and isinstance(only_order, list)
        and only_order
        and all(p["is_on_order"] for p in only_order),
        f"статус {status}",
    )
    status, only_stock = call("/api/products?in_stock_only=true")
    check(
        "фильтр «только в наличии»",
        status == 200
        and isinstance(only_stock, list)
        and only_stock
        and all(p["in_stock"] for p in only_stock),
        f"статус {status}",
    )

    print("\n[3] Вход владельца")
    status, owner_body = call(
        "/api/auth/login",
        {"email": "owner@autodom.ru", "password": "OWNER_PASSWORD_PLACEHOLDER"},
    )
    if status != 200:
        print(f"  FAIL вход владельца: {owner_body}")
        FAILED.append("вход владельца")
        print("\nИТОГ: ПРОВАЛ")
        return 1
    owner_token = owner_body["token"]

    print("\n[4] Админ: деталь под заказ")
    sku = f"TEST-ONORDER-{stamp}"
    status, created = call(
        "/api/admin/products",
        {
            "sku": sku,
            "name": "Деталь под заказ (тест)",
            "brand": "TestBrand",
            "category": "Тест",
            "price": 2500,
            "in_stock": False,
            "is_on_order": True,
            "order_days": 9,
            "description": "Проверка системы под заказ",
        },
        token=owner_token,
    )
    check("деталь создана как под заказ (201)", status == 201, f"статус {status}: {created}")
    if status != 201:
        print("\nИТОГ: ПРОВАЛ")
        return 1
    product_id = created["id"]
    check("статус под заказ сохранён", created["is_on_order"] is True, str(created))
    check("срок поставки сохранён", created["order_days"] == 9, str(created["order_days"]))
    check("в наличии снят", created["in_stock"] is False, str(created))

    status, catalog = call("/api/products")
    fresh = next((p for p in catalog if p["sku"] == sku), None)
    check("деталь видна на витрине", fresh is not None, "не найдена в каталоге")
    check(
        "деталь помечена под заказ в каталоге",
        fresh is not None and fresh["is_on_order"] and fresh["order_days"] == 9,
        str(fresh),
    )

    print("\n[5] Заказ детали под заказ")
    status, order = call(
        "/api/orders",
        {
            "items": [{"product_id": product_id, "qty": 1}],
            "pickup_method": "pickup",
            "customer_name": "Тест Под Заказ",
            "phone": "+7 900 777-88-99",
        },
    )
    check("заказ принят (201)", status == 201, f"статус {status}: {order}")
    if status != 201:
        print("\nИТОГ: ПРОВАЛ")
        return 1
    order_number = order["order_number"]
    check("заказ помечен как содержащий под заказ", order["has_on_order"] is True, str(order))
    check(
        "в позиции заказа сохранён срок",
        order["items"][0]["is_on_order"] is True
        and order["items"][0]["order_days"] == 9,
        str(order["items"]),
    )
    check(
        "уведомление Telegram ушло",
        order["telegram_sent"] is True,
        f"delivery={order.get('telegram_delivery')}",
    )

    print("\n[6] Деталь без наличия и без «под заказ» заказать нельзя")
    sku2 = f"TEST-NOSTOCK-{stamp}"
    status, created2 = call(
        "/api/admin/products",
        {
            "sku": sku2,
            "name": "Недоступная деталь (тест)",
            "price": 500,
            "in_stock": False,
            "is_on_order": False,
        },
        token=owner_token,
    )
    check("деталь создана (201)", status == 201, f"статус {status}")
    status, hidden = call("/api/products")
    check(
        "недоступная деталь скрыта с витрины",
        all(p["sku"] != sku2 for p in hidden),
        "деталь видна на витрине",
    )
    status, rejected = call(
        "/api/orders",
        {
            "items": [{"product_id": created2["id"], "qty": 1}],
            "pickup_method": "pickup",
            "customer_name": "Тест Под Заказ",
            "phone": "+7 900 777-88-99",
        },
    )
    check("заказ недоступной детали отклонён (422)", status == 422, f"статус {status}")

    print("\n[7] Админ: снятие статуса «под заказ»")
    status, patched = call(
        f"/api/admin/products/{product_id}",
        {
            "sku": sku,
            "name": "Деталь под заказ (тест)",
            "brand": "TestBrand",
            "category": "Тест",
            "price": 2500,
            "in_stock": True,
            "is_on_order": False,
            "order_days": 0,
            "description": "Проверка системы под заказ",
        },
        token=owner_token,
        method="PATCH",
    )
    check(
        "деталь переведена в наличие",
        status == 200 and patched["in_stock"] is True and patched["is_on_order"] is False,
        f"статус {status}: {patched}",
    )

    print("\n[8] Уборка")
    status, _ = call(
        f"/api/admin/products/{product_id}", None, token=owner_token, method="DELETE"
    )
    check("деталь скрыта", status == 200, f"статус {status}")
    status, _ = call(
        f"/api/admin/products/{created2['id']}", None, token=owner_token, method="DELETE"
    )
    check("вторая деталь скрыта", status == 200, f"статус {status}")
    status, catalog = call("/api/products")
    check(
        "тестовые детали убраны с витрины",
        all(p["sku"] not in (sku, sku2) for p in catalog),
        "тестовые детали остались",
    )

    print("\n[9] История заказа не едет при смене каталога")
    status, saved = call(
        f"/api/orders/{order_number}?phone=%2B79007778899"
    )
    check("заказ читается по номеру и телефону", status == 200, f"статус {status}")
    check(
        "снимок «под заказ» сохранился в истории",
        status == 200 and saved["items"][0]["is_on_order"] is True,
        str(saved.get("items")),
    )

    print(f"\n{'=' * 60}")
    print(f"Пройдено: {len(PASSED)}   Провалено: {len(FAILED)}")
    if FAILED:
        for item in FAILED:
            print(f"  ✗ {item}")
        return 1
    print("ИТОГ: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
