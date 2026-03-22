from __future__ import annotations

import json
import os
import subprocess
from dataclasses import asdict, dataclass
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
DOCS_DIR = DATA_DIR / "openclaw_docs"

DEFAULT_CONFIG = {
    "openclaw": {
        "endpoint": "http://127.0.0.1:8080",
        "agentName": "research-agent",
        "model": "gpt-4.1",
        "systemPrompt": "You are OpenClaw, a local automation agent.",
        "mission": "Collect findings, update files, and report results.",
        "maxSteps": 12,
        "memoryWindow": 8,
        "headless": False,
        "allowShell": True,
        "allowBrowser": True,
        "workingDirectory": "~/openclaw-workspace",
        "extraArgs": "",
        "docs": {
            "memoryMd": "# memory.md\n\n- Product: OpenClaw agent console\n- Goals: keep task context and prior discoveries\n- Constraints: run locally on macOS\n",
            "taskMd": "# task.md\n\n## Objective\n- Investigate the assigned target\n\n## Deliverable\n- Produce a markdown summary with findings\n",
            "toolsMd": "# tools.md\n\n- shell: enabled\n- browser: enabled\n- notifications: telegram / discord\n",
        },
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
    DOCS_DIR.mkdir(exist_ok=True)
    if not CONFIG_PATH.exists():
        CONFIG_PATH.write_text(json.dumps(DEFAULT_CONFIG, indent=2), encoding="utf-8")
    if not TASKS_PATH.exists():
        TASKS_PATH.write_text("[]", encoding="utf-8")
    config = merge_config(read_json(CONFIG_PATH, DEFAULT_CONFIG))
    write_json(CONFIG_PATH, config)
    sync_markdown_files(config)


def merge_config(config: dict[str, Any]) -> dict[str, Any]:
    merged = json.loads(json.dumps(DEFAULT_CONFIG))
    for section, values in config.items():
        if isinstance(values, dict) and isinstance(merged.get(section), dict):
            merged[section].update(values)
            if section == "openclaw" and isinstance(values.get("docs"), dict):
                merged[section]["docs"].update(values["docs"])
        else:
            merged[section] = values
    return merged


def read_json(path: Path, fallback: Any) -> Any:
    if not path.exists():
        return fallback
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def sync_markdown_files(config: dict[str, Any]) -> dict[str, Path]:
    DOCS_DIR.mkdir(exist_ok=True)
    docs = config["openclaw"].get("docs", {})
    paths = {
        "memoryMd": DOCS_DIR / "memory.md",
        "taskMd": DOCS_DIR / "task.md",
        "toolsMd": DOCS_DIR / "tools.md",
    }
    for key, path in paths.items():
        path.write_text(docs.get(key, ""), encoding="utf-8")
    return paths


@dataclass
class DispatchResult:
    ok: bool
    command: list[str]
    stdout: str
    stderr: str
    code: int
    task: dict[str, Any]


class OpenClawService:
    def __init__(self, config: dict[str, Any]):
        self.config = config

    def preview_command(self) -> list[str]:
        agent = self.config["openclaw"]
        doc_paths = sync_markdown_files(self.config)
        command = [
            "openclaw",
            "agent",
            "run",
            "--endpoint",
            agent["endpoint"],
            "--name",
            agent["agentName"],
            "--model",
            agent["model"],
            "--max-steps",
            str(agent["maxSteps"]),
            "--memory-window",
            str(agent["memoryWindow"]),
            "--working-directory",
            agent["workingDirectory"],
            "--mission",
            agent["mission"],
            "--system-prompt",
            agent["systemPrompt"],
            "--memory-file",
            str(doc_paths["memoryMd"]),
            "--task-file",
            str(doc_paths["taskMd"]),
            "--tools-file",
            str(doc_paths["toolsMd"]),
        ]
        if agent.get("headless"):
            command.append("--headless")
        if agent.get("allowShell"):
            command.append("--allow-shell")
        if agent.get("allowBrowser"):
            command.append("--allow-browser")
        if agent.get("extraArgs"):
            command.extend(agent["extraArgs"].split())
        return command


class LobsterService:
    def __init__(self, config: dict[str, Any]):
        self.config = config

    def dispatch(self, task: dict[str, Any]) -> DispatchResult:
        lobster_config = self.config["lobster"]
        agent = self.config["openclaw"]
        command = [
            lobster_config["command"],
            "dispatch",
            "--queue",
            task["queue"],
            "--target",
            task["target"],
            "--agent",
            agent["agentName"],
            "--model",
            agent["model"],
            "--mission",
            task["mission"],
            "--payload",
            json.dumps(task["parameters"], ensure_ascii=False),
        ]

        if task.get("channel") and task["channel"] != "none":
            command.extend(["--channel", task["channel"]])

        if lobster_config.get("dryRun", True):
            return DispatchResult(
                ok=True,
                command=command,
                stdout="Dry-run mode enabled; Lobster dispatch command was not executed.",
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
            payload = merge_config(self._read_json())
            write_json(CONFIG_PATH, payload)
            sync_markdown_files(payload)
            self._send_json({"ok": True, "config": payload})
            return
        if self.path == "/api/openclaw/apply":
            payload = self._read_json()
            config = merge_config(read_json(CONFIG_PATH, DEFAULT_CONFIG))
            config["openclaw"].update(payload)
            if isinstance(payload.get("docs"), dict):
                config["openclaw"]["docs"].update(payload["docs"])
            write_json(CONFIG_PATH, config)
            preview = OpenClawService(config).preview_command()
            self._send_json(
                {
                    "ok": True,
                    "message": "OpenClaw agent settings and markdown docs saved locally.",
                    "preview": " ".join(preview),
                }
            )
            return
        if self.path == "/api/tasks/dispatch":
            payload = self._read_json()
            config = merge_config(read_json(CONFIG_PATH, DEFAULT_CONFIG))
            task = {
                "id": datetime.now(timezone.utc).strftime("task-%Y%m%d%H%M%S"),
                "name": payload["name"],
                "queue": payload.get("queue") or config["lobster"]["defaultQueue"],
                "target": payload["target"],
                "channel": payload.get("channel", "telegram"),
                "mission": payload.get("mission") or config["openclaw"]["mission"],
                "agentName": config["openclaw"]["agentName"],
                "parameters": payload.get("parameters", {}),
                "createdAt": datetime.now(timezone.utc).isoformat(),
            }
            dispatch_result = LobsterService(config).dispatch(task)
            history = read_json(TASKS_PATH, [])
            history.insert(0, {**task, **asdict(dispatch_result)})
            write_json(TASKS_PATH, history)
            notifications = NotificationService(config).send(
                "Lobster task dispatched" if dispatch_result.ok else "Lobster task failed",
                f"Task: {task['name']}\nQueue: {task['queue']}\nOpenClaw agent: {config['openclaw']['agentName']}\nStatus: {'ok' if dispatch_result.ok else 'failed'}",
            )
            status = HTTPStatus.OK if dispatch_result.ok else HTTPStatus.BAD_GATEWAY
            self._send_json(
                {"ok": dispatch_result.ok, "result": asdict(dispatch_result), "notifications": notifications},
                status=status,
            )
            return
        self.send_error(HTTPStatus.NOT_FOUND, "Unknown endpoint")

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
