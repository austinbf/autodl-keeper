const apiBase = location.protocol === "chrome-extension:" ? "http://127.0.0.1:8765" : "";
const byId = (id) => document.getElementById(id);
if (apiBase) {
  document.body.classList.add("extension-popup");
  byId("brand-icon").src = "icons/icon-48.png";
  byId("brand-icon").hidden = false;
}
const token = byId("token");
const list = byId("list");
const message = byId("message");
let configured = false;
let localAuto = true;
let loadedSettings = false;
let instancesLoaded = false;
let instanceError = "";
let busy = false;
let pending = false;
let loading = false;
let credentialRevision = 0;
let nextAt = null;
let completedAt = null;
let items = [];
let renderedHealth = "";
let showingRunningLog = false;

const checked = () => [...list.querySelectorAll("input:checked")].map((item) => item.value);
const stamp = (n) => new Date(n * 1000).toLocaleString("zh-CN");

function updateButtons() {
  token.placeholder = configured ? "••••••••••••••••" : "粘贴 AutoDL 网页令牌";
  const savedState = configured ? "令牌已加密保存，刷新后仍可使用。"
    : loadedSettings ? "尚未保存令牌" : "正在读取令牌状态…";
  if (byId("configured").textContent !== savedState) byId("configured").textContent = savedState;
  byId("save").disabled = pending || busy || (!configured && !token.value.trim());
  byId("load").disabled = pending || loading || busy || !configured;
  byId("forget").disabled = pending || busy || !configured;
  byId("run").disabled = pending || busy || !configured || !checked().length;
}

async function request(path, body) {
  let response;
  try {
    response = await fetch(apiBase + path, {
      signal: AbortSignal.timeout(45000),
      ...(body ? {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(body)
      } : {})
    });
  } catch (error) {
    throw new Error(error.name === "TimeoutError"
      ? "请求超时，请检查网络后重试。"
      : "无法连接本机服务，请启动 keeper_web.py 后重试。");
  }
  const data = await response.json();
  if (!response.ok) throw new Error(data.error);
  return data;
}

function showInstanceStatus() {
  const status = byId("instance-status");
  const text = loading ? "正在查询 AutoDL 实例…"
    : instanceError || (instancesLoaded ? (items.length ? "" : "未找到实例。")
      : configured ? "等待查询实例…" : loadedSettings ? "在左下角设置中保存令牌。" : "正在读取设置…");
  if (status.textContent !== text) status.textContent = text;
  status.hidden = !text;
}

function renderInstances(force = false) {
  const now = Date.now() / 1000;
  const urgent = (item) => item.deadline != null && item.deadline - now <= 3 * 86400;
  const signature = items.map((item) => urgent(item)).join(",");
  if (!force && signature === renderedHealth) return;
  renderedHealth = signature;
  const selected = new Set(checked());
  list.replaceChildren();
  for (const item of items) {
    const label = document.createElement("label");
    label.className = urgent(item) ? "instance expiring" : "instance";
    const input = document.createElement("input");
    input.type = "checkbox";
    input.value = item.uuid;
    input.disabled = item.status !== "shutdown";
    input.checked = !input.disabled && selected.has(item.uuid);
    const details = document.createElement("div");
    const title = document.createElement("div");
    const status = {shutdown: "已关机", running: "运行中", starting: "启动中", shutting_down: "关机中"}[item.status] ?? item.status;
    title.textContent = `${item.uuid} · ${status}`;
    const info = document.createElement("small");
    const disk = item.disk_health === "normal" ? "磁盘健康" : item.disk_health ? `磁盘状态 ${item.disk_health}` : "磁盘健康未知";
    const expiry = item.deadline == null ? "暂无到期时间" : `${item.deadline_reason} ${stamp(item.deadline)}`;
    info.textContent = [item.sub_status, disk, urgent(item) ? (item.deadline <= now ? "已到期" : "三天内到期") : "", expiry].filter(Boolean).join(" · ");
    info.className = urgent(item) ? "danger" : item.disk_health === "normal" ? "healthy" : "";
    details.append(title, info);
    label.append(input, details);
    list.append(label);
  }
  showInstanceStatus();
  updateButtons();
}

async function action(callback) {
  pending = true;
  message.textContent = "";
  updateButtons();
  try {
    await callback();
  } catch (error) {
    message.textContent = error.message;
  } finally {
    pending = false;
    updateButtons();
  }
}

async function loadInstances() {
  if (loading || pending) return;
  loading = true;
  instanceError = "";
  showInstanceStatus();
  const revision = credentialRevision;
  updateButtons();
  try {
    const data = await request("/api/list", {});
    if (revision !== credentialRevision) return;
    items = data.instances;
    instancesLoaded = true;
    renderInstances(true);
  } catch (error) {
    if (revision === credentialRevision) instanceError = error.message;
  } finally {
    loading = false;
    showInstanceStatus();
    updateButtons();
  }
}

function showSettings(open) {
  byId("dashboard").hidden = open;
  byId("settings").hidden = !open;
  byId("settings-toggle").setAttribute("aria-expanded", String(open));
  byId("settings-toggle").textContent = open ? "返回" : "设置";
  (open ? byId("settings-title") : byId("settings-toggle")).focus();
}

byId("settings-toggle").addEventListener("click", () => showSettings(byId("settings").hidden));
for (const event of ["input", "change"]) token.addEventListener(event, updateButtons);
list.addEventListener("change", updateButtons);
function saveSettings() {
  if (byId("save").disabled) return;
  action(async () => {
    credentialRevision += 1;
    const data = await request("/api/configure", {token: token.value.trim(), local_auto: byId("local-auto").checked});
    configured = true;
    localAuto = data.local_auto;
    if (!localAuto) nextAt = null;
    token.value = "";
    items = data.instances;
    instancesLoaded = true;
    instanceError = "";
    renderInstances(true);
    message.textContent = "设置已保存。";
  });
}
byId("save").addEventListener("click", saveSettings);
token.addEventListener("keydown", (event) => {
  if (event.key === "Enter") saveSettings();
});
byId("load").addEventListener("click", loadInstances);
byId("forget").addEventListener("click", () => action(async () => {
  credentialRevision += 1;
  await request("/api/forget", {});
  configured = false;
  nextAt = null;
  items = [];
  instancesLoaded = false;
  instanceError = "";
  renderInstances(true);
  message.textContent = "已停用自动保活并清除已保存的令牌。";
}));
byId("run").addEventListener("click", () => {
  const uuids = checked();
  byId("run-confirmation").hidden = false;
  byId("run-summary").textContent = `按列表顺序无卡开关机 ${uuids.length} 台？`;
  byId("confirm-run").focus();
});
byId("cancel-run").addEventListener("click", () => {
  byId("run-confirmation").hidden = true;
  byId("run").focus();
});
byId("confirm-run").addEventListener("click", () => {
  const uuids = checked();
  byId("run-confirmation").hidden = true;
  if (!uuids.length || busy || pending) return;
  action(async () => {
    await request("/api/run", {uuids});
    busy = true;
  });
});

function updateCountdown() {
  if (!nextAt || !localAuto) {
    byId("countdown").textContent = configured && !localAuto ? "本机自动保活已关闭" : "保存令牌后安排首次执行";
    return;
  }
  const seconds = Math.max(0, Math.ceil(nextAt - Date.now() / 1000));
  const number = (x) => String(x).padStart(2, "0");
  const remaining = seconds ? `${Math.floor(seconds / 86400)} 天 ${number(Math.floor(seconds / 3600) % 24)}:${number(Math.floor(seconds / 60) % 60)}:${number(seconds % 60)}` : "等待本机服务执行";
  byId("countdown").textContent = `下次 ${stamp(nextAt)} · ${remaining}`;
}

async function refresh() {
  try {
    const job = await request("/api/status");
    const refreshList = job.configured && (!configured || job.completed_at !== completedAt);
    configured = job.configured;
    busy = job.state === "running";
    nextAt = job.next_at;
    localAuto = job.local_auto ?? true;
    if (!loadedSettings) {
      byId("local-auto").checked = localAuto;
      loadedSettings = true;
    }
    completedAt = job.completed_at;
    const states = {idle: "等待运行", running: "批次运行中", done: "全部完成", failed: "批次失败"};
    byId("state").textContent = states[job.state];
    byId("last").textContent = job.last_state ? `上次自动批次 · ${states[job.last_state]}` : "";
    const logs = job.events.length || busy ? job.events : job.last_events;
    const details = byId("log-details");
    details.hidden = !busy && !logs.length;
    if (busy !== showingRunningLog) {
      details.open = busy;
      showingRunningLog = busy;
    }
    byId("events").replaceChildren(...logs.map((entry) => {
      const line = document.createElement("li");
      line.textContent = entry;
      return line;
    }));
    updateButtons();
    updateCountdown();
    showInstanceStatus();
    if (refreshList && !busy) void loadInstances();
  } catch {
    const problem = "无法连接本机服务，请运行 keeper_web.py。";
    byId("state").textContent = problem;
    if (!loadedSettings) byId("configured").textContent = problem;
  } finally {
    setTimeout(refresh, 1500);
  }
}

updateButtons();
setInterval(() => { updateCountdown(); renderInstances(); }, 1000);
setInterval(() => { if (configured && !busy) void loadInstances(); }, 300000);
refresh();
