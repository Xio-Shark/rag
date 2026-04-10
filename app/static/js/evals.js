import { compareState, fillOptions, requestJson, setMessage } from "./shared.js";
import { syncReportPanel } from "./report.js";
import {
  caseGroupLabel,
  extractReportSection,
  findCaseDetail,
  renderCaseDetailBlock,
  renderCompare,
  renderCompareDetailPlaceholder,
  renderEvalSummary,
  renderRunOptions,
  renderRunResult,
  renderRunsList,
  renderSnapshotList,
  updateCaseButtonState,
} from "./renderers.js";

async function hydrateCompareDetails(payload) {
  const [baseRun, targetRun, baseReport, targetReport] = await Promise.all([
    requestJson(`/v1/evals/${encodeURIComponent(payload.base_eval_run_id)}`),
    requestJson(`/v1/evals/${encodeURIComponent(payload.target_eval_run_id)}`),
    requestJson(
      `/v1/evals/${encodeURIComponent(payload.base_eval_run_id)}/report?format=markdown`
    ),
    requestJson(
      `/v1/evals/${encodeURIComponent(payload.target_eval_run_id)}/report?format=markdown`
    ),
  ]);

  compareState.payload = payload;
  compareState.baseRun = baseRun;
  compareState.targetRun = targetRun;
  compareState.baseReport = baseReport;
  compareState.targetReport = targetReport;
  compareState.activeCaseKey = "";
  renderCompareDetailPlaceholder(payload);
}

function focusCompareSection(sectionName) {
  const section = document.querySelector(
    `#compare-output [data-summary-section="${CSS.escape(sectionName)}"]`
  );
  if (!section) {
    return;
  }
  section.scrollIntoView({ behavior: "smooth", block: "start" });
}

function showCompareCaseDetail(groupKey, caseName) {
  if (!compareState.payload) {
    return;
  }
  const container = document.getElementById("compare-detail-output");
  const baseDetail = findCaseDetail(compareState.baseRun, caseName);
  const targetDetail = findCaseDetail(compareState.targetRun, caseName);
  const baseExcerpt = baseDetail
    ? extractReportSection(compareState.baseReport?.content || "", caseName)
    : "";
  const targetExcerpt = targetDetail
    ? extractReportSection(compareState.targetReport?.content || "", caseName)
    : "";

  const blocks = [];
  if (baseDetail) {
    blocks.push(
      renderCaseDetailBlock("基线运行", baseDetail, baseExcerpt, {
        sourceEvalRunId: compareState.payload.base_eval_run_id,
        sourceSnapshotName: compareState.payload.base_snapshot_name,
      })
    );
  }
  if (targetDetail) {
    blocks.push(
      renderCaseDetailBlock("对比运行", targetDetail, targetExcerpt, {
        sourceEvalRunId: compareState.payload.target_eval_run_id,
        sourceSnapshotName: compareState.payload.target_snapshot_name,
      })
    );
  }

  container.innerHTML = `
    <div class="detail-grid">
      <div>
        <strong>${caseName}</strong>
        <div class="metric-note">分组：${caseGroupLabel(groupKey)}</div>
      </div>
      <div class="detail-columns">${blocks.join("")}</div>
    </div>
  `;

  const syncRunId =
    groupKey === "resolved"
      ? compareState.payload.base_eval_run_id
      : compareState.payload.target_eval_run_id;
  const syncPath =
    groupKey === "resolved"
      ? compareState.baseReport?.path || ""
      : compareState.targetReport?.path || "";
  const syncFullContent =
    groupKey === "resolved"
      ? compareState.baseReport?.content || ""
      : compareState.targetReport?.content || "";
  const syncExcerpt = groupKey === "resolved" ? baseExcerpt : targetExcerpt;
  syncReportPanel({
    runId: syncRunId,
    path: syncPath,
    formatName: "markdown",
    fullContent: syncFullContent,
    excerptContent: syncExcerpt,
    caseName,
  });

  compareState.activeCaseKey = `${groupKey}:${caseName}`;
  updateCaseButtonState();
}

export async function refreshDatasetsAndSnapshots() {
  const [datasetsPayload, snapshotsPayload] = await Promise.all([
    requestJson("/v1/evals/datasets"),
    requestJson("/v1/evals/snapshots"),
  ]);

  fillOptions(
    "dataset-select",
    (datasetsPayload.items || []).map((item) => ({ value: item, label: item })),
    (item) => item.label
  );
  fillOptions(
    "snapshot-select",
    (snapshotsPayload.items || []).map((item) => ({
      value: item.name,
      label: `${item.name} | ${item.description || "无描述"}`,
    })),
    (item) => item.label
  );
  fillOptions(
    "replay-snapshot-select",
    (snapshotsPayload.items || []).map((item) => ({
      value: item.name,
      label: `${item.name} | ${item.description || "无描述"}`,
    })),
    (item) => item.label
  );
  renderSnapshotList(snapshotsPayload);
}

export async function refreshRuns() {
  const payload = await requestJson("/v1/evals/runs?limit=20");
  renderRunOptions(payload);
  return payload;
}

export function bindEvaluationHandlers({
  decodeReplaySelection,
  loadAuditDetail,
  replayBadCase,
}) {
  document.getElementById("datasets-button").addEventListener("click", async () => {
    try {
      await refreshDatasetsAndSnapshots();
    } catch (error) {
      setMessage("run-eval-output", error.message, true);
    }
  });

  document.getElementById("run-eval-button").addEventListener("click", async () => {
    const datasetName = document.getElementById("dataset-select").value;
    const snapshotName = document.getElementById("snapshot-select").value;
    if (!datasetName || !snapshotName) {
      setMessage("run-eval-output", "请先选择数据集和快照", true);
      return;
    }
    setMessage("run-eval-output", "评测运行中...");
    try {
      const payload = await requestJson("/v1/evals/run", {
        method: "POST",
        body: JSON.stringify({
          dataset_name: datasetName,
          snapshot_name: snapshotName,
        }),
      });
      renderRunResult(payload);
      await refreshRuns();
    } catch (error) {
      setMessage("run-eval-output", error.message, true);
    }
  });

  document.getElementById("eval-button").addEventListener("click", async () => {
    try {
      const payload = await requestJson("/v1/evals/latest");
      renderEvalSummary(payload);
    } catch (error) {
      document.getElementById("eval-output").textContent = error.message;
    }
  });

  document.getElementById("runs-button").addEventListener("click", async () => {
    try {
      const payload = await refreshRuns();
      renderRunsList(payload);
    } catch (error) {
      document.getElementById("eval-output").textContent = error.message;
    }
  });

  document.getElementById("compare-button").addEventListener("click", async () => {
    const baseId = document.getElementById("base-run-select").value;
    const targetId = document.getElementById("target-run-select").value;
    const container = document.getElementById("compare-output");
    if (!baseId || !targetId) {
      container.innerHTML = "请先选择两次评测运行";
      return;
    }
    if (baseId === targetId) {
      container.innerHTML = "基线运行和对比运行不能相同";
      return;
    }
    container.innerHTML = "请求中...";
    try {
      const payload = await requestJson(
        `/v1/evals/compare?base_eval_run_id=${encodeURIComponent(baseId)}&target_eval_run_id=${encodeURIComponent(targetId)}`
      );
      renderCompare(payload);
      await hydrateCompareDetails(payload);
    } catch (error) {
      container.innerHTML = `<span class="error">${error.message}</span>`;
    }
  });

  document.getElementById("compare-output").addEventListener("click", (event) => {
    const button = event.target.closest(".case-button");
    if (!button) {
      return;
    }
    if (button.dataset.summaryAction === "focus-section" && button.dataset.summaryTarget) {
      focusCompareSection(button.dataset.summaryTarget);
      return;
    }
    if (button.dataset.summaryAction === "focus-case" && button.dataset.caseName) {
      showCompareCaseDetail(button.dataset.caseGroup, button.dataset.caseName);
      return;
    }
    if (!button.dataset.caseName) {
      return;
    }
    showCompareCaseDetail(button.dataset.caseGroup, button.dataset.caseName);
  });

  document.getElementById("compare-detail-output").addEventListener("click", async (event) => {
    const button = event.target.closest(".case-button");
    if (!button) {
      return;
    }
    if (button.dataset.replayQuery) {
      try {
        await replayBadCase({
          loadAuditDetail,
          selection: decodeReplaySelection(button),
        });
      } catch (error) {
        setMessage("replay-output", error.message, true);
      }
      return;
    }
    if (!button.dataset.auditId) {
      return;
    }
    try {
      await loadAuditDetail(button.dataset.auditId);
    } catch (error) {
      setMessage("audit-output", error.message, true);
    }
  });

  document.getElementById("eval-output").addEventListener("click", async (event) => {
    const button = event.target.closest(".case-button");
    if (!button || !button.dataset.replayQuery) {
      return;
    }
    try {
      await replayBadCase({
        loadAuditDetail,
        selection: decodeReplaySelection(button),
      });
    } catch (error) {
      setMessage("replay-output", error.message, true);
    }
  });

  document.getElementById("snapshot-button").addEventListener("click", async () => {
    try {
      await refreshDatasetsAndSnapshots();
    } catch (error) {
      document.getElementById("snapshot-output").innerHTML = error.message;
    }
  });
}
