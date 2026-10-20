"""Smoke-тест API: каталог + оформление заказа (без Telegram-спам — 1 запрос)."""

from __future__ import annotations

import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8000"


def call(path: str, payload: dict | None = None) -> tuple[int, dict]:
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        f"{BASE}{path}", data=data, headers=headers, method="POST" if data else "GET"
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8")
        try:
            return exc.code, json.loads(body)
        except json.JSONDecodeError:
            return exc.code, {"raw": body}


def main() -> int:
    status, health = call("/api/health")
    print("health:", status, health)

    status, products = call("/api/products")
    print("products:", status, len(products) if isinstance(products, list) else products)
    if not isinstance(products, list) or not products:
        return 1

    first = products[0]
    payload = {
        "items": [{"product_id": first["id"], "qty": 2}],
        "car_make": "Kia",
        "car_model": "Rio",
        "vin": "Z94CB41AAER123456",
        "pickup_method": "pickup",
        "customer_name": "Тест Тестов",
        "phone": "+7 900 111-22-33",
        "telegram": "@test_user",
        "comment": "Smoke-тест API",
    }
    status, order = call("/api/orders", payload)
    print("order:", status, json.dumps(order, ensure_ascii=False, indent=2))

    if status != 201:
        return 1

    status, stored = call(f"/api/orders/{order['order_number']}")
    print("stored:", status, json.dumps(stored, ensure_ascii=False))
    return 0 if status == 200 else 1


if __name__ == "__main__":
    sys.exit(main())
