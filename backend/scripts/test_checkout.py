"""Проверка новой логики оформления заказа.

Что проверяем:
  * подсказки по маркам и моделям (/api/cars/*);
  * телефон: обязателен и должен быть настоящим (не 111111111);
  * доставка недоступна — только самовывоз;
  * фильтры в кабинете владельца (статус, период, поиск, приоритет);
  * марка сохраняется в каноническом виде.

Запуск:  python backend/scripts/test_checkout.py
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

    print("\n[1] Подсказки по маркам")
    status, body = call("/api/cars/makes?q=K")
    makes = body.get("makes", []) if isinstance(body, dict) else []
    check("марки по префиксу K", status == 200 and "KIA" in makes, str(body))
    status, body = call("/api/cars/makes?q=%D0%BA%D0%B8")
    makes_ru = body.get("makes", []) if isinstance(body, dict) else []
    check(
        "русский синоним «ки» находит KIA",
        status == 200 and "KIA" in makes_ru,
        str(body),
    )
    status, body = call("/api/cars/makes?q=%D0%B0%D0%B2%D1%82%D0%BE")
    makes_ru2 = body.get("makes", []) if isinstance(body, dict) else []
    check(
        "русский синоним «авто» находит LADA",
        status == 200 and "LADA" in makes_ru2,
        str(body),
    )

    print("\n[2] Подсказки по моделям")
    status, body = call("/api/cars/models?make=KIA&q=ri")
    models = body.get("models", []) if isinstance(body, dict) else []
    check("модели KIA по префиксу ri", status == 200 and "Rio" in models, str(body))
    status, body = call("/api/cars/models?make=%D0%BA%D0%B8%D0%B0&q=")
    models_ru = body.get("models", []) if isinstance(body, dict) else []
    check(
        "русская марка «киа» резолвится в KIA",
        status == 200 and body.get("make") == "KIA" and models_ru,
        str(body),
    )

    print("\n[3] Режим работы магазина")
    status, body = call("/api/store")
    check(
        "магазин 8:00–20:00, только самовывоз",
        status == 200
        and body["open_hour"] == 8
        and body["close_hour"] == 20
        and body["pickup_only"] is True,
        str(body),
    )
    check(
        "приоритетные часы 20:00–08:00",
        body["night_start_hour"] == 20 and body["night_end_hour"] == 8,
        str(body),
    )

    print("\n[4] Валидация телефона")
    status, products = call("/api/products")
    product_id = products[0]["id"]
    base_order = {
        "items": [{"product_id": product_id, "qty": 1}],
        "pickup_method": "pickup",
        "customer_name": "Проверка Телефона",
    }

    status, body = call("/api/orders", {**base_order, "phone": "111111111"})
    check("заглушка 111111111 отклонена (422)", status == 422, f"статус {status}")
    status, body = call("/api/orders", {**base_order, "phone": "1234567890"})
    check("placeholder 1234567890 отклонён (422)", status == 422, f"статус {status}")
    status, body = call("/api/orders", {**base_order, "phone": "12345"})
    check("короткий номер отклонён (422)", status == 422, f"статус {status}")
    status, body = call("/api/orders", base_order)
    check("заказ без телефона отклонён (422)", status == 422, f"статус {status}")

    print("\n[5] Только самовывоз")
    status, body = call(
        "/api/orders",
        {
            **base_order,
            "phone": "+7 900 123-45-67",
            "pickup_method": "delivery",
            "address": "ул. Ленина, 1",
        },
    )
    check("доставка отклонена (422)", status == 422, f"статус {status}: {body}")

    print("\n[6] Заказ с корректными данными")
    status, order = call(
        "/api/orders",
        {
            **base_order,
            "phone": "+7 900 123-45-67",
            "car_make": "киа",
            "car_model": "Rio",
            "telegram": "@testclient",
            "comment": "Забрать после 18:00",
        },
    )
    check("заказ создан (201)", status == 201, f"статус {status}: {order}")
    if status != 201:
        print("\nИТОГ: ПРОВАЛ")
        return 1
    order_number = order["order_number"]
    check("марка сохранена канонически (KIA)", order["car_make"] == "KIA", str(order["car_make"]))
    check("телефон нормализован", order["phone"] == "+79001234567", str(order["phone"]))
    check("telegram без @", order["telegram"] == "testclient", str(order["telegram"]))
    check("способ получения — самовывоз", order["pickup_method"] == "pickup", str(order))
    check("комментарий сохранён", order["comment"] == "Забрать после 18:00", str(order))

    print("\n[7] Фильтры в кабинете владельца")
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

    status, all_orders = call("/api/admin/orders?limit=500", token=owner_token)
    check("список заказов доступен", status == 200, str(status))

    status, by_status = call(
        "/api/admin/orders?order_status=new&limit=500", token=owner_token
    )
    check(
        "фильтр по статусу new",
        status == 200 and all(o["status"] == "new" for o in by_status),
        str(status),
    )
    check(
        "новый заказ попал в выборку",
        any(o["order_number"] == order_number for o in by_status),
        "заказ не найден",
    )

    status, by_query = call(
        "/api/admin/orders?query=%D0%9F%D1%80%D0%BE%D0%B2%D0%B5%D1%80%D0%BA%D0%B0&limit=500",
        token=owner_token,
    )
    check(
        "поиск по имени клиента",
        status == 200 and any(o["order_number"] == order_number for o in by_query),
        f"статус {status}, найдено {len(by_query) if isinstance(by_query, list) else '?'}",
    )

    status, by_number = call(
        f"/api/admin/orders?query={order_number}&limit=500", token=owner_token
    )
    check(
        "поиск по номеру заказа",
        status == 200
        and isinstance(by_number, list)
        and len(by_number) == 1
        and by_number[0]["order_number"] == order_number,
        f"статус {status}, найдено {len(by_number) if isinstance(by_number, list) else '?'}",
    )

    today = time.strftime("%Y-%m-%d")
    status, by_date = call(
        f"/api/admin/orders?date_from={today}&date_to={today}&limit=500",
        token=owner_token,
    )
    check(
        "фильтр по периоду (сегодня)",
        status == 200 and any(o["order_number"] == order_number for o in by_date),
        f"статус {status}",
    )

    status, future = call(
        "/api/admin/orders?date_from=2099-01-01&date_to=2099-01-02&limit=500",
        token=owner_token,
    )
    check(
        "период без заказов даёт пустой список",
        status == 200 and len(future) == 0,
        f"статус {status}, записей {len(future) if isinstance(future, list) else '?'}",
    )

    status, night = call("/api/admin/orders?night_only=true&limit=500", token=owner_token)
    check(
        "фильтр только приоритетных",
        status == 200 and all(o["is_night_order"] for o in night),
        f"статус {status}",
    )

    status, sorted_old = call(
        "/api/admin/orders?sort=oldest&limit=500", token=owner_token
    )
    status, sorted_new = call(
        "/api/admin/orders?sort=newest&limit=500", token=owner_token
    )
    check(
        "сортировка работает",
        status == 200
        and isinstance(sorted_old, list)
        and isinstance(sorted_new, list)
        and (not sorted_old or not sorted_new or sorted_old[0]["id"] == sorted_new[-1]["id"]),
        "порядок не изменился",
    )

    print("\n[8] Смена статуса")
    target = next(
        (o for o in by_status if o["order_number"] == order_number), None
    )
    status, updated = call(
        f"/api/admin/orders/{target['id']}",
        {"status": "accepted"},
        token=owner_token,
        method="PATCH",
    )
    check(
        "статус изменён на accepted",
        status == 200 and updated["status"] == "accepted",
        f"статус {status}",
    )
    check(
        "событие записано в таймлайн",
        any(e["status"] == "accepted" for e in updated["events"]),
        str(updated["events"]),
    )

    print("\n[9] Кабинет клиента")
    email = f"checkout_{stamp}@test.ru"
    status, reg = call(
        "/api/auth/register",
        {"email": email, "password": "testpass123", "full_name": "Клиент Теста"},
    )
    check("регистрация клиента", status == 201, str(status))
    token = reg["token"] if status == 201 else None
    if token:
        status, my = call("/api/cabinet/orders", token=token)
        check(
            "клиент не видит чужие заказы",
            status == 200 and isinstance(my, list) and not my,
            str(status),
        )
        call("/api/auth/logout", None, token=token, method="POST")

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
