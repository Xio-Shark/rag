import {
  compareState,
  escapeHtml,
  formatMetricValue,
  formatSnapshotValue,
  statusClass,
} from "./shared.js";

function buildCompareStatusCounts(metrics) {
  return Object.values(metrics || {}).reduce(
    (counts, item) => {
      const status = item?.status || "unchanged";
      counts[status] = (counts[status] || 0) + 1;
      return counts;
    },
    { improved: 0, regressed: 0, mixed: 0, unchanged: 0 }
  );
}

function countChangedSnapshotKeys(baseValues, targetValues) {
  return Array.from(new Set([...Object.keys(baseValues), ...Object.keys(targetValues)])).filter(
    (key) => JSON.stringify(baseValues[key]) !== JSON.stringify(targetValues[key])
  ).length;
}

function compareOutcomeLabel(overallStatus) {
  if (overallStatus === "improved") return "本轮对比整体优于基线";
  if (overallStatus === "regressed") return "本轮对比出现明显回归";
  if (overallStatus === "mixed") return "本轮对比存在收益也有回退";
  return "本轮对比整体保持稳定";
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
            ["data-case-group", action.caseGroup],
            ["data-case-name", action.caseName],
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

function buildCompareSummaryAdvice({
  payload,
  changedParams,
  metricCounts,
  badCaseDiff,
  firstDiagnosis,
}) {
  const newRegressions = badCaseDiff.new_regressions || [];
  const resolvedCases = badCaseDiff.resolved || [];
  const persistedCases = badCaseDiff.persisted || [];
  const snapshotAction =
    changedParams > 0
      ? [{ label: "查看参数差异", action: "focus-section", target: "snapshot-diff" }]
      : [];

  if (newRegressions.length) {
    return {
      title: "优先查看新增回归",
      detail: `新增回归 ${newRegressions.length} 个，先检查 ${newRegressions[0]} 的审计和证据。`,
      actions: [
        {
          label: "去看 bad case",
          action: "focus-case",
          caseGroup: "new_regressions",
          caseName: newRegressions[0],
        },
        ...snapshotAction,
      ],
    };
  }

  if (payload.overall_status === "improved" && resolvedCases.length) {
    return {
      title: "先确认收益是否稳定",
      detail: `本轮解决了 ${resolvedCases.length} 个 bad case，建议先复看 ${resolvedCases[0]}。`,
      actions: [
        {
          label: "查看已解决 case",
          action: "focus-case",
          caseGroup: "resolved",
          caseName: resolvedCases[0],
        },
        ...snapshotAction,
      ],
    };
  }

  if (changedParams > 0 && payload.overall_status === "unchanged") {
    return {
      title: "当前实验收益有限",
      detail: "参数已变化，但指标和 bad case 仍基本稳定，先看参数差异再决定是否继续放大实验。",
      actions: snapshotAction,
    };
  }

  if (persistedCases.length) {
    return {
      title: "继续检查持续 bad case",
      detail: `还有 ${persistedCases.length} 个 bad case 持续存在，优先确认 ${persistedCases[0]} 是否仍受检索约束影响。`,
      actions: [
        {
          label: "查看持续 bad case",
          action: "focus-case",
          caseGroup: "persisted",
          caseName: persistedCases[0],
        },
        ...snapshotAction,
      ],
    };
  }

  return {
    title:
      metricCounts.improved > 0 && metricCounts.regressed > 0
        ? "先核对参数差异"
        : "继续观察当前结果",
    detail: firstDiagnosis,
    actions: snapshotAction,
  };
}

function renderCompareSummary(payload) {
  const metricCounts = buildCompareStatusCounts(payload.metrics || {});
  const changedParams = countChangedSnapshotKeys(
    payload.base_snapshot_values || {},
    payload.target_snapshot_values || {}
  );
  const badCaseDiff = payload.bad_case_diff || {};
  const firstDiagnosis = payload.diagnosis?.[0] || "当前没有明显归因提示";
  const advice = buildCompareSummaryAdvice({
    payload,
    changedParams,
    metricCounts,
    badCaseDiff,
    firstDiagnosis,
  });

  return `
    <div class="summary-grid">
      <div class="summary-card emphasis">
        <div class="summary-label">实验摘要</div>
        <div class="summary-main">
          <span class="status-pill ${statusClass(payload.overall_status)}">${payload.overall_status}</span>
        </div>
        <div class="summary-support">${compareOutcomeLabel(payload.overall_status)}</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">指标概览</div>
        <div class="summary-main">${metricCounts.improved} 升 / ${metricCounts.regressed} 降</div>
        <div class="summary-support">混合 ${metricCounts.mixed} 项，稳定 ${metricCounts.unchanged} 项</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">Bad Case</div>
        <div class="summary-main">${(badCaseDiff.new_regressions || []).length} 新增回归</div>
        <div class="summary-support">已解决 ${(badCaseDiff.resolved || []).length} 个，持续存在 ${(badCaseDiff.persisted || []).length} 个</div>
      </div>
      <div class="summary-card">
        <div class="summary-label">关键变化</div>
        <div class="summary-main">${changedParams} 项参数变化</div>
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

export function renderSnapshotList(payload) {
  const container = document.getElementById("snapshot-output");
  const items = payload.items || [];
  if (!items.length) {
    container.innerHTML = "暂无快照";
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <div class="metric">
          <strong>${item.name}</strong>
          <div class="muted">${item.description || "无描述"}</div>
          <pre>${JSON.stringify(item.values, null, 2)}</pre>
        </div>
      `
    )
    .join("");
}

export function renderRunOptions(payload) {
  const items = (payload.items || []).map((item) => ({
    value: item.eval_run_id,
    label: `${item.snapshot_name} | ${item.created_at} | ${item.eval_run_id.slice(0, 8)}`,
  }));
  const fillOptionList = (selectId) => {
    const select = document.getElementById(selectId);
    select.innerHTML = '<option value="">请选择</option>';
    items.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.value;
      option.textContent = item.label;
      select.appendChild(option);
    });
  };
  fillOptionList("base-run-select");
  fillOptionList("target-run-select");
  fillOptionList("report-run-select");
}

export function renderCompare(payload) {
  const container = document.getElementById("compare-output");
  const summary = renderCompareSummary(payload);
  const metrics = Object.entries(payload.metrics || {})
    .map(([name, item]) => renderCompareMetric(name, item))
    .join("");
  const diff = payload.bad_case_diff || {};
  const diagnosis = (payload.diagnosis || []).map((item) => `<li>${item}</li>`).join("");
  const snapshotDiff = renderSnapshotDiff(
    payload.base_snapshot_values || {},
    payload.target_snapshot_values || {}
  );
  container.innerHTML = `
    <div class="compare-layout">
      ${summary}
      <div class="snapshot-grid">
        <div class="snapshot-card">
          <strong>基线运行</strong>
          <div class="metric-note">${payload.base_snapshot_name} | ${payload.base_eval_run_id.slice(0, 8)}</div>
          <div class="metric-note">${payload.base_dataset_name}</div>
        </div>
        <div class="snapshot-card">
          <strong>对比运行</strong>
          <div class="metric-note">${payload.target_snapshot_name} | ${payload.target_eval_run_id.slice(0, 8)}</div>
          <div class="metric-note">${payload.target_dataset_name}</div>
        </div>
      </div>
      <div class="metric-grid">${metrics}</div>
      <div class="callout ${payload.overall_status === "regressed" ? "danger" : ""}">
        <strong>归因提示</strong>
        ${
          diagnosis
            ? `<ul class="plain-list">${diagnosis}</ul>`
            : '<div class="metric-note">暂无明显归因提示</div>'
        }
      </div>
      <div class="snapshot-card" data-summary-section="snapshot-diff">
        <strong>快照参数差异</strong>
        <div class="snapshot-diff">${snapshotDiff}</div>
      </div>
      <div class="snapshot-card">
        <strong>Bad Case 变化</strong>
        <div class="metric-note">新增回归：${(diff.new_regressions || []).join("，") || "无"}</div>
        <div class="metric-note">已解决：${(diff.resolved || []).join("，") || "无"}</div>
        <div class="metric-note">持续存在：${(diff.persisted || []).join("，") || "无"}</div>
        ${renderCompareCaseGroups(payload)}
      </div>
      <div class="snapshot-card">
        <strong>报告路径</strong>
        <div class="metric-note">JSON: ${payload.report_json_path}</div>
        <div class="metric-note">Markdown: ${payload.report_markdown_path}</div>
      </div>
    </div>
  `;
}

export function renderCompareMetric(name, item) {
  const deltaLabel =
    typeof item.delta === "number" && item.delta > 0 ? `+${item.delta}` : item.delta;
  return `
    <div class="metric-card">
      <strong>${name}</strong>
      <div class="metric-value">${formatMetricValue(item.target)}</div>
      <div class="metric-note">基线 ${formatMetricValue(item.base)} -> 对比 ${formatMetricValue(item.target)}</div>
      <div class="metric-note">delta ${deltaLabel}</div>
      <div class="metric-note">
        <span class="status-pill ${statusClass(item.status)}">${item.status}</span>
      </div>
    </div>
  `;
}

export function renderSnapshotDiff(baseValues, targetValues) {
  const keys = Array.from(new Set([...Object.keys(baseValues), ...Object.keys(targetValues)]));
  return keys
    .map((key) => {
      const baseValue = key in baseValues ? baseValues[key] : "未设置";
      const targetValue = key in targetValues ? targetValues[key] : "未设置";
      const changed = JSON.stringify(baseValue) !== JSON.stringify(targetValue);
      return `
        <div class="snapshot-row">
          <div><code>${key}</code></div>
          <div>
            <div>${formatSnapshotValue(baseValue)} -> ${formatSnapshotValue(targetValue)}</div>
            <div class="delta-note">${changed ? "已变更" : "未变化"}</div>
          </div>
        </div>
      `;
    })
    .join("");
}

export function renderEvalSummary(payload) {
  const container = document.getElementById("eval-output");
  const summaryCards = renderSummaryCards(payload.summary || {});
  const badCases = (payload.bad_cases || [])
    .map(
      (item) => `
        <div class="list-item">
          <strong>${item.case_name}</strong>
          <div class="metric-note">${item.query}</div>
          <div class="metric-note">拒答原因：${item.refusal_reason || "无"}</div>
          ${renderReplayButton(item.case_name, item, {
            sourceEvalRunId: payload.eval_run_id,
            sourceSnapshotName: payload.snapshot_name,
          })}
        </div>
      `
    )
    .join("");
  container.innerHTML = `
    <div class="panel-stack">
      <div>
        <span class="tag">${payload.snapshot_name}</span>
        <div class="metric-note">${payload.eval_run_id.slice(0, 8)} | ${payload.created_at}</div>
      </div>
      <div class="metric-grid">${summaryCards}</div>
      <div class="snapshot-card">
        <strong>Bad Cases</strong>
        ${badCases || '<div class="metric-note">当前运行无 bad case</div>'}
      </div>
    </div>
  `;
}

export function renderRunResult(payload) {
  const container = document.getElementById("run-eval-output");
  const badCaseCount = (payload.bad_cases || []).length;
  container.innerHTML = `
    <div class="panel-stack">
      <div>
        <span class="tag">${payload.snapshot_name}</span>
        <div class="metric-note">${payload.eval_run_id}</div>
      </div>
      <div class="metric-grid">${renderSummaryCards(payload.summary || {})}</div>
      <div class="snapshot-card">
        <strong>运行结果</strong>
        <div class="metric-note">用例数：${payload.case_count}</div>
        <div class="metric-note">bad case 数量：${badCaseCount}</div>
        <div class="metric-note">Markdown 报告：${payload.report_markdown_path}</div>
      </div>
    </div>
  `;
}

export function renderRunsList(payload) {
  const container = document.getElementById("eval-output");
  const items = payload.items || [];
  if (!items.length) {
    container.innerHTML = "暂无运行记录";
    return;
  }
  container.innerHTML = items
    .map(
      (item) => `
        <div class="snapshot-card">
          <strong>${item.snapshot_name}</strong>
          <div class="metric-note">${item.eval_run_id.slice(0, 8)} | ${item.created_at}</div>
          <div class="metric-grid">${renderSummaryCards(item.summary || {})}</div>
        </div>
      `
    )
    .join("");
}

export function renderSummaryCards(summary) {
  return Object.entries(summary)
    .map(
      ([name, value]) => `
        <div class="metric-card">
          <strong>${name}</strong>
          <div class="metric-value">${formatMetricValue(value)}</div>
        </div>
      `
    )
    .join("");
}

export function renderCompareCaseGroups(payload) {
  const groups = [
    {
      label: "新增回归",
      key: "new_regressions",
      cases: payload.bad_case_diff?.new_regressions || [],
    },
    {
      label: "已解决",
      key: "resolved",
      cases: payload.bad_case_diff?.resolved || [],
    },
    {
      label: "持续存在",
      key: "persisted",
      cases: payload.bad_case_diff?.persisted || [],
    },
  ].filter((group) => group.cases.length);

  if (!groups.length) {
    return '<div class="metric-note">当前没有可钻取的 bad case</div>';
  }

  return groups
    .map(
      (group) => `
        <div class="case-group">
          <div class="metric-note">${group.label}</div>
          <div class="case-buttons">
            ${group.cases
              .map(
                (caseName) => `
                  <button
                    class="case-button"
                    data-case-group="${group.key}"
                    data-case-name="${caseName}"
                    type="button"
                  >
                    ${caseName}
                  </button>
                `
              )
              .join("")}
          </div>
        </div>
      `
    )
    .join("");
}

export function renderReplayButton(caseName, detail, sourceContext = {}) {
  return `
    <button
      class="case-button"
      data-replay-query="${encodeURIComponent(detail.query || "")}"
      data-replay-case-name="${encodeURIComponent(caseName || "")}"
      data-original-answer="${encodeURIComponent(detail.answer || "")}"
      data-original-refusal="${encodeURIComponent(detail.refusal_reason || "")}"
      data-source-eval-run-id="${encodeURIComponent(sourceContext.sourceEvalRunId || "")}"
      data-source-snapshot-name="${encodeURIComponent(sourceContext.sourceSnapshotName || "")}"
      type="button"
    >
      重新回放
    </button>
  `;
}

export function renderCompareDetailPlaceholder(payload) {
  const container = document.getElementById("compare-detail-output");
  const regressionCount = payload.bad_case_diff?.new_regressions?.length || 0;
  container.innerHTML = `
    <div class="detail-grid">
      <div class="status-pill ${statusClass(payload.overall_status)}">${payload.overall_status}</div>
      <div class="metric-note">
        已加载基线 ${payload.base_snapshot_name} 和对比 ${payload.target_snapshot_name} 的报告正文。
      </div>
      <div class="metric-note">
        当前新增回归 ${regressionCount} 个，点击上方 bad case 按钮查看明细。
      </div>
    </div>
  `;
}

export function findCaseDetail(runPayload, caseName) {
  return (runPayload?.bad_cases || []).find((item) => item.case_name === caseName) || null;
}

export function extractReportSection(content, caseName) {
  const lines = String(content || "").split(/\r?\n/);
  const sectionHeading = /^###\s+\d+\.\s+/;
  const startIndex = lines.findIndex(
    (line) => sectionHeading.test(line.trim()) && line.includes(caseName)
  );

  if (startIndex === -1) {
    return "报告正文中未找到该用例片段";
  }

  let endIndex = lines.length;
  for (let index = startIndex + 1; index < lines.length; index += 1) {
    if (sectionHeading.test(lines[index].trim())) {
      endIndex = index;
      break;
    }
  }

  return lines.slice(startIndex, endIndex).join("\n").trim();
}

export function syncReportPanel(runId, path, excerpt, caseName) {
  const reportRunSelect = document.getElementById("report-run-select");
  reportRunSelect.value = runId;
  setMessage("report-meta", `${path} | 已定位到 ${caseName}`);
  document.getElementById("report-output").textContent = excerpt;
}

export function renderCaseDetailBlock(title, detail, excerpt, runContext) {
  const expectedKeywords = (detail.expected_keywords || []).join("，") || "无";
  return `
    <div class="detail-block">
      <strong>${title}</strong>
      ${
        detail.audit_id
          ? `
            <button
              class="case-button"
              data-audit-id="${detail.audit_id}"
              type="button"
            >
              查看审计
            </button>
          `
          : ""
      }
      ${renderReplayButton(detail.case_name, detail, runContext)}
      <div class="metric-note">问题：${detail.query}</div>
      <div class="metric-note">拒答原因：${detail.refusal_reason || "无"}</div>
      <div class="metric-note">期望关键词：${expectedKeywords}</div>
      <div class="metric-note">回答：</div>
      <pre>${detail.answer || "空"}</pre>
      <div class="metric-note">报告片段：</div>
      <pre>${excerpt}</pre>
    </div>
  `;
}

export function caseGroupLabel(groupKey) {
  if (groupKey === "new_regressions") return "新增回归";
  if (groupKey === "resolved") return "已解决";
  if (groupKey === "persisted") return "持续存在";
  return groupKey;
}

export function updateCaseButtonState() {
  document.querySelectorAll(".case-button").forEach((button) => {
    const key = `${button.dataset.caseGroup}:${button.dataset.caseName}`;
    button.classList.toggle("active", key === compareState.activeCaseKey);
  });
}
