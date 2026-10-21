"""Проверка реальной доставки уведомления клиенту.

Отправляет сообщение в чат владельца (TELEGRAM_CHAT_ID) через тот же код,
который уходит клиенту. Так проверяется, что Telegram реально принимает
сообщение с текстом и разметкой, а не только что код не падает.

Запуск:  python backend/scripts/test_delivery.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR.parent))

from backend import db, settings  # noqa: E402
from backend.telegram import notifier  # noqa: E402


async def main() -> int:
    row = await db.fetchrow(
        """
        SELECT order_number, customer_name, address, phone
        FROM orders WHERE order_number = 'A-261021-0076'
        """
    )
    if row is None:
        print("Нет заказа A-261021-0076")
        await db.close_pool()
        return 1

    print(f"Отправляем тестовое уведомление в чат {settings.TELEGRAM_CHAT_ID}...")
    print(f"Заказ: {row['order_number']}\n")

    ok = await notifier.notify_client_status(
        order_number=row["order_number"],
        status="ready",
        chat_id=int(settings.TELEGRAM_CHAT_ID),
        telegram_username=None,
        address=row["address"],
        phone=row["phone"],
    )
    print(f"\nРезультат доставки: {ok}")
    if ok:
        print("OK   Telegram принял сообщение с текстом уведомления")
    else:
        print("FAIL сообщение не доставлено")

    await db.close_pool()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
