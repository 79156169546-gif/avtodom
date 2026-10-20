#!/usr/bin/env python3
"""Загрузить код в GitHub через Git Data API (без git-протокола).

Нужен, когда `git push` зависает на авторизации: токен уже получен и лежит
в ~/.config/gh/hosts.yml. API-путь не требует интерактивного ввода.

Использование:
    python scripts/push_via_api.py [owner/repo] [branch]
"""

from __future__ import annotations

import base64
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
API = "https://api.github.com"


def load_token() -> str:
    """Токен из конфига gh.

    gh на Windows читает %APPDATA%\\GitHub CLI\\hosts.yml, на остальных
    платформах — ~/.config/gh/hosts.yml. Проверяем оба пути.
    """
    candidates = [
        Path.home() / ".config" / "gh" / "hosts.yml",
        Path(os.environ.get("APPDATA", "")) / "GitHub CLI" / "hosts.yml",
    ]
    for cfg in candidates:
        if not cfg.is_file():
            continue
        match = re.search(r"oauth_token:\s*(\S+)", cfg.read_text(encoding="utf-8"))
        if match:
            return match.group(1)
    raise RuntimeError(
        "нет oauth_token — выполните `gh auth login` "
        "(или `gh auth setup-git` после ручной авторизации)"
    )


def request(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, object]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        f"{API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "autodom-deploy",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as response:
            raw = response.read().decode("utf-8", "replace")
            return response.status, (json.loads(raw) if raw else {})
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        try:
            return exc.code, json.loads(raw)
        except json.JSONDecodeError:
            return exc.code, raw[:400]
    except Exception as exc:  # noqa: BLE001
        return 0, str(exc)


def tracked_files() -> list[tuple[str, bytes]]:
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True, check=True
    )
    result = []
    for raw in out.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8")
        path = ROOT / rel
        if path.is_file():
            result.append((rel, path.read_bytes()))
    return result


def main() -> int:
    repo_slug = sys.argv[1] if len(sys.argv) > 1 else "79156169546-gif/avtodom"
    branch = sys.argv[2] if len(sys.argv) > 2 else "main"
    token = load_token()
    repo = f"/repos/{repo_slug}"

    files = tracked_files()
    print(f"файлов к загрузке: {len(files)}")

    # 1. Блобы — по одному запросу на файл
    tree: list[dict] = []
    for index, (rel, data) in enumerate(files, 1):
        status, payload = request(
            "POST",
            f"{repo}/git/blobs",
            token,
            {"content": base64.b64encode(data).decode("ascii"), "encoding": "base64"},
        )
        if status != 201 or not isinstance(payload, dict) or "sha" not in payload:
            print(f"  ОШИБКА blob {rel}: {status} {str(payload)[:150]}")
            return 1
        tree.append({"path": rel, "mode": "100644", "type": "blob", "sha": payload["sha"]})
        if index % 20 == 0:
            print(f"  blob: {index}/{len(files)}")

    # 2. Дерево
    status, payload = request("POST", f"{repo}/git/trees", token, {"tree": tree})
    if status != 201 or not isinstance(payload, dict) or "sha" not in payload:
        print(f"ОШИБКА tree: {status} {str(payload)[:300]}")
        return 1
    tree_sha = payload["sha"]
    print(f"дерево создано: {tree_sha}")

    # 3. Коммит
    status, ref = request("GET", f"{repo}/git/ref/heads/{branch}", token)
    parents: list[str] = []
    if status == 200 and isinstance(ref, dict):
        parents = [ref["object"]["sha"]]
        print(f"родительский коммит: {parents[0][:8]}")

    status, payload = request(
        "POST",
        f"{repo}/git/commits",
        token,
        {
            "message": "Витрина заказов 24/7: каталог, оформление, кабинеты, Telegram",
            "tree": tree_sha,
            "parents": parents,
        },
    )
    if status != 201 or not isinstance(payload, dict) or "sha" not in payload:
        print(f"ОШИБКА commit: {status} {str(payload)[:300]}")
        return 1
    commit_sha = payload["sha"]
    print(f"коммит: {commit_sha}")

    # 4. Обновляем ветку
    if parents:
        status, payload = request(
            "PATCH", f"{repo}/git/refs/heads/{branch}", token, {"sha": commit_sha, "force": False}
        )
        if status not in (200, 202):
            print(f"ОШИБКА ref: {status} {str(payload)[:300]}")
            return 1
    else:
        status, payload = request(
            "POST", f"{repo}/git/refs", token, {"ref": f"refs/heads/{branch}", "sha": commit_sha}
        )
        if status not in (200, 201, 202):
            print(f"ОШИБКА ref: {status} {str(payload)[:300]}")
            return 1
    print(f"ветка {branch} обновлена")

    # 5. Проверка
    time.sleep(1)
    status, payload = request("GET", f"{repo}/git/ref/heads/{branch}", token)
    if status == 200 and isinstance(payload, dict):
        print(f"ПРОВЕРКА: {branch} -> {payload['object']['sha'][:8]}")
    else:
        print(f"ПРОВЕРКА не удалась: {status}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
