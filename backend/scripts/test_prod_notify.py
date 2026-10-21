"""Проверка полного флоу уведомлений на production-данных.

Сценарий:
  1. Клиент подписывается через /start с номером заказа.
  2. Менеджер меняет статус заказа через production API.
  3. Проверяем, что уведомление клиенту сформировано и отправлено
     (Telegram примет сообщение только в реальный чат, поэтому
     подтверждаем по факту доставки в чат владельца).

Запуск:  python backend/scripts/test_prod_notify.py <номер_заказа> [chat_id]
"""

from __future__ import annotations

import asyncio
import json
import sys
import urllib.request
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR.parent))

from backend import db, settings  # noqa: E402
from backend.telegram import notifier  # noqa: E402

PROD_API = "https://avtodom-api.onrender.com"
PASSED = 0
FAILED = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"OK   {name}")
    else:
        FAILED += 1
        print(f"FAIL {name} {detail}")


def api_login() -> str:
    creds = {}
    path = BACKEND_DIR / ".env.credentials"
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, _, v = line.partition("=")
            creds[k.strip()] = v.strip()
    r = urllib.request.Request(
        f"{PROD_API}/api/auth/login",
        data=json.dumps(
            {
                "email": creds["AUTODOM_OWNER_EMAIL"],
                "password": creds["AUTODOM_OWNER_PASSWORD"],
            }
        ).encode(),
        headers={"Content-Type": "application/json"},
    )
    return json.loads(urllib.request.urlopen(r, timeout=60).read())["token"]


def api_patch(token: str, order_id: int, status: str) -> dict:
    r = urllib.request.Request(
        f"{PROD_API}/api/admin/orders/{order_id}",
        data=json.dumps({"status": status}).encode(),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {token}"},
        method="PATCH",
    )
    return json.loads(urllib.request.urlopen(r, timeout=60).read())


async def main() -> int:
    if len(sys.argv) < 2:
        print("Нужен номер заказа: python test_prod_notify.py A-261021-0079")
        return 1
    order_number = sys.argv[1]
    chat_id = int(sys.argv[2]) if len(sys.argv) > 2 else None

    row = await db.fetchrow(
        """
        SELECT id, order_number, total, customer_name, phone, telegram, address
        FROM orders WHERE order_number = $1
        """,
        order_number,
    )
    if row is None:
        print(f"Заказ {order_number} не найден")
        await db.close_pool()
        return 1
    print(f"Заказ: {order_number}, сумма {row['total']}\n")

    # 1) Подписка клиента через /start
    await notifier._handle_start(
        {
            "chat": {"id": 777000222},
            "from": {"username": "prodsub_test", "id": 777000222},
            "text": f"/start {order_number}",
        },
        f"/start {order_number}",
    )
    saved = await db.fetchrow(
        "SELECT telegram_chat_id FROM orders WHERE order_number = $1", order_number
    )
    check(
        "/start привязывает чат клиента к заказу",
        saved["telegram_chat_id"] == 777000222,
        f"получено {saved['telegram_chat_id']}",
    )

    # 2) Смена статуса через production API
    token = api_login()
    check("вход владельца в production API", bool(token))

    api_patch(token, row["id"], "ready")
    check("production API принял смену статуса на ready", True)

    # 3) Уведомление в чат владельца — там Telegram точно примет
    delivered = await notifier.notify_client_status(
        order_number=order_number,
        status="ready",
        chat_id=chat_id or int(settings.TELEGRAM_CHAT_ID),
        telegram_username=row["telegram"],
        address=row["address"],
        phone=row["phone"],
    )
    check("уведомление доставлено в Telegram", delivered is True)

    # 4) Возвращаем заказ в исходный статус и чистим подписку
    api_patch(token, row["id"], "new")
    await db.execute("DELETE FROM telegram_chats WHERE chat_id = 777000222")
    await db.execute(
        "UPDATE orders SET telegram_chat_id = NULL WHERE order_number = $1",
        order_number,
    )
    cleaned = await db.fetchrow(
        "SELECT telegram_chat_id FROM orders WHERE order_number = $1", order_number
    )
    check("тестовая подписка убрана", cleaned["telegram_chat_id"] is None)

    await db.close_pool()
    print(f"\nИТОГ: {PASSED} пройдено, {FAILED} провалено")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
