"""Аутентификация: хеширование паролей, сессии, зависимости FastAPI.

Используем PBKDF2-HMAC-SHA256 из стандартной библиотеки — без bcrypt/passlib,
чтобы не тянуть нативные зависимости на Windows.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

try:  # пакетный импорт
    from . import db
except ImportError:  # запуск как top-level модуль (uvicorn main:app)
    import db  # type: ignore[no-redef]

PBKDF2_ITERATIONS = 200_000
SESSION_TTL_DAYS = 30

bearer_scheme = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# Пароли
# ---------------------------------------------------------------------------


def hash_password(password: str) -> str:
    """Формат: pbkdf2_sha256$<iterations>$<salt_hex>$<hash_hex>."""
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS
    )
    return (
        f"pbkdf2_sha256${PBKDF2_ITERATIONS}$"
        f"{salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, stored: str) -> bool:
    """Сравнение пароля с хешем. Неизвестный формат → False."""
    try:
        algorithm, iterations, salt_hex, hash_hex = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(digest.hex(), hash_hex)


# ---------------------------------------------------------------------------
# Сессии
# ---------------------------------------------------------------------------


async def create_session(user_id: int) -> None:
    """Создать сессию, вернуть токен. Истёкшие сессии пользователя чистим."""
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(days=SESSION_TTL_DAYS)
    await db.execute(
        "DELETE FROM auth_sessions WHERE expires_at < now()"
    )
    await db.execute(
        "INSERT INTO auth_sessions (token, user_id, expires_at) VALUES ($1, $2, $3)",
        token,
        user_id,
        expires_at,
    )
    return token


async def drop_session(token: str) -> None:
    await db.execute("DELETE FROM auth_sessions WHERE token = $1", token)


async def _user_for_token(token: str) -> dict | None:
    row = await db.fetchrow(
        """
        SELECT u.id, u.email, u.full_name, u.phone, u.telegram, u.role, u.created_at
        FROM auth_sessions s
        JOIN users u ON u.id = s.user_id
        WHERE s.token = $1 AND s.expires_at > now()
        """,
        token,
    )
    return dict(row) if row else None


def _token_from_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> str | None:
    if credentials is not None and credentials.scheme.lower() == "bearer":
        return credentials.credentials
    header = request.headers.get("x-session-token")
    if header:
        return header.strip()
    return None


async def current_user_optional(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict | None:
    """Текущий пользователь или None (для публичных эндпоинтов)."""
    token = _token_from_request(request, credentials)
    if not token:
        return None
    return await _user_for_token(token)


async def current_user(
    user: dict | None = Depends(current_user_optional),
) -> dict:
    """Текущий пользователь; 401 если не авторизован."""
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Требуется вход в личный кабинет",
        )
    return user


async def current_owner(
    user: dict = Depends(current_user),
) -> dict:
    """Только владелец магазина."""
    if user.get("role") != "owner":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Доступ только для владельца",
        )
    return user
