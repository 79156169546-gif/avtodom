"""Конфигурация приложения.

Источники:
  * корень проекта `../.env.local` — DATABASE_URL (Neon)
  * `backend/.env.telegram` — TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
    (генерируется скриптом `backend/scripts/sync_telegram_env.py` из
    конфига Hermes, чтобы токен не попадал в исходники)
  * переменные окружения имеют приоритет над файлами.
"""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_DIR.parent

TRUE_VALUES = {"1", "true", "yes", "on"}


def _parse_env_file(path: Path) -> dict[str, str]:
    """Минимальный парсер .env: KEY=value, KEY="value", KEY='value'."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _load(*paths: Path) -> dict[str, str]:
    merged: dict[str, str] = {}
    for path in paths:
        merged.update(_parse_env_file(path))
    return merged


_FILE_VALUES = _load(
    BACKEND_DIR / ".env",
    BACKEND_DIR / ".env.telegram",
    PROJECT_ROOT / ".env.local",
)


def _get(key: str, default: str = "") -> str:
    return os.environ.get(key) or _FILE_VALUES.get(key, default)


def _get_bool(key: str, default: bool = False) -> bool:
    raw = _get(key, "").strip().lower()
    if not raw:
        return default
    return raw in TRUE_VALUES


DATABASE_URL: str = _get("DATABASE_URL")
TELEGRAM_BOT_TOKEN: str = _get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID: str = _get("TELEGRAM_CHAT_ID")
# Username бота без @ — нужен для ссылки-подписки t.me/<bot>?start=<заказ>.
TELEGRAM_BOT_USERNAME: str = _get("TELEGRAM_BOT_USERNAME", "avtodomrzn_bot").lstrip("@")

# Разрешённые origins фронтенда (dev-сервер Vite).
CORS_ORIGINS: list[str] = [
    origin.strip()
    for origin in _get(
        "CORS_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:4173,http://localhost:4173",
    ).split(",")
    if origin.strip()
]

# Часовой пояс магазина (Москва) — определяет «ночной заказ».
STORE_UTC_OFFSET_HOURS: int = int(_get("STORE_UTC_OFFSET_HOURS", "3"))

# Режим работы магазина. Заказы в нерабочие часы — приоритетные.
STORE_OPEN_HOUR: int = int(_get("STORE_OPEN_HOUR", "8"))
STORE_CLOSE_HOUR: int = int(_get("STORE_CLOSE_HOUR", "20"))

# Контакты магазина — показываются в шапке витрины.
# Дефолты — нейтральные (white-label шаблон). Для клиента меняются в .env
# (или прямо из «Кабинета владельца» — тогда значение лежит в БД и имеет
# приоритет над этими дефолтами, см. backend/main.py, /api/store).
STORE_NAME: str = _get("STORE_NAME", "Автомагазин")
STORE_SLOGAN: str = _get("STORE_SLOGAN", "Запчасти для вашего авто")
STORE_CITY: str = _get("STORE_CITY", "Ваш город")
STORE_PHONE: str = _get("STORE_PHONE", "+7 (999) 000-00-00")
STORE_PHONE_HREF: str = _get("STORE_PHONE_HREF", "tel:+79990000000")
STORE_ADDRESS: str = _get("STORE_ADDRESS", "Ваш город, ул. Примерная, 1")
STORE_MAPS_URL: str = _get("STORE_MAPS_URL", "#")
STORE_LOGO: str = _get("STORE_LOGO", "")
STORE_LAT: float = float(_get("STORE_LAT", "0"))
STORE_LON: float = float(_get("STORE_LON", "0"))
STORE_RATING: str = _get("STORE_RATING", "5.0")
STORE_RATING_COUNT: int = int(_get("STORE_RATING_COUNT", "10"))

# 20:00–08:00 — нерабочее время, заказы в приоритете.
NIGHT_ORDER_START_HOUR: int = int(_get("NIGHT_ORDER_START_HOUR", "20"))
NIGHT_ORDER_END_HOUR: int = int(_get("NIGHT_ORDER_END_HOUR", "8"))

# Телеграм-уведомления: primary — через MCP-сервер tgbot-mcp,
# fallback — прямой вызов Bot API, если MCP недоступен.
TELEGRAM_USE_MCP: bool = _get_bool("TELEGRAM_USE_MCP", True)
TELEGRAM_MCP_COMMAND: str = _get("TELEGRAM_MCP_COMMAND", "uvx")
TELEGRAM_MCP_PACKAGE: str = _get("TELEGRAM_MCP_PACKAGE", "tgbot-mcp")
TELEGRAM_MCP_TIMEOUT_SECONDS: int = int(_get("TELEGRAM_MCP_TIMEOUT_SECONDS", "120"))


def validate() -> None:
    """Проверки при старте — падаем громко, а не молча."""
    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL не найден. Ожидается файл .env.local в корне проекта."
        )
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            "Не заданы TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID. "
            "Запустите backend/scripts/sync_telegram_env.py или задайте переменные вручную."
        )
