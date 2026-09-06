const $ = (selector) => document.querySelector(selector);
const compactFormat = new Intl.NumberFormat("zh-CN", { notation: "compact", maximumFractionDigits: 1 });
const exactFormat = new Intl.NumberFormat("zh-CN");
let agentRuns = [];
let selectedRunId = null;

const COMPONENT_LABELS = {
  base_system: "基础指令", system: "System（合并）", context: "工作区 Context",
  ephemeral_context: "临时 Context", skills: "Skills", memory: "Memory / User profile", volatile: "Skills / Memory（合并）",
  runtime: "运行信息", user_messages: "User 消息", assistant_history: "Assistant 历史",
  tool_results: "Tool 结果", other_history: "其他历史", tool_schema: "Tool schemas",
  mcp_schema: "MCP schemas", unattributed: "未归因差额",
};

function n(value) { return Number(value || 0); }
function number(value) { return exactFormat.format(n(value)); }
function token(value) { return value == null ? "—" : number(value); }
function compact(value) { return compactFormat.format(n(value)); }
function dateTime(value) { return new Date(value).toLocaleString("zh-CN", { hour12: false }); }
function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({"&":"&amp;","<":"&lt;",">":"&gt;","'":"&#39;",'"':"&quot;"}[char]));
}
function emptyRow(columns, text) { return `<tr><td colspan="${columns}" class="empty">${text}</td></tr>`; }
function cacheRatio(item) { return n(item.prompt_tokens) ? n(item.cache_read_tokens) / n(item.prompt_tokens) : 0; }

function renderCards(totals) {
  const prompt = n(totals.input_tokens) + n(totals.cache_read_tokens) + n(totals.cache_write_tokens);
  const items = [
    ["模型调用", number(totals.calls), `${number(totals.error_calls)} errors · ${number(totals.retried_attempts)} retries`],
    ["Prompt tokens", compact(prompt), `${number(totals.input_tokens)} 未缓存`],
    ["缓存命中率", totals.cache_read_ratio == null ? "—" : `${(totals.cache_read_ratio * 100).toFixed(1)}%`, `${compact(totals.cache_read_tokens)} cache read`],
    ["Output tokens", compact(totals.output_tokens), `${number(totals.reasoning_tokens)} reasoning`],
  ];
  $("#cards").innerHTML = items.map(([label, value, note]) =>
    `<article class="card"><p>${label}</p><strong>${value}</strong><span>${note}</span></article>`
  ).join("");
}

function renderTokens(totals) {
  const tokens = [
    ["未缓存 Input", n(totals.input_tokens), "input"], ["Cache read", n(totals.cache_read_tokens), "read"],
    ["Cache write", n(totals.cache_write_tokens), "write"], ["Output", n(totals.output_tokens), "output"],
  ];
  const sum = tokens.reduce((total, item) => total + item[1], 0) || 1;
  let offset = 0;
  const segments = tokens.filter((item) => item[1] > 0).map(([label, value, kind]) => {
    const width = value / sum * 100;
    const segment = `<rect class="${kind}" x="${offset}" y="0" width="${width}" height="12"><title>${label}: ${number(value)}</title></rect>`;
    offset += width;
    return segment;
  }).join("");
  $("#token-bar").innerHTML = `<svg viewBox="0 0 100 12" preserveAspectRatio="none" role="img">${segments}</svg>`;
  $("#token-legend").innerHTML = tokens.map(([label, value, kind]) =>
    `<span><i class="${kind}"></i>${label} <b>${number(value)}</b></span>`
  ).join("");
}

function renderModels(models) {
  $("#models").innerHTML = models.length ? models.map((item) => {
    const prompt = n(item.input_tokens) + n(item.cache_read_tokens) + n(item.cache_write_tokens);
    const ratio = prompt ? n(item.cache_read_tokens) / prompt : 0;
    return `<tr><td><b>${escapeHtml(item.provider)}</b><small>${escapeHtml(item.model)}</small></td>
      <td>${number(item.calls)}</td><td>${number(prompt)}</td><td>${number(item.input_tokens)}</td>
      <td>${number(item.cache_read_tokens)}</td><td>${(ratio * 100).toFixed(1)}%</td>
      <td>${number(item.output_tokens)}</td><td class="${item.errors ? "bad" : "good"}">${number(item.errors)}</td></tr>`;
  }).join("") : emptyRow(8, "该时间范围没有模型调用");
}

function componentSummary(components) {
  const groups = new Map();
  for (const item of components || []) {
    const type = item.type || "unknown";
    const current = groups.get(type) || { type, estimated_tokens: 0, chars: 0, items: 0 };
    current.estimated_tokens += n(item.estimated_tokens);
    current.chars += n(item.chars);
    current.items += n(item.items);
    groups.set(type, current);
  }
  return [...groups.values()].sort((a, b) => b.estimated_tokens - a.estimated_tokens);
}

function renderComponentBreakdown(attempt) {
  const groups = componentSummary(attempt.components);
  if (!groups.length) return `<p class="empty compact-empty">暂无组件数据</p>`;
  const maximum = Math.max(...groups.map((item) => item.estimated_tokens), 1);
  const rows = groups.map((item) => {
    const schema = item.type === "tool_schema" || item.type === "mcp_schema";
    const note = item.type === "unattributed" ? "精确总量减本地可见估算"
      : schema ? `${number(item.items)} definitions` : `${compact(item.chars)} chars`;
    return `<div class="component-row"><span>${escapeHtml(COMPONENT_LABELS[item.type] || item.type)}</span>
      <progress max="${maximum}" value="${item.estimated_tokens}"></progress>
      <b>≈ ${number(item.estimated_tokens)}</b><small>${note}</small></div>`;
  }).join("");
  const schemas = (attempt.components || []).filter((item) =>
    (item.type === "tool_schema" || item.type === "mcp_schema") && item.name && item.name !== "combined"
  );
  const detail = schemas.length ? `<details class="schema-detail"><summary>查看 ${number(schemas.length)} 个 Tool / MCP schema</summary>
    <div>${schemas.map((item) => `<span><b>${escapeHtml(item.name)}</b><small>≈ ${number(item.estimated_tokens)} tokens</small></span>`).join("")}</div></details>` : "";
  return `<div class="component-list">${rows}</div>${detail}`;
}

function renderToolCalls(attempt) {
  if (!(attempt.tools || []).length) {
    return `<div class="loop-tools"><p class="label">本 Loop 工具调用</p><span class="muted">无</span></div>`;
  }
  return `<div class="loop-tools"><p class="label">本 Loop 工具调用</p><div>${attempt.tools.map((item) =>
    `<span class="tool-chip"><i>${item.kind === "mcp" ? "MCP" : "TOOL"}</i>${escapeHtml(item.tool_name)}<b>× ${number(item.calls)}</b></span>`
  ).join("")}</div></div>`;
}

function renderAttempt(attempt) {
  const status = escapeHtml(attempt.status || "unknown");
  const loop = attempt.api_call_count == null ? "—" : number(attempt.api_call_count);
  return `<article class="loop-card"><header><div><p class="label">Loop ${loop} · Attempt ${number(attempt.attempt_index)}</p>
      <h4>${escapeHtml(attempt.provider)} <span>${escapeHtml(attempt.model)}</span></h4></div>
      <span class="status ${status}">${status}</span></header>
    <div class="loop-metrics"><span><small>Prompt</small><b>${token(attempt.prompt_tokens)}</b></span>
      <span><small>未缓存</small><b>${token(attempt.input_tokens)}</b></span>
      <span><small>Cache read</small><b>${token(attempt.cache_read_tokens)}</b></span>
      <span><small>命中率</small><b>${(cacheRatio(attempt) * 100).toFixed(1)}%</b></span>
      <span><small>Output</small><b>${token(attempt.output_tokens)}</b></span></div>
    <div class="loop-body"><div><p class="label">Prompt 组件（Token 估算）</p>${renderComponentBreakdown(attempt)}</div>
      ${renderToolCalls(attempt)}</div></article>`;
}

function renderRunDetail(run) {
  if (!run) {
    $("#run-detail").innerHTML = `<p class="empty">选择一行，查看逐 Loop 的 Token 构成和工具调用次数。</p>`;
    return;
  }
  $("#run-detail").innerHTML = `<div class="run-detail-head"><div><p class="label">匿名执行 ${escapeHtml(run.run_id.slice(0, 8))}</p>
      <h3>${dateTime(run.started_at_iso)}</h3></div><p>${number(run.loop_count)} loops · ${number(run.attempt_count)} API attempts</p></div>
    <div class="loop-stack">${run.attempts.map(renderAttempt).join("")}</div>
    <p class="footnote">Prompt/Cache/Output 来自 Provider；组件 Token 由本地字符规模估算，不保存 Prompt、Tool 参数或返回正文。</p>`;
}

function renderRuns(runs) {
  agentRuns = runs;
  if (selectedRunId && !runs.some((run) => run.run_id === selectedRunId)) selectedRunId = null;
  $("#runs").innerHTML = runs.length ? runs.map((run) => {
    const selected = run.run_id === selectedRunId;
    const ratio = run.totals.prompt_tokens ? run.totals.cache_read_tokens / run.totals.prompt_tokens : 0;
    return `<tr class="${selected ? "selected" : ""}"><td><button class="run-open" type="button" data-run-id="${escapeHtml(run.run_id)}" aria-expanded="${selected}">${dateTime(run.started_at_iso)}<small>Run ${escapeHtml(run.run_id.slice(0, 8))}</small></button></td>
      <td>${escapeHtml(run.platform)}</td><td>${number(run.loop_count)}</td><td>${number(run.attempt_count)}</td>
      <td>${number(run.totals.prompt_tokens)}</td><td>${(ratio * 100).toFixed(1)}%</td><td>${number(run.totals.output_tokens)}</td></tr>`;
  }).join("") : emptyRow(7, "该时间范围没有 Agent 执行");
  renderRunDetail(runs.find((run) => run.run_id === selectedRunId));
}

async function load() {
  const days = $("#days").value;
  $("#notice").className = "notice loading";
  $("#notice").textContent = "正在读取指标…";
  $("#refresh").disabled = true;
  try {
    const [reportResponse, runsResponse] = await Promise.all([
      fetch(`/api/report?days=${days}`), fetch(`/api/runs?days=${days}&limit=50`),
    ]);
    if (!reportResponse.ok || !runsResponse.ok) throw new Error("Viewer API unavailable");
    const report = await reportResponse.json();
    const runs = await runsResponse.json();
    renderCards(report.totals); renderTokens(report.totals); renderModels(report.models); renderRuns(runs.items);
    $("#coverage").textContent = `主模型逐 API attempt · 辅助模型聚合 ${number(report.auxiliary_totals.calls)} calls`;
    $("#updated").textContent = `更新于 ${new Date().toLocaleTimeString("zh-CN", { hour12: false })}`;
    $("#notice").className = "notice ready";
    $("#notice").textContent = `已加载最近 ${days} 天的数据`;
  } catch (error) {
    $("#notice").className = "notice error";
    $("#notice").textContent = "无法读取观测数据，请检查 Viewer 服务和数据库。";
  } finally { $("#refresh").disabled = false; }
}

$("#refresh").addEventListener("click", load);
$("#days").addEventListener("change", load);
$("#runs").addEventListener("click", (event) => {
  const button = event.target.closest(".run-open");
  if (!button) return;
  selectedRunId = button.dataset.runId;
  renderRuns(agentRuns);
});
load();
setInterval(load, 30000);
