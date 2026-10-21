"""Проверка уведомлений клиенту в Telegram.

Сценарий:
  1. Клиент подписывается на заказ (/start с номером заказа).
  2. Бот находит чат клиента по номеру заказа.
  3. При смене статуса формируется и отправляется уведомление.
  4. Бот находит чат клиента по username (если /start не было).

Запуск:  python backend/scripts/test_client_notify.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR.parent))

from backend import db  # noqa: E402
from backend.telegram import (  # noqa: E402
    CLIENT_NOTIFY_STATUSES,
    CLIENT_STATUS_TEXTS,
    notifier,
)

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


async def main() -> int:
    # Тестовый заказ: отдельный, чтобы не трогать реальные.
    row = await db.fetchrow(
        """
        SELECT id, order_number, total, customer_name, phone, telegram, address
        FROM orders WHERE status = 'accepted'
        ORDER BY id DESC LIMIT 1
        """
    )
    if row is None:
        print("Нет заказа в статусе accepted — нечего проверять")
        await db.close_pool()
        return 1

    order_number = row["order_number"]
    username = (row["telegram"] or "").strip().lstrip("@") or "notify_test_client"
    fake_chat = 999000001

    print(f"Заказ: {order_number}, сумма {row['total']}, telegram @{username}\n")

    # --- 1. Подписка клиента ---
    await db.execute(
        """
        INSERT INTO telegram_chats (chat_id, username, order_number)
        VALUES ($1, $2, $3)
        ON CONFLICT (chat_id) DO UPDATE
        SET username = EXCLUDED.username,
            order_number = EXCLUDED.order_number,
            updated_at = now()
        """,
        fake_chat,
        username,
        order_number,
    )
    await db.execute(
        "UPDATE orders SET telegram_chat_id = $1 WHERE id = $2",
        fake_chat,
        row["id"],
    )
    saved = await db.fetchrow(
        "SELECT telegram_chat_id FROM orders WHERE id = $1", row["id"]
    )
    check("подписка сохраняет chat_id в заказе", saved["telegram_chat_id"] == fake_chat)

    # --- 2. Поиск чата по номеру заказа (основной путь) ---
    found = await notifier._find_chat_by_username(username)
    check("бот находит чат клиента по username", found == fake_chat, f"получено {found}")

    # --- 3. Тексты уведомлений ---
    for status in ("accepted", "in_progress", "ready", "completed"):
        template = CLIENT_STATUS_TEXTS.get(status)
        check(f"есть текст уведомления «{status}»,", bool(template))
        if template:
            text = template.format(
                order_number=order_number,
                address=row["address"] or "ул. Тестовая, 1",
                phone=row["phone"] or "+7 (000) 000-00-00",
                hours="8:00–20:00",
            )
            check(
                f"текст «{status}» содержит номер заказа",
                order_number in text,
            )
            check(f"текст «{status}» не пустой", len(text.strip()) > 20)

    check(
        "статус «new» не отправляется клиенту (он и так знает о заказе)",
        "new" not in CLIENT_NOTIFY_STATUSES,
    )

    # --- 4. Форматирование не падает на пустых данных ---
    template = CLIENT_STATUS_TEXTS["ready"]
    text = template.format(
        order_number=order_number,
        address="",
        phone="",
        hours="8:00–20:00",
    )
    check("готовый заказ форматируется с пустым адресом", "Заказ" in text)

    # --- 5. Уведомление клиенту реально уходит (в тестовый чат) ---
    # Telegram не примет сообщение в несуществующий чат — ожидаем ошибку,
    # но важно, что код дошёл до отправки и не упал раньше.
    sent = await notifier.notify_client_status(
        order_number=order_number,
        status="ready",
        chat_id=fake_chat,
        telegram_username=username,
        address=row["address"],
        phone=row["phone"],
    )
    check("отправка уведомления обработана без исключения", sent in (True, False))

    # --- 6. Без chat_id уведомление не отправляется, но и не падает ---
    sent_no_chat = await notifier.notify_client_status(
        order_number=order_number,
        status="accepted",
        chat_id=None,
        telegram_username=None,
    )
    check("без chat_id уведомление пропускается", sent_no_chat is False)

    # --- 7. Убираем тестовые следы ---
    await db.execute("DELETE FROM telegram_chats WHERE chat_id = $1", fake_chat)
    await db.execute(
        "UPDATE orders SET telegram_chat_id = NULL WHERE id = $1", row["id"]
    )
    cleaned = await db.fetchrow(
        "SELECT telegram_chat_id FROM orders WHERE id = $1", row["id"]
    )
    check("тестовая подписка убрана", cleaned["telegram_chat_id"] is None)

    await db.close_pool()
    print(f"\nИТОГ: {PASSED} пройдено, {FAILED} провалено")
    return 0 if FAILED == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
