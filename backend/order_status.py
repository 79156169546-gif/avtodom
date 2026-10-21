"""Смена статуса заказа — общая точка для API и Telegram.

Держим в отдельном модуле, чтобы telegram.py и main.py пользовались
одним кодом без циклического импорта.

completed_at — момент выполнения заказа. По нему считается выручка:
пока заказ не в статусе completed, его сумма в выручку не входит.
"""

from __future__ import annotations

from typing import Any


async def apply_order_status(
    conn: Any,
    order_id: int,
    status: str,
    *,
    note: str | None = None,
    actor: str = "manager",
    status_label: str | None = None,
) -> None:
    """Сменить статус заказа и записать событие в историю.

    conn — соединение asyncpg (или любой объект с await conn.execute(...)).
    completed_at ставится при первом переходе в completed и обнуляется,
    если статус ушёл из completed (заказ переоткрыли).
    """
    await conn.execute(
        """
        UPDATE orders
        SET status = $1,
            updated_at = now(),
            completed_at = CASE
                WHEN $1 = 'completed' THEN COALESCE(completed_at, now())
                ELSE NULL
            END
        WHERE id = $2
        """,
        status,
        order_id,
    )

    default_note = f"Статус изменён на «{status_label or status}»"
    await conn.execute(
        """
        INSERT INTO order_events (order_id, status, note, actor)
        VALUES ($1, $2, $3, $4)
        """,
        order_id,
        status,
        note or default_note,
        actor,
    )
