import { replayState, requestJson, setMessage } from "./shared.js";
import {
  fillReplayExperimentOptions,
  readReplayControls,
  renderReplayComparison,
  renderReplayContext,
  renderReplayExperimentHistory,
  renderReplayWorkbench,
} from "./renderers.js";

export function decodeReplaySelection(button) {
  return {
    caseName: decodeURIComponent(button.dataset.replayCaseName || ""),
    query: decodeURIComponent(button.dataset.replayQuery || ""),
    originalAnswer: decodeURIComponent(button.dataset.originalAnswer || ""),
    originalRefusal: decodeURIComponent(button.dataset.originalRefusal || ""),
    sourceEvalRunId: decodeURIComponent(button.dataset.sourceEvalRunId || ""),
    sourceSnapshotName: decodeURIComponent(button.dataset.sourceSnapshotName || ""),
  };
}

export async function refreshReplayExperiments(activeQuery = replayState.selectedCase?.query || "") {
  const params = new URLSearchParams({ limit: "20" });
  if (activeQuery) {
    params.set("query", activeQuery);
  }
  const payload = await requestJson(`/v1/evals/replay-experiments?${params.toString()}`);
  replayState.experiments = payload.items || [];
  renderReplayExperimentHistory(replayState.experiments, activeQuery);
  fillReplayExperimentOptions();
}

export async function replayBadCase({ loadAuditDetail, selection = null } = {}) {
  if (selection) {
    replayState.selectedCase = selection;
    document.getElementById("query").value = selection.query || "";
    document.getElementById("replay-top-k-input").value = "";
    document.getElementById("replay-threshold-input").value = "";
    document.getElementById("replay-snapshot-select").value =
      selection.sourceSnapshotName || "default";
    renderReplayContext();
  }
  if (!replayState.selectedCase?.query) {
    setMessage("replay-output", "请先选择一个 bad case 再执行回放", true);
    return;
  }
  const controls = readReplayControls();
  setMessage("replay-output", "回放实验执行中...");
  const replayPayload = await requestJson("/v1/evals/replay-experiments", {
    method: "POST",
    body: JSON.stringify({
      case_name: replayState.selectedCase.caseName,
      query: replayState.selectedCase.query,
      snapshot_name: controls.snapshot_name,
      top_k: controls.top_k,
      retrieval_threshold: controls.retrieval_threshold,
      source_eval_run_id: replayState.selectedCase.sourceEvalRunId || undefined,
      source_snapshot_name: replayState.selectedCase.sourceSnapshotName || undefined,
    }),
  });
  renderReplayWorkbench({
    selectedCase: replayState.selectedCase,
    replayPayload,
  });
  await refreshReplayExperiments(replayState.selectedCase.query);
  if (loadAuditDetail) {
    await loadAuditDetail(replayPayload.audit_id);
  }
}

function focusReplaySection(sectionName) {
  const section = document.querySelector(
    `#replay-compare-output [data-summary-section="${CSS.escape(sectionName)}"]`
  );
  if (!section) {
    return;
  }
  section.scrollIntoView({ behavior: "smooth", block: "start" });
}

function restoreFullReportFromSuggestion() {
  const restoreButton = document.getElementById("report-restore-button");
  if (!restoreButton || restoreButton.disabled) {
    setMessage("report-meta", "当前报告已经是完整正文");
    return;
  }
  restoreButton.click();
}

export function bindReplayHandlers({ loadAuditDetail }) {
  document.getElementById("replay-run-button").addEventListener("click", async () => {
    try {
      await replayBadCase({ loadAuditDetail });
    } catch (error) {
      setMessage("replay-output", error.message, true);
    }
  });

  document.getElementById("replay-history-button").addEventListener("click", async () => {
    try {
      await refreshReplayExperiments();
    } catch (error) {
      setMessage("replay-history-output", error.message, true);
    }
  });

  document.getElementById("replay-compare-button").addEventListener("click", async () => {
    const baseExperimentId = document.getElementById("replay-base-select").value;
    const targetExperimentId = document.getElementById("replay-target-select").value;
    if (!baseExperimentId || !targetExperimentId) {
      setMessage("replay-compare-output", "请先选择两条实验记录", true);
      return;
    }
    if (baseExperimentId === targetExperimentId) {
      setMessage("replay-compare-output", "基线实验和对比实验不能相同", true);
      return;
    }
    setMessage("replay-compare-output", "生成实验对比中...");
    try {
      const payload = await requestJson(
        `/v1/evals/replay-experiments/compare?base_experiment_id=${encodeURIComponent(baseExperimentId)}&target_experiment_id=${encodeURIComponent(targetExperimentId)}`
      );
      renderReplayComparison(payload);
    } catch (error) {
      setMessage("replay-compare-output", error.message, true);
    }
  });

  document.getElementById("replay-history-output").addEventListener("click", async (event) => {
    const button = event.target.closest(".case-button");
    if (!button) {
      return;
    }
    if (button.dataset.replaySelectRole && button.dataset.experimentId) {
      const targetSelectId =
        button.dataset.replaySelectRole === "base"
          ? "replay-base-select"
          : "replay-target-select";
      document.getElementById(targetSelectId).value = button.dataset.experimentId;
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

  document.getElementById("replay-compare-output").addEventListener("click", async (event) => {
    const button = event.target.closest(".case-button");
    if (!button) {
      return;
    }
    if (button.dataset.summaryAction === "restore-report") {
      restoreFullReportFromSuggestion();
      return;
    }
    if (button.dataset.summaryAction === "focus-section" && button.dataset.summaryTarget) {
      focusReplaySection(button.dataset.summaryTarget);
      return;
    }
    if (button.dataset.summaryAction === "open-audit" && button.dataset.auditId) {
      try {
        await loadAuditDetail(button.dataset.auditId);
      } catch (error) {
        setMessage("audit-output", error.message, true);
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
}
