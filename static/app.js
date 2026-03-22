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
      agentName: qs('agentName').value,
      model: qs('model').value,
      systemPrompt: qs('systemPrompt').value,
      mission: qs('mission').value,
      maxSteps: Number(qs('maxSteps').value),
      memoryWindow: Number(qs('memoryWindow').value),
      headless: qs('headless').checked,
      allowShell: qs('allowShell').checked,
      allowBrowser: qs('allowBrowser').checked,
      workingDirectory: qs('workingDirectory').value,
      extraArgs: qs('extraArgs').value,
      docs: {
        memoryMd: qs('memoryMd').value,
        taskMd: qs('taskMd').value,
        toolsMd: qs('toolsMd').value,
      },
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
  qs('agentName').value = openclaw.agentName;
  qs('model').value = openclaw.model;
  qs('systemPrompt').value = openclaw.systemPrompt;
  qs('mission').value = openclaw.mission;
  qs('maxSteps').value = openclaw.maxSteps;
  qs('memoryWindow').value = openclaw.memoryWindow;
  qs('headless').checked = openclaw.headless;
  qs('allowShell').checked = openclaw.allowShell;
  qs('allowBrowser').checked = openclaw.allowBrowser;
  qs('workingDirectory').value = openclaw.workingDirectory;
  qs('extraArgs').value = openclaw.extraArgs;
  qs('memoryMd').value = openclaw.docs.memoryMd;
  qs('taskMd').value = openclaw.docs.taskMd;
  qs('toolsMd').value = openclaw.docs.toolsMd;
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
      <p>OpenClaw agent: ${item.task.agentName || 'configured agent'} · Queue: ${item.queue}</p>
      <p>Target: ${item.target} · Status: ${item.ok ? 'ok' : 'failed'}</p>
      <p>Mission: ${item.mission}</p>
      <p>Command: ${item.command.join(' ')}</p>
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
      mission: qs('task-mission').value,
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
