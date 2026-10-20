"""Применение схемы БД из backend/schema.sql (идемпотентно).

Запуск:  python backend/scripts/apply_schema.py
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR.parent))

from backend import db  # noqa: E402

SCHEMA_PATH = BACKEND_DIR / "schema.sql"


async def main() -> int:
    if not SCHEMA_PATH.exists():
        print(f"Файл схемы не найден: {SCHEMA_PATH}", file=sys.stderr)
        return 1

    sql = SCHEMA_PATH.read_text(encoding="utf-8")

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        await conn.execute(sql)

    async with pool.acquire() as conn:
        tables = await conn.fetch(
            """
            SELECT table_name FROM information_schema.tables
            WHERE table_schema = 'public' ORDER BY table_name
            """
        )
        columns = await conn.fetch(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'products' AND table_schema = 'public'
            ORDER BY column_name
            """
        )
    print("Таблицы:", ", ".join(row["table_name"] for row in tables))
    print("Колонки products:", ", ".join(row["column_name"] for row in columns))
    await db.close_pool()
    print("Схема применена.")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
