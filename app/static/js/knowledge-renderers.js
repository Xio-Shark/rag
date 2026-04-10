import { documentState, escapeHtml, formatMetricValue } from "./shared.js";

export function renderAnswer(payload) {
  const container = document.getElementById("answer");
  const citations = (payload.citations || [])
    .map(
      (citation) => `
        <div class="citation">
          <strong>${escapeHtml(citation.document_title)}</strong>
          <div class="muted">${escapeHtml(citation.title_path || "无标题路径")} | 分数 ${formatMetricValue(citation.score)}</div>
          <div>${escapeHtml(citation.snippet)}</div>
        </div>
      `
    )
    .join("");
  container.innerHTML = `
    <p><strong>回答：</strong>${escapeHtml(payload.answer || "空")}</p>
    <p><strong>拒答原因：</strong>${escapeHtml(payload.refusal_reason || "无")}</p>
    <p><strong>证据置信度：</strong>${formatMetricValue(payload.confidence)}</p>
    <p><strong>审计 ID：</strong>${escapeHtml(payload.audit_id)}</p>
    <div class="citations">${citations || "<div class='muted'>无引用</div>"}</div>
  `;
}

export function renderDocuments(payload) {
  const container = document.getElementById("documents-output");
  const items = payload.items || [];
  if (!items.length) {
    container.innerHTML = "暂无文档";
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <div class="list-item">
          <button
            class="case-button"
            data-document-id="${item.document_id}"
            type="button"
          >
            ${item.title || item.source_path.split("/").pop()}
          </button>
          <div class="muted">${item.file_type} | chunk ${item.chunk_count} | chars ${item.content_chars}</div>
          <div class="muted">${item.source_path}</div>
        </div>
      `
    )
    .join("");
}

export function renderAuditDetail(payload) {
  const container = document.getElementById("audit-output");
  const retrieved = (payload.retrieved_chunks || [])
    .slice(0, 5)
    .map(
      (item) => `
        <div class="list-item">
          <button
            class="case-button"
            data-chunk-id="${item.chunk_id}"
            type="button"
          >
            ${item.document_title}
          </button>
          <div class="metric-note">${item.title_path || "无标题路径"} | 分数 ${item.score}</div>
          <div class="metric-note">${item.snippet}</div>
        </div>
      `
    )
    .join("");
  container.innerHTML = `
    <div class="panel-stack">
      <div>
        <strong>${payload.query}</strong>
        <div class="metric-note">审计 ID：${payload.audit_id}</div>
      </div>
      <div class="metric-grid">
        <div class="metric-card">
          <strong>证据置信度</strong>
          <div class="metric-value">${formatMetricValue(payload.confidence)}</div>
        </div>
        <div class="metric-card">
          <strong>延迟</strong>
          <div class="metric-value">${formatMetricValue(payload.latency_ms)} ms</div>
        </div>
        <div class="metric-card">
          <strong>Token</strong>
          <div class="metric-value">${formatMetricValue(payload.token_usage)}</div>
        </div>
        <div class="metric-card">
          <strong>失败阶段</strong>
          <div class="metric-value">${payload.failure_stage || "无"}</div>
        </div>
      </div>
      <div class="snapshot-card">
        <strong>运行元数据</strong>
        <div class="metric-note">prompt_version：${payload.prompt_version}</div>
        <div class="metric-note">generator：${payload.generator_model}</div>
        <div class="metric-note">embedding：${payload.embedding_model}</div>
        <div class="metric-note">top_k：${payload.top_k} | chunk_size：${payload.chunk_size}</div>
        <div class="metric-note">
          context_char_count：${payload.context_char_count} | cost：${payload.cost}
        </div>
      </div>
      <div class="snapshot-card">
        <strong>回答结果</strong>
        <div class="metric-note">拒答原因：${payload.refusal_reason || "无"}</div>
        <pre>${payload.answer || "空"}</pre>
      </div>
      <div class="snapshot-card">
        <strong>检索候选</strong>
        ${retrieved || '<div class="metric-note">无检索候选</div>'}
      </div>
    </div>
  `;
}

export function renderChunkDetail(payload) {
  const container = document.getElementById("chunk-output");
  const neighbors = (payload.neighbors || [])
    .map(
      (item) => `
        <div class="neighbor-item ${item.is_target ? "target" : ""}">
          <strong>块 ${item.sequence}${item.is_target ? " · 当前命中" : ""}</strong>
          <div class="metric-note">${item.title_path || "无标题路径"}</div>
          <div class="metric-note">${item.snippet}</div>
        </div>
      `
    )
    .join("");
  container.innerHTML = `
    <div class="panel-stack">
      <div>
        <button
          class="case-button"
          data-document-id="${payload.document_id}"
          data-focus-chunk-id="${payload.chunk_id}"
          type="button"
        >
          ${payload.document_title}
        </button>
        <div class="metric-note">${payload.source_path}</div>
        <div class="metric-note">序号 ${payload.sequence} | ${payload.title_path || "无标题路径"}</div>
      </div>
      <div class="snapshot-card">
        <strong>当前片段正文</strong>
        <pre>${payload.text}</pre>
      </div>
      <div class="snapshot-card">
        <strong>相邻上下文</strong>
        <div class="neighbor-list">${neighbors || '<div class="metric-note">无相邻片段</div>'}</div>
      </div>
    </div>
  `;
}

export function renderDocumentDetail(payload, focusChunkId = "") {
  const container = document.getElementById("document-output");
  documentState.payload = payload;
  documentState.focusChunkId = focusChunkId;
  const filterText = document.getElementById("document-filter-input").value.trim();
  documentState.filterText = filterText;
  const chunks = (payload.chunks || [])
    .map((item) => {
      const searchText = `${item.title_path || ""}\n${item.snippet}`.toLowerCase();
      const matched = !filterText || searchText.includes(filterText.toLowerCase());
      return `
        <div class="document-chunk ${item.chunk_id === focusChunkId ? "focused" : ""} ${matched ? "" : "hidden"}">
          <button
            class="case-button"
            data-chunk-id="${item.chunk_id}"
            type="button"
          >
            块 ${item.sequence}${item.chunk_id === focusChunkId ? " · 当前定位" : ""}
          </button>
          <div class="metric-note">${item.title_path || "无标题路径"} | chars ${item.char_count}</div>
          <div class="metric-note">${item.snippet}</div>
          ${matched && filterText ? `<div class="match-chip">命中：${filterText}</div>` : ""}
        </div>
      `;
    })
    .join("");
  const visibleCount = (payload.chunks || []).filter((item) => {
    const searchText = `${item.title_path || ""}\n${item.snippet}`.toLowerCase();
    return !filterText || searchText.includes(filterText.toLowerCase());
  }).length;
  container.innerHTML = `
    <div class="panel-stack">
      <div>
        <strong>${payload.title}</strong>
        <div class="metric-note">${payload.source_path}</div>
        <div class="metric-note">${payload.file_type} | chunk ${payload.chunk_count} | chars ${payload.content_chars}</div>
        <div class="metric-note">当前显示 ${visibleCount} / ${payload.chunks.length} 个 chunk</div>
      </div>
      <div class="snapshot-card">
        <strong>分块时间线</strong>
        <div class="document-chunk-list">
          ${chunks || '<div class="metric-note">当前文档没有 chunk</div>'}
        </div>
      </div>
    </div>
  `;
}

export function renderAuditRuns(payload) {
  const container = document.getElementById("audit-list-output");
  const items = payload.items || [];
  if (!items.length) {
    container.innerHTML = "暂无问答记录";
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <div class="list-item">
          <button
            class="case-button"
            data-audit-id="${item.audit_id}"
            type="button"
          >
            ${item.query}
          </button>
          <div class="metric-note">
            ${item.audit_id.slice(0, 8)} | 置信度 ${formatMetricValue(item.confidence)}
          </div>
          <div class="metric-note">
            拒答 ${item.refusal_reason || "无"} | 失败阶段 ${item.failure_stage || "无"}
          </div>
        </div>
      `
    )
    .join("");
}
