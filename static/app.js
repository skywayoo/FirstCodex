const qs = (id) => document.getElementById(id);

async function fetchJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  return response.json();
}

function getConfigPayload() {
  return {
    openclaw: {
      endpoint: qs('endpoint').value,
      profile: qs('profile').value,
      concurrency: Number(qs('concurrency').value),
      headless: qs('headless').checked,
      timeoutSeconds: Number(qs('timeoutSeconds').value),
      retryCount: Number(qs('retryCount').value),
      environment: qs('environment').value,
      extraArgs: qs('extraArgs').value,
    },
    lobster: {
      command: qs('lobster-command').value,
      workspace: qs('lobster-workspace').value,
      defaultQueue: qs('lobster-queue').value,
      dryRun: qs('lobster-dryrun').checked,
    },
    notifications: {
      telegramBotToken: qs('telegram-token').value,
      telegramChatId: qs('telegram-chat').value,
      discordWebhookUrl: qs('discord-webhook').value,
      notifyOnDispatch: true,
      notifyOnError: true,
    },
  };
}

function hydrateConfig(config) {
  const { openclaw, lobster, notifications } = config;
  qs('endpoint').value = openclaw.endpoint;
  qs('profile').value = openclaw.profile;
  qs('concurrency').value = openclaw.concurrency;
  qs('headless').checked = openclaw.headless;
  qs('timeoutSeconds').value = openclaw.timeoutSeconds;
  qs('retryCount').value = openclaw.retryCount;
  qs('environment').value = openclaw.environment;
  qs('extraArgs').value = openclaw.extraArgs;
  qs('lobster-command').value = lobster.command;
  qs('lobster-workspace').value = lobster.workspace;
  qs('lobster-queue').value = lobster.defaultQueue;
  qs('lobster-dryrun').checked = lobster.dryRun;
  qs('telegram-token').value = notifications.telegramBotToken;
  qs('telegram-chat').value = notifications.telegramChatId;
  qs('discord-webhook').value = notifications.discordWebhookUrl;
}

async function loadConfig() {
  const config = await fetchJson('/api/config');
  hydrateConfig(config);
  qs('config-status').textContent = '設定已載入';
  await applyOpenClawSettings();
}

async function applyOpenClawSettings() {
  const result = await fetchJson('/api/openclaw/apply', {
    method: 'POST',
    body: JSON.stringify(getConfigPayload().openclaw),
  });
  qs('openclaw-preview').textContent = result.preview;
}

async function saveAllConfig() {
  const config = getConfigPayload();
  await fetchJson('/api/config', {
    method: 'POST',
    body: JSON.stringify(config),
  });
  qs('config-status').textContent = '設定已儲存';
  await applyOpenClawSettings();
}

async function loadHistory() {
  const history = await fetchJson('/api/tasks');
  const root = qs('history');
  root.innerHTML = '';
  if (!history.length) {
    root.innerHTML = '<div class="history-item"><p>目前還沒有派發紀錄。</p></div>';
    return;
  }
  for (const item of history) {
    const el = document.createElement('article');
    el.className = 'history-item';
    el.innerHTML = `
      <h3>${item.name}</h3>
      <p>Queue: ${item.queue} · Target: ${item.target}</p>
      <p>Status: ${item.ok ? 'ok' : 'failed'} · Command: ${item.command.join(' ')}</p>
      <p>${item.stdout || item.stderr || ''}</p>
    `;
    root.appendChild(el);
  }
}

async function dispatchTask() {
  const result = await fetchJson('/api/tasks/dispatch', {
    method: 'POST',
    body: JSON.stringify({
      name: qs('task-name').value,
      queue: qs('task-queue').value,
      target: qs('task-target').value,
      channel: qs('task-channel').value,
      parameters: JSON.parse(qs('task-parameters').value || '{}'),
    }),
  });
  qs('dispatch-result').textContent = JSON.stringify(result, null, 2);
  await loadHistory();
}

qs('save-openclaw').addEventListener('click', applyOpenClawSettings);
qs('save-config').addEventListener('click', saveAllConfig);
qs('dispatch-task').addEventListener('click', dispatchTask);
qs('refresh-history').addEventListener('click', loadHistory);

loadConfig().then(loadHistory);
