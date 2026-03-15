import {
  bindEvaluationHandlers,
  refreshDatasetsAndSnapshots,
  refreshRuns,
} from "./evals.js";
import {
  bindKnowledgeHandlers,
  loadAuditDetail,
  refreshAuditRuns,
  refreshDocuments,
} from "./knowledge.js";
import { bindReplayHandlers, decodeReplaySelection, refreshReplayExperiments, replayBadCase } from "./replay.js";
import { bindReportHandlers } from "./report.js";
import {
  isFeatureEnabled,
  requestJson,
  setControlsDisabled,
  setFeatureFlags,
  setMessage,
} from "./shared.js";

const evalControlIds = [
  "dataset-select",
  "snapshot-select",
  "datasets-button",
  "run-eval-button",
  "eval-button",
  "runs-button",
  "base-run-select",
  "target-run-select",
  "compare-button",
  "snapshot-button",
  "report-run-select",
  "report-format-select",
  "report-button",
];

const replayControlIds = [
  "replay-snapshot-select",
  "replay-top-k-input",
  "replay-threshold-input",
  "replay-run-button",
  "replay-history-button",
  "replay-base-select",
  "replay-target-select",
  "replay-compare-button",
];

function bindWorkbenchHandlers() {
  bindKnowledgeHandlers();
  bindReportHandlers();
  bindReplayHandlers({ loadAuditDetail });
  bindEvaluationHandlers({
    decodeReplaySelection,
    loadAuditDetail,
    replayBadCase,
  });
}

async function loadHealthStatus() {
  const payload = await requestJson("/v1/health");
  setFeatureFlags(payload.feature_flags || {});
}

function applyFeatureFlags() {
  const evalsEnabled = isFeatureEnabled("evals");
  const replayEnabled = isFeatureEnabled("replay_experiments");

  setControlsDisabled(evalControlIds, !evalsEnabled);
  if (!evalsEnabled) {
    setMessage("run-eval-output", "当前环境未启用评测与回归功能");
    setMessage("eval-output", "当前环境未启用评测与回归功能");
    setMessage("compare-output", "当前环境未启用评测与回归功能");
    setMessage("compare-detail-output", "当前环境未启用评测与回归功能");
    setMessage("snapshot-output", "当前环境未启用评测与回归功能");
    setMessage("report-meta", "当前环境未启用评测与回归功能");
    document.getElementById("report-output").textContent = "当前环境未启用评测与回归功能";
    document.getElementById("report-outline-output").textContent =
      "当前环境未启用评测与回归功能";
  }

  setControlsDisabled(replayControlIds, !replayEnabled);
  if (!replayEnabled) {
    setMessage("replay-context-output", "当前环境未启用回放实验功能");
    setMessage("replay-output", "当前环境未启用回放实验功能");
    setMessage("replay-compare-output", "当前环境未启用回放实验功能");
    setMessage("replay-history-output", "当前环境未启用回放实验功能");
  }
}

export async function initializeWorkbench() {
  bindWorkbenchHandlers();
  try {
    await loadHealthStatus();
    applyFeatureFlags();

    const tasks = [refreshDocuments(), refreshAuditRuns()];
    if (isFeatureEnabled("evals")) {
      tasks.push(refreshDatasetsAndSnapshots(), refreshRuns());
    }
    if (isFeatureEnabled("replay_experiments")) {
      tasks.push(refreshReplayExperiments());
    }
    await Promise.all(tasks);
  } catch (error) {
    console.error(error);
  }
}
