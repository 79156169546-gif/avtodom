"""Создание/обновление владельца магазина.

Использование:
    python backend/scripts/create_owner.py --email owner@autodom.ru --password "секрет"
    python backend/scripts/create_owner.py --email owner@autodom.ru --password "секрет" --rotate

Если аккаунт уже есть — обновляется пароль (при --rotate) или ничего не
происходит (без флага: сообщается, что аккаунт существует).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR.parent))

from backend import db  # noqa: E402
from backend.auth import hash_password  # noqa: E402


async def main() -> int:
    parser = argparse.ArgumentParser(description="Создать владельца магазина")
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--name", default="Владелец")
    parser.add_argument(
        "--rotate",
        action="store_true",
        help="Обновить пароль, если аккаунт уже существует",
    )
    args = parser.parse_args()

    email = args.email.strip().lower()
    if "@" not in email:
        print("Некорректный e-mail", file=sys.stderr)
        return 1
    if len(args.password) < 6:
        print("Пароль должен быть не короче 6 символов", file=sys.stderr)
        return 1

    pool = await db.get_pool()
    async with pool.acquire() as conn:
        existing = await conn.fetchval(
            "SELECT id FROM users WHERE email = $1", email
        )
        if existing:
            if not args.rotate:
                print(
                    f"Аккаунт {email} уже существует. "
                    "Используйте --rotate, чтобы обновить пароль."
                )
                await db.close_pool()
                return 0
            await conn.execute(
                """
                UPDATE users
                SET password_hash = $1, role = 'owner', full_name = $2
                WHERE email = $3
                """,
                hash_password(args.password),
                args.name,
                email,
            )
            print(f"Пароль владельца {email} обновлён.")
        else:
            await conn.execute(
                """
                INSERT INTO users (email, password_hash, full_name, role)
                VALUES ($1, $2, $3, 'owner')
                """,
                email,
                hash_password(args.password),
                args.name,
            )
            print(f"Владелец {email} создан.")

    await db.close_pool()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
