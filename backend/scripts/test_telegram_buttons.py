"""Проверка обработки нажатий на inline-кнопки Telegram.

Эмулирует callback_query, который Telegram присылает при нажатии на кнопку
«Принял / Перезвонил / Отказ», и проверяет, что статус заказа в БД изменился,
а событие попало в таймлайн.

Запуск:  python backend/scripts/test_telegram_buttons.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR.parent))

from backend import db  # noqa: E402
from backend.telegram import BUTTON_ACTIONS, notifier  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    if condition:
        PASSED.append(name)
        print(f"  OK   {name}")
    else:
        FAILED.append(f"{name} — {detail}")
        print(f"  FAIL {name}: {detail}")


async def main() -> int:
    # 1. Берём последний заказ, у которого есть сохранённая привязка кнопок.
    order = await db.fetchrow(
        """
        SELECT o.id, o.order_number, o.status
        FROM telegram_buttons b
        JOIN orders o ON o.id = b.order_id
        ORDER BY b.id DESC
        LIMIT 1
        """
    )
    if order is None:
        print("Нет заказов с привязкой к Telegram-кнопкам.", file=sys.stderr)
        print("Сначала оформите заказ через витрину.", file=sys.stderr)
        await db.close_pool()
        return 1

    print(f"\nЗаказ для проверки: {order['order_number']} (статус {order['status']})")

    button = await db.fetchrow(
        """
        SELECT message_id, label, action, used_at
        FROM telegram_buttons
        WHERE order_id = $1 ORDER BY id DESC LIMIT 1
        """,
        order["id"],
    )
    if button is None:
        print("У заказа нет сохранённых кнопок.", file=sys.stderr)
        await db.close_pool()
        return 1

    print(f"Кнопка: «{button['label']}» (message_id={button['message_id']})")

    # 2. Эмулируем callback_query от Telegram.
    expected_status, expected_note = BUTTON_ACTIONS[button["label"]]
    await notifier._handle_callback(
        {
            "id": "test-callback-id",
            "data": button["label"],
            "message": {"message_id": button["message_id"]},
        }
    )

    # 3. Проверяем результат в БД.
    updated = await db.fetchrow(
        "SELECT status FROM orders WHERE id = $1", order["id"]
    )
    check(
        f"статус заказа изменён на «{expected_status}»",
        updated["status"] == expected_status,
        f"в базе {updated['status']}",
    )

    event = await db.fetchrow(
        """
        SELECT status, note, actor FROM order_events
        WHERE order_id = $1 ORDER BY id DESC LIMIT 1
        """,
        order["id"],
    )
    check(
        "событие записано в таймлайн",
        event is not None and event["status"] == expected_status,
        str(dict(event)) if event else "нет события",
    )
    check(
        "подпись события совпадает",
        event is not None and event["note"] == expected_note,
        event["note"] if event else "",
    )
    check("актор — менеджер", event is not None and event["actor"] == "manager", "")

    used = await db.fetchval(
        "SELECT used_at FROM telegram_buttons WHERE order_id = $1 LIMIT 1",
        order["id"],
    )
    check("кнопка помечена использованной", used is not None, "used_at пуст")

    # 4. Повторное нажатие той же кнопки не должно менять статус.
    await notifier._handle_callback(
        {
            "id": "test-callback-id-2",
            "data": button["label"],
            "message": {"message_id": button["message_id"]},
        }
    )
    again = await db.fetchrow(
        "SELECT status FROM orders WHERE id = $1", order["id"]
    )
    check(
        "повторное нажатие игнорируется",
        again["status"] == expected_status,
        f"статус изменился на {again['status']}",
    )

    # 5. Кнопка «Отказ» на другом заказе.
    other = await db.fetchrow(
        """
        SELECT o.id, o.order_number, o.status FROM orders o
        WHERE o.id <> $1 AND o.status = 'new'
        ORDER BY o.id DESC LIMIT 1
        """,
        order["id"],
    )
    if other is not None:
        await db.execute(
            """
            INSERT INTO telegram_buttons (order_id, message_id, action, label)
            VALUES ($1, $2, 'rejected', '❌ Отказ')
            ON CONFLICT DO NOTHING
            """,
            other["id"],
            999_000_001,
        )
        await notifier._handle_callback(
            {
                "id": "test-callback-reject",
                "data": "❌ Отказ",
                "message": {"message_id": 999_000_001},
            }
        )
        rejected = await db.fetchrow(
            "SELECT status FROM orders WHERE id = $1", other["id"]
        )
        check(
            "кнопка «Отказ» ставит статус rejected",
            rejected["status"] == "rejected",
            f"в базе {rejected['status']}",
        )

    await db.close_pool()
    print(f"\n{'=' * 60}")
    print(f"Пройдено: {len(PASSED)}   Провалено: {len(FAILED)}")
    if FAILED:
        for item in FAILED:
            print(f"  ✗ {item}")
        return 1
    print("ИТОГ: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
