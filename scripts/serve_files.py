#!/usr/bin/env python3
"""Отдать содержимое отслеживаемых git-файлов на localhost для push через Git Data API.

Запуск: python scripts/serve_files.py [порт]
"""

from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def collect_files() -> list[dict]:
    """Список отслеживаемых git-файлов с base64-содержимым."""
    out = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=str(ROOT), capture_output=True, check=True,
    )
    files = []
    for raw in out.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8")
        path = ROOT / rel
        if not path.is_file():
            continue
        data = path.read_bytes()
        files.append({
            "path": rel,
            "b64": base64.b64encode(data).decode("ascii"),
            "size": len(data),
        })
    return files


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path.startswith("/files"):
            payload = json.dumps(collect_files()).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self.end_headers()
            self.wfile.write(payload)
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        """Сохранить токен, полученный от браузера, в конфиг gh."""
        length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(length).decode("utf-8", "replace")
        try:
            token = json.loads(body).get("token", "").strip()
        except json.JSONDecodeError:
            token = body.strip()
        if not token.startswith("ghp_") or len(token) < 30:
            self._json({"ok": False, "error": "невалидный токен"}, 400)
            return
        target = Path.home() / ".config" / "gh" / "hosts.yml"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "github.com:\n"
            f"    oauth_token: {token}\n"
            "    user: 79156169546-gif\n"
            "    git_protocol: https\n",
            encoding="utf-8",
        )
        try:
            os.chmod(target, 0o600)
        except OSError:
            pass
        self._json({"ok": True, "path": str(target)})

    def _json(self, payload: dict, status: int = 200) -> None:
        raw = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, *args) -> None:
        pass


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
    server = HTTPServer(("127.0.0.1", port), Handler)
    print(f"слушаю http://127.0.0.1:{port}/files", flush=True)
    threading.Thread(target=server.serve_forever, daemon=False).start()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
