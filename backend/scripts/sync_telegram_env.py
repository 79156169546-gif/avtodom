"""Синхронизация Telegram-реквизитов из конфига Hermes в backend/.env.telegram.

Токен бота лежит в `mcp_servers.tgbot-mcp.args` глобального config.yaml
Hermes. Этот скрипт достаёт TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID и
кладёт их в `backend/.env.telegram` (в git не попадает), чтобы бэкенд
мог поднять MCP-сервер tgbot-mcp локально.

Запуск:  python backend/scripts/sync_telegram_env.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
PROJECT_ROOT = BACKEND_DIR.parent
TARGET = BACKEND_DIR / ".env.telegram"

TOKEN_RE = re.compile(r"TELEGRAM_BOT_TOKEN=([^\s'\"]+)")
CHAT_RE = re.compile(r"TELEGRAM_CHAT_ID=([^\s'\"]+)")


def find_hermes_config() -> Path | None:
    """Ищем конфиг Hermes, в котором реально есть блок tgbot-mcp."""
    candidates = [
        Path.home() / "AppData" / "Local" / "hermes" / "config.yaml",
        Path.home() / ".hermes" / "config.yaml",
    ]
    for candidate in candidates:
        if not candidate.exists():
            continue
        text = candidate.read_text(encoding="utf-8", errors="replace")
        if TOKEN_RE.search(text) and CHAT_RE.search(text):
            return candidate
    return None


def main() -> int:
    config_path = find_hermes_config()
    if config_path is None:
        print("config.yaml Hermes не найден.", file=sys.stderr)
        return 1

    text = config_path.read_text(encoding="utf-8", errors="replace")
    token_match = TOKEN_RE.search(text)
    chat_match = CHAT_RE.search(text)
    if not token_match or not chat_match:
        print(
            "В config.yaml не найдены TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID "
            "(блок mcp_servers.tgbot-mcp).",
            file=sys.stderr,
        )
        return 1

    TARGET.write_text(
        f"TELEGRAM_BOT_TOKEN={token_match.group(1)}\n"
        f"TELEGRAM_CHAT_ID={chat_match.group(1)}\n",
        encoding="utf-8",
    )
    print(f"Записано: {TARGET} (значения не выведены)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
