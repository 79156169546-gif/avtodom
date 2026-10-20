#!/usr/bin/env python3
"""Проверка заказа в базе Neon: заказ, позиции, события, Telegram-кнопки."""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def db_url() -> str:
    text = (ROOT / ".env.local").read_text(encoding="utf-8")
    match = re.search(r"^DATABASE_URL=(.+)$", text, re.M)
    if not match:
        raise SystemExit("нет DATABASE_URL в .env.local")
    return match.group(1).strip().strip('"').strip("'")


async def main(order_number: str) -> int:
    import asyncpg

    pool = await asyncpg.create_pool(db_url(), min_size=1, max_size=2)
    async with pool.acquire() as con:
        row = await con.fetchrow(
            """
            SELECT order_number, status, total, customer_name, phone,
                   pickup_method, is_night_order, created_at
            FROM orders WHERE order_number = $1
            """,
            order_number,
        )
        print("=== orders ===")
        print(" ", dict(row) if row else "не найден")

        items = await con.fetch(
            """
            SELECT oi.product_name, oi.qty, oi.line_total, oi.is_on_order, oi.order_days
            FROM order_items oi JOIN orders o ON o.id = oi.order_id
            WHERE o.order_number = $1
            """,
            order_number,
        )
        print("=== order_items ===")
        for item in items:
            print(" ", dict(item))

        events = await con.fetch(
            """
            SELECT e.status, e.note, e.actor, e.created_at
            FROM order_events e JOIN orders o ON o.id = e.order_id
            WHERE o.order_number = $1
            """,
            order_number,
        )
        print("=== order_events ===")
        for event in events:
            print(" ", dict(event))

        buttons = await con.fetch(
            """
            SELECT tb.message_id, tb.action, tb.label, tb.used_at
            FROM telegram_buttons tb JOIN orders o ON o.id = tb.order_id
            WHERE o.order_number = $1
            """,
            order_number,
        )
        print("=== telegram_buttons (кнопки, которые обработает poller) ===")
        for button in buttons:
            print(" ", dict(button))
        if not buttons:
            print("  (пусто — poller не сможет сопоставить нажатие)")

        total = await con.fetchval("SELECT count(*) FROM orders")
        today = await con.fetchval(
            "SELECT count(*) FROM orders WHERE created_at::date = current_date"
        )
        print(f"=== всего заказов: {total}, за сегодня: {today} ===")
    await pool.close()
    return 0


if __name__ == "__main__":
    number = sys.argv[1] if len(sys.argv) > 1 else "A-261020-0039"
    raise SystemExit(asyncio.run(main(number)))
