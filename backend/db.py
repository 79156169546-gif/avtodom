"""Слой доступа к PostgreSQL (Neon) на asyncpg."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any

import asyncpg

try:  # пакетный импорт
    from . import settings
except ImportError:  # запуск как top-level модуль (uvicorn main:app)
    import settings  # type: ignore[no-redef]

_pool: asyncpg.Pool | None = None


async def get_pool() -> asyncpg.Pool:
    """Ленивая инициализация пула соединений."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            settings.DATABASE_URL,
            min_size=1,
            max_size=5,
            command_timeout=30,
        )
    return _pool


async def close_pool() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None


async def fetch(query: str, *args: Any) -> list[asyncpg.Record]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)


async def fetchrow(query: str, *args: Any) -> asyncpg.Record | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)


async def fetchval(query: str, *args: Any) -> Any:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


@asynccontextmanager
async def transaction():
    """Контекстный менеджер атомарной транзакции (yield conn).

    Все запросы внутри либо применяются целиком, либо не применяются.
    Нужен, например, при пакетном сохранении настроек магазина.
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        async with conn.transaction():
            yield conn


async def execute(query: str, *args: Any) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)
