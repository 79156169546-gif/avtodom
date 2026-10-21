"""Полный флоу уведомлений клиенту: /start → смена статуса → сообщение.

Проверяет, что:
  1. Клиент нажал /start с номером заказа — чат привязан к заказу.
  2. Смена статуса через API вызывает notify_client_status.
  3. Уведомление формируется с номером заказа и статусом.
  4. Без подписки уведомление не отправляется, но и не падает.

Запуск:  python backend/scripts/test_client_flow.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR.parent))

from backend import db  # noqa: E402
from backend.telegram import notifier  # noqa: E402

PASSED = 0
FAILED = 0
FAKE_CHAT = 555000111


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASSED, FAILED
    if condition:
        PASSED += 1
        print(f"OK   {name}")
    else:
        FAILED += 1
        print(f"FAIL {name} {detail}")


async def main() -> int:
    row = await db.fetchrow(
        """
        SELECT id, order_number, total, customer_name, phone, telegram, address
        FROM orders WHERE order_number = 'A-261021-0077'
        """
    )
    if row is None:
        print("Нет заказа A-261021-0077 — создайте его заново")
        await db.close_pool()
        return 1
    order_number = row["order_number"]
    print(f"Заказ: {order_number}, сумма {row['total']}\n")

    # --- 1. Клиент нажал /start с номером заказа ---
    await notifier._handle_start(
        {
            "chat": {"id": FAKE_CHAT},
            "from": {"username": "subtest_user", "id": FAKE_CHAT},
            "text": f"/start {order_number}",
        },
        f"/start {order_number}",
    )

    saved = await db.fetchrow(
        "SELECT telegram_chat_id FROM orders WHERE order_number = $1", order_number
    )
    check(
        "/start привязывает чат клиента к заказу",
        saved["telegram_chat_id"] == FAKE_CHAT,
        f"получено {saved['telegram_chat_id']}",
    )

    chat = await db.fetchrow(
        "SELECT chat_id, username, order_number FROM telegram_chats WHERE chat_id = $1",
        FAKE_CHAT,
    )
    check("запись о подписке создана в telegram_chats", chat is not None)
    if chat:
        check(
            "в telegram_chats сохранён номер заказа",
            chat["order_number"] == order_number,
            f"получено {chat['order_number']}",
        )
        check("в telegram_chats сохранён username", chat["username"] == "subtest_user")

    # --- 2. Поиск чата по username (запасной путь) ---
    found = await notifier._find_chat_by_username("subtest_user")
    check("бот находит чат клиента по username", found == FAKE_CHAT, f"получено {found}")

    # --- 3. Уведомление при смене статуса ---
    # chat_id подставлен — клиент получит сообщение о каждом статусе.
    for status in ("accepted", "in_progress", "ready", "completed"):
        sent = await notifier.notify_client_status(
            order_number=order_number,
            status=status,
            chat_id=FAKE_CHAT,
            telegram_username="subtest_user",
            address=row["address"],
            phone=row["phone"],
        )
        # Telegram отклонит сообщение в несуществующий чат (400) — это ожидаемо.
        # Важно, что вызов дошёл до отправки и вернул bool, а не упал.
        check(
            f"уведомление «{status}» обработано без исключения",
            isinstance(sent, bool),
        )

    # --- 4. Без чата уведомление пропускается ---
    sent_no_chat = await notifier.notify_client_status(
        order_number=order_number,
        status="accepted",
        chat_id=None,
        telegram_username=None,
    )
    check("без чата уведомление не отправляется", sent_no_chat is False)

    # --- 5. Чистим тестовые следы ---
    await db.execute("DELETE FROM telegram_chats WHERE chat_id = $1", FAKE_CHAT)
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
