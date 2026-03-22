from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib import error, parse, request

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
DATA_DIR = BASE_DIR / "data"
CONFIG_PATH = DATA_DIR / "config.json"
TASKS_PATH = DATA_DIR / "tasks.json"

DEFAULT_CONFIG = {
    "openclaw": {
        "endpoint": "http://127.0.0.1:8080",
        "profile": "default",
        "concurrency": 2,
        "headless": False,
        "timeoutSeconds": 120,
        "retryCount": 1,
        "environment": "local-macos",
        "extraArgs": "",
    },
    "lobster": {
        "command": "lobster",
        "workspace": "~/lobster-workspace",
        "defaultQueue": "general",
        "dryRun": True,
    },
    "notifications": {
        "telegramBotToken": "",
        "telegramChatId": "",
        "discordWebhookUrl": "",
        "notifyOnDispatch": True,
        "notifyOnError": True,
    },
}


def ensure_data_files() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    if not TASKS_PATH.exists():
        TASKS_PATH.write_text("[]", encoding="utf-8")


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


@dataclass
class DispatchResult:
    ok: bool
    command: list[str]
    stdout: str
    stderr: str
    code: int
    task: dict[str, Any]


class LobsterService:
    def __init__(self, config: dict[str, Any]):
        self.config = config

    def dispatch(self, task: dict[str, Any]) -> DispatchResult:
        lobster_config = self.config["lobster"]
        command = [
            lobster_config["command"],
            "dispatch",
            "--queue",
            task["queue"],
            "--target",
            task["target"],
            "--profile",
            self.config["openclaw"]["profile"],
            "--params",
            json.dumps(task["parameters"], ensure_ascii=False),
        ]

        if task.get("channel"):
            command.extend(["--channel", task["channel"]])

        if lobster_config.get("dryRun", True):
            return DispatchResult(
                ok=True,
                command=command,
                stdout="Dry-run mode enabled; command was not executed.",
                stderr="",
                code=0,
                task=task,
            )

        completed = subprocess.run(
            command,
            cwd=os.path.expanduser(lobster_config["workspace"]),
            text=True,
            capture_output=True,
            check=False,
        )
        return DispatchResult(
            ok=completed.returncode == 0,
            command=command,
            stdout=completed.stdout,
            stderr=completed.stderr,
            code=completed.returncode,
            task=task,
        )


class NotificationService:
    def __init__(self, config: dict[str, Any]):
        self.config = config

    def send(self, title: str, message: str) -> list[str]:
        results: list[str] = []
        notifications = self.config["notifications"]
        if notifications.get("telegramBotToken") and notifications.get("telegramChatId"):
            results.append(self._send_telegram(title, message))
        if notifications.get("discordWebhookUrl"):
            results.append(self._send_discord(title, message))
        if not results:
            results.append("No notification channel configured.")
        return results

    def _send_telegram(self, title: str, message: str) -> str:
        notifications = self.config["notifications"]
        payload = parse.urlencode({
            "chat_id": notifications["telegramChatId"],
            "text": f"{title}\n{message}",
        }).encode()
        url = f"https://api.telegram.org/bot{notifications['telegramBotToken']}/sendMessage"
        try:
            request.urlopen(request.Request(url, data=payload, method="POST"), timeout=10).read()
            return "Telegram notification sent."
        except error.URLError as exc:
            return f"Telegram notification failed: {exc}"

    def _send_discord(self, title: str, message: str) -> str:
        payload = json.dumps({"content": f"**{title}**\n{message}"}).encode()
        try:
            request.urlopen(
                request.Request(
                    self.config["notifications"]["discordWebhookUrl"],
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                ),
                timeout=10,
            ).read()
            return "Discord notification sent."
        except error.URLError as exc:
            return f"Discord notification failed: {exc}"


class OpenClawHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, directory=str(STATIC_DIR), **kwargs)

    def do_GET(self) -> None:
        ensure_data_files()
        if self.path == "/api/config":
            self._send_json(read_json(CONFIG_PATH, DEFAULT_CONFIG))
            return
        if self.path == "/api/tasks":
            self._send_json(read_json(TASKS_PATH, []))
            return
        return super().do_GET()

    def do_POST(self) -> None:
        ensure_data_files()
        if self.path == "/api/config":
            payload = self._read_json()
            write_json(CONFIG_PATH, payload)
            self._send_json({"ok": True, "config": payload})
            return
        if self.path == "/api/openclaw/apply":
            payload = self._read_json()
            config = read_json(CONFIG_PATH, DEFAULT_CONFIG)
            config["openclaw"].update(payload)
            write_json(CONFIG_PATH, config)
            cmd_preview = self._build_openclaw_preview(config)
            self._send_json({"ok": True, "message": "OpenClaw settings saved locally.", "preview": cmd_preview})
            return
        if self.path == "/api/tasks/dispatch":
            payload = self._read_json()
            config = read_json(CONFIG_PATH, DEFAULT_CONFIG)
            task = {
                "id": datetime.now(timezone.utc).strftime("task-%Y%m%d%H%M%S"),
                "name": payload["name"],
                "queue": payload.get("queue") or config["lobster"]["defaultQueue"],
                "target": payload["target"],
                "channel": payload.get("channel", "telegram"),
                "parameters": payload.get("parameters", {}),
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            dispatch_result = LobsterService(config).dispatch(task)
            history = read_json(TASKS_PATH, [])
            history.insert(0, {**task, **asdict(dispatch_result)})
            write_json(TASKS_PATH, history)
            notifications = NotificationService(config).send(
                "Lobster task dispatched" if dispatch_result.ok else "Lobster task failed",
                f"Task: {task['name']}\nQueue: {task['queue']}\nTarget: {task['target']}\nStatus: {'ok' if dispatch_result.ok else 'failed'}",
            )
            status = HTTPStatus.OK if dispatch_result.ok else HTTPStatus.BAD_GATEWAY
            self._send_json({"ok": dispatch_result.ok, "result": asdict(dispatch_result), "notifications": notifications}, status=status)
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")

    def _build_openclaw_preview(self, config: dict[str, Any]) -> str:
        openclaw = config["openclaw"]
        return (
            f"openclaw --endpoint {openclaw['endpoint']} --profile {openclaw['profile']} "
            f"--concurrency {openclaw['concurrency']} --timeout {openclaw['timeoutSeconds']} "
            f"--retries {openclaw['retryCount']} {'--headless' if openclaw['headless'] else ''} {openclaw['extraArgs']}"
        ).strip()

    def _read_json(self) -> dict[str, Any]:
        content_length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(content_length) if content_length else b"{}"
        return json.loads(raw.decode("utf-8") or "{}")

    def _send_json(self, payload: Any, status: HTTPStatus = HTTPStatus.OK) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def run_server(port: int = 8000) -> None:
    ensure_data_files()
    server = ThreadingHTTPServer(("127.0.0.1", port), OpenClawHandler)
    print(f"OpenClaw control center running at http://127.0.0.1:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run_server(int(os.environ.get("PORT", "8000")))
