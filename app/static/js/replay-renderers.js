import {
  escapeHtml,
  fillOptions,
  formatMetricValue,
  formatSnapshotValue,
  replayState,
  statusClass,
} from "./shared.js";

function replayOutcomeLabel(overallStatus) {
  if (overallStatus === "changed") return "当前实验结果已相对基线发生变化";
  return "当前实验结果与基线基本一致";
}

function renderSummaryActions(actions) {
  if (!actions.length) {
    return '<div class="metric-note">当前暂无直接入口</div>';
  }

  return `
    <div class="summary-actions">
      ${actions
        .map((action) => {
          const attributes = [
            ["data-summary-action", action.action],
            ["data-summary-target", action.target],
            ["data-audit-id", action.auditId],
          ]
            .filter(([, value]) => value)
            .map(([key, value]) => `${key}="${escapeHtml(String(value))}"`)
            .join(" ");
          const disabled = action.disabled ? " disabled" : "";

          return `
            <button class="case-button" ${attributes} type="button"${disabled}>
              ${escapeHtml(action.label)}
            </button>
          `;
        })
        .join("")}
    </div>
  `;
}

function buildReplaySummaryAdvice(payload, changedSettingsCount, outcome) {
  const reportRestoreButton = document.getElementById("report-restore-button");
  const canRestoreReport = Boolean(reportRestoreButton && !reportRestoreButton.disabled);
  const outputChanged =
    Boolean(outcome.answer_changed)
    || Boolean(outcome.refusal_changed)
    || outcome.citation_count_delta !== 0
    || Math.abs(Number(outcome.confidence_delta ?? 0)) > 0.001
    || Number(outcome.citation_overlap ?? 1) < 0.999;

  if (outputChanged) {
    const detail = outcome.refusal_changed
      ? "拒答或作答状态已经切换，先核对审计里的检索分数和证据片段。"
      : outcome.answer_changed
        ? "答案或证据组合已经变化，建议先看审计确认变化是否由有效证据带来。"
        : "实验结果已经变化，建议先回查审计确认变化来源。";

    return {
      title: "先核对变化来源",
      detail,
      actions: [
        payload.target_experiment?.audit_id
          ? {
              label: "查看审计",
              action: "open-audit",
              auditId: payload.target_experiment.audit_id,
            }
          : null,
        canRestoreReport
          ? { label: "恢复完整报告", action: "restore-report" }
          : { label: "查看参数差异", action: "focus-section", target: "settings-diff" },
      ].filter(Boolean),
    };
  }

  if (changedSettingsCount > 0) {
    return {
      title: "当前实验收益有限",
      detail: "参数已变化，但回答、拒答和引用基本没动，先看参数差异再决定是否继续扩大实验。",
      actions: [{ label: "查看参数差异", action: "focus-section", target: "settings-diff" }],
    };
  }

  return {
    title: "结果保持稳定",
    detail: "当前实验输出与基线基本一致，可以继续尝试更激进的参数组合。",
    actions: [],
  };
}

function renderReplaySummary(payload) {
  const outcome = payload.outcome || {};
  const changedSettingsCount = Object.values(payload.settings_diff || {}).filter(
    (item) => item.changed
  ).length;
  const firstDiagnosis = payload.diagnosis?.[0] || "当前没有明显归因提示";
  const answerSummary = `${outcome.answer_changed ? "回答已变化" : "回答稳定"} / ${
    outcome.refusal_changed ? "拒答已变化" : "拒答稳定"
  }`;
  const statusTone =
    payload.overall_status === "changed" ? statusClass("mixed") : statusClass("unchanged");
  const advice = buildReplaySummaryAdvice(payload, changedSettingsCount, outcome);

  return `
    <div class="summary-grid">
      <div class="summary-card emphasis">
        <div class="summary-label">实验摘要</div>
        <div class="summary-main">
          <span class="status-pill ${statusTone}">${payload.overall_status}</span>
        </div>
        <div class="summary-support">${replayOutcomeLabel(payload.overall_status)}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">证据变化</div>
        <div class="summary-main">置信度 ${formatMetricValue(outcome.confidence_delta ?? 0)}</div>
        <div class="summary-support">引用数量变化 ${formatMetricValue(outcome.citation_count_delta ?? 0)}，重叠率 ${formatMetricValue(outcome.citation_overlap ?? 0)}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">回答变化</div>
        <div class="summary-main">${answerSummary}</div>
        <div class="summary-support">same_query：${outcome.same_query ? "是" : "否"}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">参数变化</div>
        <div class="summary-main">${changedSettingsCount} 项设置变化</div>
        <div class="summary-support">${firstDiagnosis}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">建议动作</div>
        <div class="summary-main">${escapeHtml(advice.title)}</div>
        <div class="summary-support">${escapeHtml(advice.detail)}</div>
        ${renderSummaryActions(advice.actions)}
      </div>
    </div>
  `;
}

export function renderReplayContext() {
  const container = document.getElementById("replay-context-output");
  const selectedCase = replayState.selectedCase;
  if (!selectedCase) {
    container.innerHTML = "点击 bad case 的“重新回放”后绑定当前案例";
    return;
  }
  container.innerHTML = `
    <div class="panel-stack">
      <div>
        <strong>${escapeHtml(selectedCase.caseName || "未命名 bad case")}</strong>
        <div class="metric-note">${escapeHtml(selectedCase.query)}</div>
      </div>
      <div class="metric-note">
        来源运行：${escapeHtml(selectedCase.sourceEvalRunId || "无")} | 来源快照：${escapeHtml(selectedCase.sourceSnapshotName || "无")}
      </div>
      <div class="metric-note">历史拒答原因：${escapeHtml(selectedCase.originalRefusal || "无")}</div>
    </div>
  `;
}

export function readReplayControls() {
  const snapshotSelect = document.getElementById("replay-snapshot-select");
  const topKRaw = document.getElementById("replay-top-k-input").value.trim();
  const thresholdRaw = document.getElementById("replay-threshold-input").value.trim();
  const snapshotName =
    snapshotSelect.value || replayState.selectedCase?.sourceSnapshotName || "default";
  let topK = null;
  let retrievalThreshold = null;

  if (topKRaw) {
    topK = Number(topKRaw);
    if (!Number.isInteger(topK) || topK < 1 || topK > 5) {
      throw new Error("top_k 必须是 1 到 5 之间的整数");
    }
  }
  if (thresholdRaw) {
    retrievalThreshold = Number(thresholdRaw);
    if (
      Number.isNaN(retrievalThreshold)
      || retrievalThreshold < 0
      || retrievalThreshold > 1
    ) {
      throw new Error("拒答阈值必须在 0 到 1 之间");
    }
  }

  return {
    snapshot_name: snapshotName,
    top_k: topK,
    retrieval_threshold: retrievalThreshold,
  };
}

export function fillReplayExperimentOptions() {
  const baseSelect = document.getElementById("replay-base-select");
  const targetSelect = document.getElementById("replay-target-select");
  const previousBase = baseSelect.value;
  const previousTarget = targetSelect.value;
  const items = replayState.experiments.map((item) => ({
    value: item.experiment_id,
    label: `${item.snapshot_name} | ${item.created_at} | ${item.experiment_id.slice(0, 8)} | top_k ${item.effective_settings?.top_k ?? "?"}`,
  }));

  fillOptions("replay-base-select", items, (item) => item.label);
  fillOptions("replay-target-select", items, (item) => item.label);

  if (items.some((item) => item.value === previousBase)) {
    baseSelect.value = previousBase;
  }
  if (items.some((item) => item.value === previousTarget)) {
    targetSelect.value = previousTarget;
  }
  if (!baseSelect.value && items[1]) {
    baseSelect.value = items[1].value;
  }
  if (!targetSelect.value && items[0]) {
    targetSelect.value = items[0].value;
  }
}

export function renderReplayExperimentHistory(items, activeQuery = "") {
  const container = document.getElementById("replay-history-output");
  if (!items.length) {
    container.innerHTML = "暂无实验记录";
    return;
  }
  container.innerHTML = `
    <div class="panel-stack">
      ${
        activeQuery
          ? `<div class="metric-note">当前按问题过滤：${escapeHtml(activeQuery)}</div>`
          : ""
      }
      <div class="history-list">
        ${items
          .map(
            (item) => `
              <div class="history-item">
                <div>
                  <strong>${escapeHtml(item.case_name || item.query)}</strong>
                  <div class="metric-note">${escapeHtml(item.snapshot_name)} | ${escapeHtml(item.created_at)}</div>
                  <div class="metric-note">实验 ID：${escapeHtml(item.experiment_id)} | 审计 ID：${escapeHtml(item.audit_id)}</div>
                </div>
                <div class="metric-note">
                  top_k ${item.effective_settings?.top_k ?? "?"} | 阈值 ${formatMetricValue(item.effective_settings?.retrieval_threshold ?? 0)}
                </div>
                <div class="metric-note">
                  置信度 ${formatMetricValue(item.confidence)} | 拒答 ${escapeHtml(item.refusal_reason || "无")}
                </div>
                <div class="history-actions">
                  <button
                    class="case-button"
                    data-replay-select-role="base"
                    data-experiment-id="${item.experiment_id}"
                    type="button"
                  >
                    设为基线
                  </button>
                  <button
                    class="case-button"
                    data-replay-select-role="target"
                    data-experiment-id="${item.experiment_id}"
                    type="button"
                  >
                    设为对比
                  </button>
                  <button
                    class="case-button"
                    data-audit-id="${item.audit_id}"
                    type="button"
                  >
                    查看审计
                  </button>
                </div>
              </div>
            `
          )
          .join("")}
      </div>
    </div>
  `;
}

export function renderReplayComparison(payload) {
  const container = document.getElementById("replay-compare-output");
  const summary = renderReplaySummary(payload);
  const changedSettings = Object.entries(payload.settings_diff || {})
    .filter(([, item]) => item.changed)
    .map(
      ([key, item]) => `
        <div class="snapshot-row">
          <div><code>${key}</code></div>
          <div>
            <div>${formatSnapshotValue(item.base)} -> ${formatSnapshotValue(item.target)}</div>
            <div class="delta-note">已变更</div>
          </div>
        </div>
      `
    )
    .join("");
  const diagnosis = (payload.diagnosis || []).map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  const outcome = payload.outcome || {};
  container.innerHTML = `
    <div class="panel-stack">
      ${summary}
      <div class="replay-grid">
        <div class="detail-block">
          <strong>基线实验</strong>
          <div class="metric-note">${escapeHtml(payload.base_experiment.snapshot_name)} | ${escapeHtml(payload.base_experiment.experiment_id)}</div>
          <button class="case-button" data-audit-id="${payload.base_experiment.audit_id}" type="button">查看审计</button>
          <div class="metric-note">拒答原因：${escapeHtml(payload.base_experiment.refusal_reason || "无")}</div>
          <pre>${escapeHtml(payload.base_experiment.answer || "空")}</pre>
        </div>
        <div class="detail-block">
          <strong>对比实验</strong>
          <div class="metric-note">${escapeHtml(payload.target_experiment.snapshot_name)} | ${escapeHtml(payload.target_experiment.experiment_id)}</div>
          <button class="case-button" data-audit-id="${payload.target_experiment.audit_id}" type="button">查看审计</button>
          <div class="metric-note">拒答原因：${escapeHtml(payload.target_experiment.refusal_reason || "无")}</div>
          <pre>${escapeHtml(payload.target_experiment.answer || "空")}</pre>
        </div>
      </div>
      <div class="snapshot-card">
        <strong>结果变化</strong>
        <div class="metric-note">confidence delta：${formatMetricValue(outcome.confidence_delta ?? 0)}</div>
        <div class="metric-note">citation_count delta：${formatMetricValue(outcome.citation_count_delta ?? 0)}</div>
        <div class="metric-note">citation overlap：${formatMetricValue(outcome.citation_overlap ?? 0)}</div>
        <div class="metric-note">answer_changed：${outcome.answer_changed ? "是" : "否"}</div>
        <div class="metric-note">refusal_changed：${outcome.refusal_changed ? "是" : "否"}</div>
      </div>
      <div class="snapshot-card" data-summary-section="settings-diff">
        <strong>参数差异</strong>
        <div class="snapshot-diff">
          ${changedSettings || '<div class="metric-note">当前无参数变化</div>'}
        </div>
      </div>
      <div class="callout">
        <strong>归因提示</strong>
        <ul class="plain-list">${diagnosis}</ul>
      </div>
    </div>
  `;
}

export function renderReplayWorkbench({ selectedCase, replayPayload }) {
  const container = document.getElementById("replay-output");
  const replayCitations = (replayPayload.citations || [])
    .map(
      (item) => `
        <div class="list-item">
          <div class="metric-note">
            ${escapeHtml(item.document_title)} | ${escapeHtml(item.title_path || "无标题路径")} | ${formatMetricValue(item.score)}
          </div>
          <div class="metric-note">${escapeHtml(item.snippet || "")}</div>
        </div>
      `
    )
    .join("");
  const overrideEntries = Object.entries(replayPayload.overrides || {});
  const effectiveEntries = Object.entries(replayPayload.effective_settings || {})
    .map(
      ([key, value]) =>
        `<div class="metric-note">${escapeHtml(key)}：${escapeHtml(formatSnapshotValue(value))}</div>`
    )
    .join("");
  container.innerHTML = `
    <div class="panel-stack">
      <div>
        <strong>${escapeHtml(selectedCase.caseName || "未命名 bad case")}</strong>
        <div class="metric-note">${escapeHtml(selectedCase.query)}</div>
        <div class="metric-note">实验 ID：${escapeHtml(replayPayload.experiment_id)} | 审计 ID：${escapeHtml(replayPayload.audit_id)}</div>
      </div>
      <div class="metric-grid">
        <div class="metric-card">
          <strong>证据置信度</strong>
          <div class="metric-value">${formatMetricValue(replayPayload.confidence)}</div>
        </div>
        <div class="metric-card">
          <strong>当前快照</strong>
          <div class="metric-value">${escapeHtml(replayPayload.snapshot_name)}</div>
        </div>
      </div>
      <div class="replay-grid">
        <div class="detail-block">
          <strong>历史结果</strong>
          <div class="metric-note">拒答原因：${escapeHtml(selectedCase.originalRefusal || "无")}</div>
          <pre>${escapeHtml(selectedCase.originalAnswer || "空")}</pre>
        </div>
        <div class="detail-block">
          <strong>当前实验结果</strong>
          <div class="metric-note">拒答原因：${escapeHtml(replayPayload.refusal_reason || "无")}</div>
          <pre>${escapeHtml(replayPayload.answer || "空")}</pre>
        </div>
      </div>
      <div class="snapshot-card">
        <strong>覆盖参数</strong>
        ${
          overrideEntries.length
            ? overrideEntries
                .map(
                  ([key, value]) =>
                    `<div class="metric-note">${escapeHtml(key)}：${escapeHtml(formatSnapshotValue(value))}</div>`
                )
                .join("")
            : '<div class="metric-note">本次未额外覆盖，完全跟随快照</div>'
        }
      </div>
      <div class="snapshot-card">
        <strong>有效参数</strong>
        ${effectiveEntries}
      </div>
      <div class="snapshot-card">
        <strong>当前回放引用</strong>
        ${replayCitations || '<div class="metric-note">无引用</div>'}
      </div>
    </div>
  `;
}
