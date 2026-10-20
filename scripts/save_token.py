#!/usr/bin/env python3
"""Приём токена от браузера и запись его в ~/.config/gh/hosts.yml.

Браузер не может писать на диск, поэтому он отправляет токен POST-ом на
локальный сервер (scripts/serve_files.py), а этот скрипт сохраняет его
в файл конфигурации gh, откуда его подхватит gh CLI.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

HOME = Path.home()
TARGET = HOME / ".config" / "gh" / "hosts.yml"


def main() -> int:
    if len(sys.argv) < 2:
        print("использование: save_token.py <token>", file=sys.stderr)
        return 1
    token = sys.argv[1].strip()
    if not token.startswith("ghp_") or len(token) < 30:
        print("не похоже на токен GitHub", file=sys.stderr)
        return 1
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    TARGET.write_text(
        "github.com:\n"
        f"    oauth_token: {token}\n"
        "    user: 79156169546-gif\n"
        "    git_protocol: https\n",
        encoding="utf-8",
    )
    try:
        os.chmod(TARGET, 0o600)
    except OSError:
        pass
    print(f"токен сохранён в {TARGET}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
