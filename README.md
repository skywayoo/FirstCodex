# OpenClaw Local Control Center

這個專案提供一個可以在 **macOS 本機** 執行的前後端介面，讓你可以：

- 在同一個頁面調整 OpenClaw 的 endpoint、profile、併發、timeout、retry、headless 與額外參數。
- 將設定保存到本機 JSON 檔案，並立即預覽對應的 OpenClaw CLI 指令。
- 透過 Lobster 進行任務派發，並保存派發歷史。
- 在派發後嘗試發送 Telegram 或 Discord 通知。

## 專案結構

- `app.py`：純 Python 後端，提供靜態頁面與 JSON API。
- `static/`：前端頁面、樣式與互動腳本。
- `data/`：執行後自動產生的本機設定與派發紀錄。
- `tests/`：基本單元測試。

## macOS 使用方式

### 1. 啟動

```bash
python3 app.py
```

啟動後開啟：<http://127.0.0.1:8000>

### 2. 設定 OpenClaw

在畫面左側可以一次設定：

- OpenClaw endpoint
- profile
- concurrency
- timeoutSeconds
- retryCount
- environment
- headless
- extraArgs

按下 **「套用 OpenClaw 設定」** 後，系統會更新本機設定並顯示 CLI 預覽。

## Lobster 安裝與整合

這個專案預設 **不直接內嵌 Lobster 二進位**，而是透過 README 指引安裝，原因是：

- macOS 上你可能會依照自己的 Python / Homebrew / 內部發行方式安裝 Lobster。
- 你可以直接在介面裡指定 `Lobster Command` 與 `Workspace`，不綁定固定路徑。
- 如果你之後要改成 bundle 方式，也可以把 `lobster` 可執行檔放進 repo，再把 `command` 改成相對路徑。

### 建議安裝方式

依你實際使用的 Lobster 專案而定，常見做法包括：

```bash
brew install lobster
# 或
pip install lobster
# 或改成你內部的安裝方式
```

安裝完成後，請在畫面中填入：

- `Lobster Command`：例如 `lobster`
- `Workspace`：例如 `~/lobster-workspace`
- `Default Queue`：例如 `general`

### Dry Run 模式

預設啟用 `Dry Run`，用來安全確認派發命令是否正確。關閉後，後端才會真的執行：

```bash
lobster dispatch --queue <queue> --target <target> --profile <profile> --params '<json>'
```

## Telegram / Discord 通知

### Telegram

請在介面內填寫：

- `Telegram Bot Token`
- `Telegram Chat ID`

派發後會呼叫 Telegram Bot API `sendMessage`。

### Discord

請在介面內填寫：

- `Discord Webhook URL`

派發後會以 webhook 發送訊息。

## API 摘要

- `GET /api/config`：讀取目前設定
- `POST /api/config`：儲存全部設定
- `POST /api/openclaw/apply`：只更新 OpenClaw 區塊並回傳 CLI 預覽
- `GET /api/tasks`：讀取派發歷史
- `POST /api/tasks/dispatch`：派發 Lobster 任務並通知

## 測試

```bash
python3 -m unittest discover -s tests
```
