#!/usr/bin/env python3
"""Автономный деплой «Витрины заказов 24/7»: GitHub → Render (API) → Netlify.

Секреты (DATABASE_URL, TELEGRAM_*) читаются из файлов и уходят в Render
через HTTP-запрос, а не через аргументы командной строки — так они не
светятся в списке процессов.

Использование:
    python scripts/deploy.py            # полный цикл
    python scripts/deploy.py --step env # только обновить CORS_ORIGINS
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND = ROOT / "frontend"
RENDER_API = "https://api.render.com/v1"
SERVICE_NAME = os.environ.get("RENDER_SERVICE_NAME", "avtodom-api")
REPO_NAME = os.environ.get("GITHUB_REPO_NAME", "avtodom")
NETLIFY_SITE_NAME = os.environ.get("NETLIFY_SITE_NAME", "avtodom-storefront")

# --- вспомогательное --------------------------------------------------------


def run(
    cmd: list[str],
    cwd: Path | None = None,
    quiet: bool = False,
    env: dict[str, str] | None = None,
) -> str:
    """Выполнить команду и вернуть stdout; при ошибке — исключение."""
    proc = subprocess.run(
        cmd,
        cwd=str(cwd) if cwd else None,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    out = (proc.stdout or "") + (proc.stderr or "")
    if not quiet:
        print(f"$ {' '.join(cmd)}\n{out.strip()}\n")
    if proc.returncode != 0:
        raise RuntimeError(f"команда завершилась с кодом {proc.returncode}:\n{out.strip()}")
    return out


def read_env_file(path: Path) -> dict[str, str]:
    """Разобрать .env-файл в словарь."""
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        values[key.strip()] = value
    return values


def render_key() -> str:
    """API-ключ Render из ~/.render/cli.yaml (поле api.key)."""
    config = Path.home() / ".render" / "cli.yaml"
    text = config.read_text(encoding="utf-8")
    match = re.search(r"api:\s*\n\s*key:\s*(\S+)", text)
    if not match:
        raise RuntimeError("не найден api.key в ~/.render/cli.yaml — выполните render login")
    return match.group(1)


def render_api(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    """Запрос к Render API. Возвращает (код, разобранный JSON или текст)."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    request = urllib.request.Request(
        f"{RENDER_API}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {render_key()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            raw = response.read().decode("utf-8", "replace")
            status = response.status
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", "replace")
        status = exc.code
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"Render API недоступен: {exc}") from exc
    try:
        return status, json.loads(raw)
    except json.JSONDecodeError:
        return status, raw


def workspace_id() -> str:
    """ID активного воркспейса Render."""
    status, payload = render_api("GET", "/owners")
    if status != 200 or not isinstance(payload, list):
        raise RuntimeError(f"не удалось получить воркспейсы Render: {status} {payload}")
    for item in payload:
        owner = item.get("owner") or {}
        if owner.get("type") == "team" and owner.get("id"):
            return owner["id"]
    raise RuntimeError("в аккаунте Render нет team-воркспейса")


def find_service() -> dict | None:
    """Сервис Render с именем SERVICE_NAME, если он уже создан."""
    status, payload = render_api("GET", f"/services?name={SERVICE_NAME}")
    if status != 200 or not isinstance(payload, list):
        return None
    for service in payload:
        if service.get("name") == SERVICE_NAME:
            return service
    return None


def env_vars_for_render() -> list[dict[str, str]]:
    """Переменные окружения для Render из локальных .env-файлов."""
    local = read_env_file(ROOT / ".env.local")
    telegram = read_env_file(ROOT / "backend" / ".env.telegram")
    database_url = local.get("DATABASE_URL") or ""
    token = telegram.get("TELEGRAM_BOT_TOKEN") or ""
    chat_id = telegram.get("TELEGRAM_CHAT_ID") or ""
    missing = [
        name
        for name, value in (
            ("DATABASE_URL", database_url),
            ("TELEGRAM_BOT_TOKEN", token),
            ("TELEGRAM_CHAT_ID", chat_id),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"в локальных .env-файлах нет: {', '.join(missing)}")
    return [
        {"key": "DATABASE_URL", "value": database_url},
        {"key": "TELEGRAM_BOT_TOKEN", "value": token},
        {"key": "TELEGRAM_CHAT_ID", "value": chat_id},
        {"key": "CORS_ORIGINS", "value": "*"},
        {"key": "TELEGRAM_USE_MCP", "value": "false"},
        {"key": "PYTHON_VERSION", "value": "3.12.8"},
    ]


# --- шаги --------------------------------------------------------------------


def step_github() -> str:
    """Создать репозиторий и запушить код. Возвращает "URL|ветка".

    Репозиторий должен быть ПУБЛИЧНЫМ: Render клонирует публичный репозиторий
    по прямой ссылке, без OAuth-связи между аккаунтами Render и GitHub.
    Приватный репозиторий Render не увидит ("invalid or unfetchable") — пока
    в аккаунте Render не установлено GitHub-приложение.
    """
    existing = run(["gh", "repo", "view", REPO_NAME, "--json", "url"], quiet=True)
    url = re.search(r'"url"\s*:\s*"([^"]+)"', existing)
    if url:
        print(f"репозиторий уже существует: {url.group(1)}")
        repo_url = url.group(1)
    else:
        run(
            [
                "gh", "repo", "create", REPO_NAME,
                "--public", "--source=.", "--remote=origin", "--push",
            ]
        )
        repo_url = re.search(
            r'"url"\s*:\s*"([^"]+)"',
            run(["gh", "repo", "view", REPO_NAME, "--json", "url"], quiet=True),
        ).group(1)
    # пуш всех локальных коммитов
    run(["git", "push", "-u", "origin", "HEAD"], quiet=True)
    branch = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], quiet=True).strip()
    return f"{repo_url}|{branch}"


def step_render(repo_url: str, branch: str) -> str:
    """Создать Web Service на Render. Возвращает публичный URL."""
    existing = find_service()
    if existing:
        print(f"сервис уже существует: {existing.get('name')} ({existing.get('id')})")
        return existing.get("serviceDetails", {}).get("url") or existing.get("url") or ""

    body = {
        "type": "web_service",
        "name": SERVICE_NAME,
        "repo": repo_url,
        "branch": branch,
        "rootDir": "backend",
        "runtime": "python",
        "plan": "free",
        "region": "oregon",
        "buildCommand": "pip install -r requirements.txt",
        "startCommand": "uvicorn main:app --host 0.0.0.0 --port $PORT",
        "healthCheckPath": "/api/health",
        "envVars": env_vars_for_render(),
    }
    status, payload = render_api("POST", "/services", body)
    if status not in (200, 201, 202):
        raise RuntimeError(f"создание сервиса Render не удалось: {status} {payload}")
    service = payload if isinstance(payload, dict) else {}
    print(f"сервис создан: {service.get('name')} id={service.get('id')}")
    return service.get("serviceDetails", {}).get("url") or service.get("url") or ""


def wait_for_backend(url: str, timeout: int = 600) -> dict:
    """Дождаться, пока бэкенд на Render начнёт отвечать 200 на /api/health."""
    if not url:
        raise RuntimeError("не получен URL бэкенда")
    health_url = f"{url.rstrip('/')}/api/health"
    print(f"жду ответа {health_url} (до {timeout} с)")
    deadline = time.time() + timeout
    last_error = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=30) as response:
                if response.status == 200:
                    payload = json.loads(response.read().decode("utf-8", "replace"))
                    print(f"бэкенд отвечает: {payload}")
                    return payload
        except Exception as exc:  # noqa: BLE001
            last_error = str(exc)[:120]
        time.sleep(10)
    raise RuntimeError(f"бэкенд не поднялся за {timeout} с. Последняя ошибка: {last_error}")


def step_netlify(api_base: str) -> str:
    """Собрать фронтенд с адресом API и задеплоить на Netlify. Возвращает URL.

    `netlify deploy` перезапускает `[build].command` из netlify.toml, поэтому
    переменная окружения нужна и для самого deploy — иначе Netlify пересоберёт
    бандл заново уже без VITE_API_BASE и зальёт битый билд.

    Сайт передаётся как ID, а не как имя: `netlify deploy --site=<name>` ищет
    сайт по имени, а CLI-версия аккаунта этот поиск не поддерживает
    ("Failed retrieving site data ... Not Found"). ID берётся из линка
    `.netlify/state.json`, который `netlify link --id` создаёт.
    """
    env = dict(os.environ)
    env["VITE_API_BASE"] = api_base
    print(f"сборка фронтенда с VITE_API_BASE={api_base}")
    run(["npm", "run", "build"], cwd=FRONTEND, env=env)

    site_id = netlify_site_id()
    if site_id:
        run(["netlify", "link", "--id", site_id], cwd=FRONTEND, quiet=True)
    else:
        run(
            ["netlify", "sites:create", "--name", NETLIFY_SITE_NAME, "--disable-linking"],
            cwd=FRONTEND,
        )
        site_id = netlify_site_id()

    out = run(
        ["netlify", "deploy", "--prod", "--dir=dist", f"--site={site_id}"],
        cwd=FRONTEND,
        env=env,
    )
    match = re.search(r"https://[A-Za-z0-9.-]+\.netlify\.app", out)
    if not match:
        raise RuntimeError(f"не удалось извлечь URL из вывода netlify deploy:\n{out}")
    return match.group(0)


def netlify_site_id() -> str:
    """ID связанного Netlify-сайта из .netlify/state.json (пусто, если нет)."""
    state = FRONTEND / ".netlify" / "state.json"
    if not state.exists():
        return ""
    try:
        return json.loads(state.read_text(encoding="utf-8")).get("siteId", "")
    except (json.JSONDecodeError, OSError):
        return ""


def step_update_cors(frontend_url: str) -> None:
    """Заменить CORS_ORIGINS=* на точный домен Netlify."""
    service = find_service()
    if not service:
        raise RuntimeError("сервис Render не найден — нечего обновлять")
    current = service.get("envVars") or []
    updated = []
    for var in current:
        if var.get("key") == "CORS_ORIGINS":
            updated.append({**var, "value": frontend_url})
        else:
            updated.append(var)
    if not any(v.get("key") == "CORS_ORIGINS" for v in updated):
        updated.append({"key": "CORS_ORIGINS", "value": frontend_url})
    status, payload = render_api("PATCH", f"/services/{service['id']}", {"envVars": updated})
    if status not in (200, 202):
        raise RuntimeError(f"не удалось обновить CORS_ORIGINS: {status} {payload}")
    print(f"CORS_ORIGINS на Render = {frontend_url}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--step", choices=["all", "env"], default="all")
    args = parser.parse_args()

    try:
        if args.step == "env":
            frontend_url = sys.argv[sys.argv.index("--frontend-url") + 1] if "--frontend-url" in sys.argv else ""
            step_update_cors(frontend_url)
            return 0

        info = step_github()
        repo_url, branch = info.split("|", 1)
        backend_url = step_render(repo_url, branch)
        if not backend_url:
            backend_url = f"https://{SERVICE_NAME}.onrender.com"
        print(f"URL бэкенда: {backend_url}")

        health = wait_for_backend(backend_url)
        if health.get("database") != "ok":
            print("предупреждение: база данных не отвечает:", health)

        frontend_url = step_netlify(backend_url.rstrip("/"))
        print(f"URL фронтенда: {frontend_url}")

        step_update_cors(frontend_url)

        print("\n=== ГОТОВО ===")
        print(f"Фронтенд: {frontend_url}")
        print(f"Бэкенд:   {backend_url}")
        print(f"Health:   {json.dumps(health, ensure_ascii=False)}")
        return 0
    except Exception as exc:  # noqa: BLE001
        print(f"\nОШИБКА: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
