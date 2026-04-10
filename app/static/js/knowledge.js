import { documentState, requestJson, setMessage } from "./shared.js";
import {
  renderAnswer,
  renderAuditDetail,
  renderAuditRuns,
  renderChunkDetail,
  renderDocumentDetail,
  renderDocuments,
} from "./renderers.js";

function syncDocumentFilterFromQuery(query) {
  if (!query) {
    return;
  }
  document.getElementById("document-filter-input").value = query;
  documentState.filterText = query;
}

export async function loadDocumentDetail(documentId, focusChunkId = "") {
  if (!documentId) {
    setMessage("document-output", "请先选择文档", true);
    return;
  }
  setMessage("document-output", "加载文档中...");
  const payload = await requestJson(`/v1/documents/${encodeURIComponent(documentId)}`);
  renderDocumentDetail(payload, focusChunkId);
}

export async function loadChunkDetail(chunkId) {
  if (!chunkId) {
    setMessage("chunk-output", "请先选择证据片段", true);
    return;
  }
  setMessage("chunk-output", "加载证据片段中...");
  const payload = await requestJson(`/v1/documents/chunks/${encodeURIComponent(chunkId)}?window=1`);
  renderChunkDetail(payload);
  await loadDocumentDetail(payload.document_id, payload.chunk_id);
}

export async function loadAuditDetail(auditId) {
  if (!auditId) {
    setMessage("audit-output", "请先输入审计 ID", true);
    return;
  }
  setMessage("audit-output", "查询中...");
  const payload = await requestJson(`/v1/qa/runs/${encodeURIComponent(auditId)}`);
  document.getElementById("audit-id-input").value = auditId;
  renderAuditDetail(payload);
  syncDocumentFilterFromQuery(payload.query);
  const firstChunkId = payload.retrieved_chunks?.[0]?.chunk_id;
  if (firstChunkId) {
    await loadChunkDetail(firstChunkId);
  }
}

export async function refreshAuditRuns() {
  const payload = await requestJson("/v1/qa/runs?limit=10");
  renderAuditRuns(payload);
}

export async function refreshDocuments() {
  const payload = await requestJson("/v1/documents?limit=20");
  renderDocuments(payload);
}

export function bindKnowledgeHandlers() {
  document.getElementById("ask-button").addEventListener("click", async () => {
    const query = document.getElementById("query").value.trim();
    const container = document.getElementById("answer");
    if (!query) {
      container.innerHTML = "请输入问题";
      return;
    }
    container.innerHTML = "请求中...";
    try {
      const payload = await requestJson("/v1/qa/ask", {
        method: "POST",
        body: JSON.stringify({ query, top_k: 3 }),
      });
      renderAnswer(payload);
      await loadAuditDetail(payload.audit_id);
    } catch (error) {
      container.innerHTML = `<span class="error">${error.message}</span>`;
    }
  });

  document.getElementById("audit-button").addEventListener("click", async () => {
    const auditId = document.getElementById("audit-id-input").value.trim();
    try {
      await loadAuditDetail(auditId);
    } catch (error) {
      setMessage("audit-output", error.message, true);
    }
  });

  document.getElementById("audit-runs-button").addEventListener("click", async () => {
    try {
      await refreshAuditRuns();
    } catch (error) {
      setMessage("audit-list-output", error.message, true);
    }
  });

  document.getElementById("import-button").addEventListener("click", async () => {
    const sourceDir = document.getElementById("import-dir").value.trim() || ".";
    setMessage("import-status", "导入中...");
    try {
      const payload = await requestJson("/v1/documents/import", {
        method: "POST",
        body: JSON.stringify({ source_dir: sourceDir }),
      });
      setMessage(
        "import-status",
        `完成：imported=${payload.imported_count}, skipped=${payload.skipped_count}, chunks=${payload.chunk_count}`
      );
      await refreshDocuments();
    } catch (error) {
      setMessage("import-status", error.message, true);
    }
  });

  document.getElementById("documents-button").addEventListener("click", async () => {
    try {
      await refreshDocuments();
    } catch (error) {
      setMessage("import-status", error.message, true);
    }
  });

  document.getElementById("health-button").addEventListener("click", async () => {
    try {
      const payload = await requestJson("/v1/health");
      document.getElementById("health-output").textContent = JSON.stringify(payload, null, 2);
    } catch (error) {
      document.getElementById("health-output").textContent = error.message;
    }
  });

  document.getElementById("audit-list-output").addEventListener("click", async (event) => {
    const button = event.target.closest(".case-button");
    if (!button || !button.dataset.auditId) {
      return;
    }
    try {
      await loadAuditDetail(button.dataset.auditId);
    } catch (error) {
      setMessage("audit-output", error.message, true);
    }
  });

  document.getElementById("audit-output").addEventListener("click", async (event) => {
    const button = event.target.closest(".case-button");
    if (!button || !button.dataset.chunkId) {
      if (button?.dataset.documentId) {
        try {
          await loadDocumentDetail(button.dataset.documentId, button.dataset.focusChunkId || "");
        } catch (error) {
          setMessage("document-output", error.message, true);
        }
      }
      return;
    }
    try {
      await loadChunkDetail(button.dataset.chunkId);
    } catch (error) {
      setMessage("chunk-output", error.message, true);
    }
  });

  document.getElementById("chunk-output").addEventListener("click", async (event) => {
    const button = event.target.closest(".case-button");
    if (!button || !button.dataset.documentId) {
      return;
    }
    try {
      await loadDocumentDetail(button.dataset.documentId, button.dataset.focusChunkId || "");
    } catch (error) {
      setMessage("document-output", error.message, true);
    }
  });

  document.getElementById("documents-output").addEventListener("click", async (event) => {
    const button = event.target.closest(".case-button");
    if (!button || !button.dataset.documentId) {
      return;
    }
    try {
      await loadDocumentDetail(button.dataset.documentId);
    } catch (error) {
      setMessage("document-output", error.message, true);
    }
  });

  document.getElementById("document-output").addEventListener("click", async (event) => {
    const button = event.target.closest(".case-button");
    if (!button || !button.dataset.chunkId) {
      return;
    }
    try {
      await loadChunkDetail(button.dataset.chunkId);
    } catch (error) {
      setMessage("chunk-output", error.message, true);
    }
  });

  document.getElementById("document-filter-input").addEventListener("input", () => {
    if (!documentState.payload) {
      return;
    }
    renderDocumentDetail(documentState.payload, documentState.focusChunkId);
  });
}
