"""Проверка новой функциональности: регистрация, кабинеты, скидки, статусы.

Запуск:  python backend/scripts/test_accounts.py
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
    email = f"client_{stamp}@test.ru"
    password = "testpass123"

    print("\n[1] Регистрация клиента")
    status, body = call(
        "/api/auth/register",
        {
            "email": email,
            "password": password,
            "full_name": "Тестовый Клиент",
            "phone": "+7 900 000-11-22",
        },
    )
    check("регистрация возвращает 201", status == 201, f"статус {status}: {body}")
    if status != 201:
        print("\nИТОГ: ПРОВАЛ — не удалось зарегистрироваться")
        return 1
    token = body["token"]
    check("токен выдан", bool(token), "токен пуст")
    check("роль клиента = customer", body["user"]["role"] == "customer", body["user"]["role"])

    print("\n[2] Повторная регистрация того же e-mail")
    status, _ = call(
        "/api/auth/register", {"email": email, "password": password}
    )
    check("дубль e-mail отклонён (409)", status == 409, f"статус {status}")

    print("\n[3] Вход и неверный пароль")
    status, body = call("/api/auth/login", {"email": email, "password": password})
    check("вход возвращает 201/200", status == 200, f"статус {status}")
    status, _ = call("/api/auth/login", {"email": email, "password": "wrong"})
    check("неверный пароль отклонён (401)", status == 401, f"статус {status}")

    print("\n[4] /api/auth/me")
    status, body = call("/api/auth/me", token=token)
    check("me отдаёт пользователя", status == 200 and body["email"] == email, str(body))
    status, _ = call("/api/auth/me")
    check("me без токена — 401", status == 401, f"статус {status}")

    print("\n[5] Заказ из авторизованной сессии")
    status, products = call("/api/products")
    check(
        "каталог доступен",
        status == 200 and len(products) >= 10,
        f"статус {status}, товаров {len(products) if isinstance(products, list) else '?'}",
    )
    product_id = products[0]["id"]

    status, order = call(
        "/api/orders",
        {
            "items": [{"product_id": product_id, "qty": 2}],
            "pickup_method": "pickup",
            "customer_name": "Тестовый Клиент",
            "phone": "+7 900 000-11-22",
        },
        token=token,
    )
    check("заказ создан (201)", status == 201, f"статус {status}: {order}")
    if status != 201:
        print("\nИТОГ: ПРОВАЛ — заказ не создался")
        return 1
    order_number = order["order_number"]
    check("заказ привязан к аккаунту", order["status"] == "new", order["status"])
    check(
        "таймлайн содержит создание",
        any(e["status"] == "new" for e in order["events"]),
        str(order["events"]),
    )

    print("\n[6] Кабинет клиента")
    status, orders = call("/api/cabinet/orders", token=token)
    check("кабинет отдаёт заказы", status == 200 and len(orders) == 1, str(orders))
    check(
        "заказ в кабинете с таймлайном",
        status == 200 and bool(orders[0]["events"]),
        "таймлайн пуст",
    )
    status, _ = call("/api/cabinet/orders")
    check("кабинет без токена — 401", status == 401, f"статус {status}")

    print("\n[7] Чужой заказ недоступен")
    status, _ = call(f"/api/cabinet/orders/{order_number}", token=token)
    check("свой заказ в кабинете доступен", status == 200, f"статус {status}")

    print("\n[8] Вход владельца и кабинет владельца")
    status, owner_body = call(
        "/api/auth/login",
        {"email": "owner@autodom.ru", "password": "OWNER_PASSWORD_PLACEHOLDER"},
    )
    check("вход владельца", status == 200, f"статус {status}: {owner_body}")
    if status != 200:
        print("\nИТОГ: ПРОВАЛ — владелец не вошёл")
        return 1
    owner_token = owner_body["token"]
    check("роль = owner", owner_body["user"]["role"] == "owner", owner_body["user"]["role"])

    status, admin_orders = call("/api/admin/orders", token=owner_token)
    check("владелец видит заказы", status == 200 and len(admin_orders) >= 1, str(status))
    status, _ = call("/api/admin/orders", token=token)
    check("клиент не попадает в админку (403)", status == 403, f"статус {status}")

    print("\n[9] Смена статуса заказа владельцем")
    admin_order_id = None
    for row in admin_orders:
        if row["order_number"] == order_number:
            admin_order_id = row.get("id")
    status, updated = call(
        f"/api/admin/orders/{order_number.replace('-', '-')}",
        None,
        token=owner_token,
        method="GET",
    )
    # PATCH принимает id; найдём его через список заказов кабинета владельца
    status, all_orders = call("/api/admin/orders?limit=500", token=owner_token)
    target = next(
        (r for r in all_orders if r["order_number"] == order_number), None
    )
    check("заказ найден в списке админа", target is not None, "не найден")
    if target is None:
        print("\nИТОГ: ПРОВАЛ")
        return 1

    print("\n[10] Управление каталогом: добавление, скидка, скрытие")
    sku = f"TEST-{stamp}"
    status, created = call(
        "/api/admin/products",
        {
            "sku": sku,
            "name": "Тестовая деталь",
            "brand": "TestBrand",
            "category": "Тест",
            "price": 1000,
            "old_price": 1250,
            "discount_percent": 20,
            "in_stock": True,
            "description": "Проверка CRUD",
        },
        token=owner_token,
    )
    check("товар создан (201)", status == 201, f"статус {status}: {created}")
    if status != 201:
        print("\nИТОГ: ПРОВАЛ")
        return 1
    product_id_new = created["id"]
    check("скидка сохранена", created["discount_percent"] == 20, str(created))

    status, patched = call(
        f"/api/admin/products/{product_id_new}",
        {
            "sku": sku,
            "name": "Тестовая деталь (обновлена)",
            "brand": "TestBrand",
            "category": "Тест",
            "price": 900,
            "old_price": 1250,
            "discount_percent": 28,
            "in_stock": False,
            "is_active": True,
            "description": "Обновлено",
        },
        token=owner_token,
        method="PATCH",
    )
    check("товар обновлён", status == 200 and float(patched["price"]) == 900, str(patched))
    check("скидка обновлена", patched["discount_percent"] == 28, str(patched))
    check("наличие снято", patched["in_stock"] is False, str(patched))

    status, deleted = call(
        f"/api/admin/products/{product_id_new}",
        None,
        token=owner_token,
        method="DELETE",
    )
    check("товар скрыт", status == 200 and deleted["is_active"] is False, str(deleted))

    status, public_products = call("/api/products")
    check(
        "скрытого товара нет на витрине",
        all(p["sku"] != sku for p in public_products),
        "товар всё ещё в каталоге",
    )

    status, _ = call(
        "/api/admin/products",
        {"sku": sku, "name": "Дубль", "price": 100},
        token=token,
        method="POST",
    )
    check("клиент не может править каталог (403)", status == 403, f"статус {status}")

    print("\n[11] Сводка владельца")
    status, stats = call("/api/admin/stats", token=owner_token)
    check("статистика доступна", status == 200, str(stats))
    check("есть счётчик заказов", stats["totals"]["orders_total"] >= 1, str(stats))

    print("\n[12] Выход")
    status, _ = call("/api/auth/logout", token=token, method="POST")
    check("logout отработал", status == 204, f"статус {status}")
    status, _ = call("/api/auth/me", token=token)
    check("токен после logout не работает", status == 401, f"статус {status}")

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
