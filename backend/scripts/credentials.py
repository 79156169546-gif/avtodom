"""Учётные данные владельца для автотестов — вне Git.

Пароль владельца не должен лежать в репозитории: репозиторий публичный.
Этот модуль читает его из локального файла `backend/.env.credentials`
(он в .gitignore) или из переменной окружения `STORE_OWNER_PASSWORD`.

Порядок поиска:
1. переменная окружения STORE_OWNER_EMAIL / STORE_OWNER_PASSWORD;
2. файл backend/.env.credentials рядом с этим модулем;
3. значение по умолчанию — если файл не найден, тесты объяснят, что делать.

Использование:
    from credentials import owner_credentials
    email, password = owner_credentials()
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_EMAIL = "owner@autodom.ru"

# Файл с учётными данными лежит рядом с этим модулем (backend/scripts/).
# Он же ищется в backend/ — на случай запуска из другого каталога.
CREDENTIALS_FILES = (
    Path(__file__).resolve().parent.parent / ".env.credentials",
    Path(__file__).resolve().parent / ".env.credentials",
)


def _read_credentials_file() -> dict[str, str]:
    """Читает KEY=VALUE из первого найденного файла учётных данных."""
    for path in CREDENTIALS_FILES:
        if not path.exists():
            continue
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip().strip('"').strip("'")
        if values:
            return values
    return {}


def owner_credentials() -> tuple[str, str]:
    """Возвращает (email, password) владельца магазина.

    Бросает RuntimeError с понятной инструкцией, если пароль не найден:
    тест без пароля владельца всё равно упадёт, но падать должно понятно.
    """
    email = os.environ.get("STORE_OWNER_EMAIL", "").strip()
    password = os.environ.get("STORE_OWNER_PASSWORD", "").strip()

    if not email or not password:
        file_values = _read_credentials_file()
        email = email or file_values.get("STORE_OWNER_EMAIL", "").strip()
        password = password or file_values.get("STORE_OWNER_PASSWORD", "").strip()

    if not password:
        raise RuntimeError(
            "Не найден пароль владельца.\n"
            "Создайте файл backend/.env.credentials с содержимым:\n"
            "    STORE_OWNER_EMAIL=admin@example.com\n"
            "    STORE_OWNER_PASSWORD=<пароль>\n"
            "или задайте переменные окружения STORE_OWNER_EMAIL и "
            "STORE_OWNER_PASSWORD.\n"
            "Сгенерировать новый пароль:\n"
            '    python backend/scripts/create_owner.py --email admin@example.com '
            '--password "<новый>" --rotate'
        )

    return email or DEFAULT_EMAIL, password
