# OpenClaw Agent Console

這份 repo 提供的是一個 **本機控制 OpenClaw AI agent** 的前後端介面；**Lobster 只用來做任務派發，不是 OpenClaw 本身**。

## Repo 內有哪些程式

- `app.py`：後端 HTTP 服務與 JSON API。
- `static/index.html`、`static/app.js`、`static/styles.css`：前端介面。
- `tests/test_server.py`：基本測試。
- `run_local.sh`：macOS / Linux 快速啟動腳本。

## 這次補上的重點：OpenClaw markdown 檔也能設定

你提到 OpenClaw 常會搭配 `memory.md` 與其他 markdown 文件，這次我已經把它們納入 UI 與本機同步流程：

- `memory.md`
- `task.md`
- `tools.md`

這些內容現在可以直接在介面編輯，儲存後會同步寫到：

- `data/openclaw_docs/memory.md`
- `data/openclaw_docs/task.md`
- `data/openclaw_docs/tools.md`

同時 `openclaw agent run` 的預覽命令也會把這些 markdown 檔案帶進去。

## 這個介面可以做什麼

### 1. 本機控制 OpenClaw AI agent

你可以在 UI 裡一次設定 OpenClaw agent 的：

- endpoint
- agent name
- model
- system prompt
- default mission
- max steps
- memory window
- working directory
- headless
- shell / browser 權限
- extra args
- `memory.md`
- `task.md`
- `tools.md`

### 2. 用 Lobster 派發 OpenClaw 任務

Lobster 在這個專案裡扮演的是 **dispatcher / queue runner**：

- 指定 queue
- 指定 target
- 帶入要給 OpenClaw agent 的 mission
- 帶入任務參數 JSON
- 可選擇 Telegram / Discord 通知

換句話說：

- **OpenClaw = AI agent**
- **Lobster = 派發任務給 agent 的工具**

## macOS 使用方式

### 啟動

```bash
./run_local.sh
# 或
python3 app.py
```

然後開啟 <http://127.0.0.1:8000>

## Lobster 安裝

這份 repo 預設不內嵌 Lobster binary，而是讓你在本機安裝後填入：

- `Lobster Command`
- `Workspace`
- `Default Queue`

常見安裝方式：

```bash
brew install lobster
# 或
pip install lobster
```

預設 `Dry Run` 會開啟，方便先確認派發命令。

## Telegram / Discord 通知

### Telegram

請在 UI 內設定：

- `Telegram Bot Token`
- `Telegram Chat ID`

### Discord

請在 UI 內設定：

- `Discord Webhook URL`

## API

- `GET /api/config`
- `POST /api/config`
- `POST /api/openclaw/apply`
- `GET /api/tasks`
- `POST /api/tasks/dispatch`

## 測試

```bash
python3 -m unittest discover -s tests
```

## Git / PR 補充

如果目前工作目錄沒有設定 `git remote`，我可以完成本地 commit，但不能直接 push 到 GitHub 或建立真正的遠端 PR。
