"""Проверка Telegram-канала: MCP-путь и резервный Bot API.

Запуск:  python backend/scripts/test_telegram.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR.parent))

from backend import settings  # noqa: E402
from backend.telegram import TelegramNotifier  # noqa: E402

ORDER_NUMBER = "TEST-TG-0001"

ITEMS = [
    ("Тормозные колодки, комплект", 1, 4890.0),
    ("Масляный фильтр", 2, 450.0),
]


async def main() -> int:
    settings.validate()
    notifier = TelegramNotifier()
    await notifier.start()

    sent, channel = await notifier.send_order_notification(
        order_number=ORDER_NUMBER,
        customer_name="Тест Telegram",
        phone="+7 900 000-00-00",
        telegram="@autodom_test",
        car_info="Kia Rio (VIN Z94CB41AAER123456)",
        pickup_label="Самовывоз",
        address=None,
        items=ITEMS,
        total=5790.0,
        comment="Проверка доставки уведомления",
        created_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
        is_night=False,
    )
    print(f"MCP-путь: sent={sent} channel={channel}")

    await notifier.stop()

    fallback = TelegramNotifier()
    fallback._disabled = True  # принудительно только Bot API
    sent_fb, channel_fb = await fallback.send_order_notification(
        order_number="TEST-TG-0002",
        customer_name="Тест Telegram (fallback)",
        phone="+7 900 000-00-00",
        telegram=None,
        car_info=None,
        pickup_label="Доставка",
        address="ул. Ленина, д. 10",
        items=ITEMS,
        total=5790.0,
        comment="Проверка резервного канала",
        created_at=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
        is_night=True,
    )
    print(f"Fallback-путь: sent={sent_fb} channel={channel_fb}")

    ok = sent and sent_fb
    print("ИТОГ:", "OK" if ok else "ПРОВАЛ")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
