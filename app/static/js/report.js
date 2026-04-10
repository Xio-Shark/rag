import { requestJson, setMessage } from "./shared.js";

const reportState = {
  runId: "",
  path: "",
  format: "markdown",
  fullContent: "",
  displayedContent: "",
  activeSectionTitle: "",
  sections: [],
};

function parseReportSections(content, formatName) {
  if (formatName !== "markdown") {
    return [];
  }
  const lines = String(content || "").split(/\r?\n/);
  const headingPattern = /^(#{1,3})\s+(.+)$/;
  const headings = [];

  lines.forEach((line, index) => {
    const match = line.match(headingPattern);
    if (!match) {
      return;
    }
    headings.push({
      level: match[1].length,
      title: match[2].trim().replace(/^\d+\.\s+/, ""),
      lineIndex: index,
    });
  });

  return headings.map((heading, index) => {
    const next = headings[index + 1];
    return {
      ...heading,
      content: lines
        .slice(heading.lineIndex, next ? next.lineIndex : lines.length)
        .join("\n")
        .trim(),
    };
  });
}

function updateRestoreButton() {
  const button = document.getElementById("report-restore-button");
  const canRestore =
    Boolean(reportState.fullContent)
    && reportState.displayedContent
    && reportState.displayedContent !== reportState.fullContent;
  button.disabled = !canRestore;
}

function renderReportOutline() {
  const container = document.getElementById("report-outline-output");
  if (!reportState.fullContent) {
    container.innerHTML = "读取 Markdown 报告后显示目录";
    return;
  }
  if (reportState.format !== "markdown") {
    container.innerHTML = "JSON 报告暂不提供目录导航";
    return;
  }
  if (!reportState.sections.length) {
    container.innerHTML = "当前报告没有可导航标题";
    return;
  }

  container.innerHTML = `
    <div class="outline-list">
      ${reportState.sections
        .map(
          (section, index) => `
            <button
              class="outline-button level-${section.level} ${section.title === reportState.activeSectionTitle ? "active" : ""}"
              data-report-section-index="${index}"
              type="button"
            >
              ${section.title}
            </button>
          `
        )
        .join("")}
    </div>
  `;
}

function renderReportContent(content, metaMessage) {
  setMessage("report-meta", metaMessage);
  document.getElementById("report-output").textContent = content || "暂无报告";
  updateRestoreButton();
  renderReportOutline();
}

export async function loadReport(evalRunId, formatName) {
  if (!evalRunId) {
    setMessage("report-meta", "请先选择一个评测运行", true);
    return;
  }
  setMessage("report-meta", "读取报告中...");
  const payload = await requestJson(
    `/v1/evals/${encodeURIComponent(evalRunId)}/report?format=${encodeURIComponent(formatName)}`
  );
  reportState.runId = evalRunId;
  reportState.path = payload.path;
  reportState.format = formatName;
  reportState.fullContent = payload.content;
  reportState.displayedContent = payload.content;
  reportState.activeSectionTitle = "";
  reportState.sections = parseReportSections(payload.content, formatName);
  renderReportContent(payload.content, payload.path);
}

export function syncReportPanel({
  runId,
  path,
  formatName = "markdown",
  fullContent = "",
  excerptContent = "",
  caseName = "",
}) {
  reportState.runId = runId || reportState.runId;
  reportState.path = path || reportState.path;
  reportState.format = formatName;
  reportState.fullContent = fullContent || excerptContent || reportState.fullContent;
  reportState.displayedContent = excerptContent || fullContent || reportState.fullContent;
  reportState.activeSectionTitle = caseName || "";
  reportState.sections = parseReportSections(reportState.fullContent, reportState.format);

  const reportRunSelect = document.getElementById("report-run-select");
  if (runId) {
    reportRunSelect.value = runId;
  }
  document.getElementById("report-format-select").value = formatName;

  const metaMessage = caseName ? `${reportState.path} | 已定位到 ${caseName}` : reportState.path;
  renderReportContent(reportState.displayedContent, metaMessage);
}

function restoreFullReport() {
  if (!reportState.fullContent) {
    return;
  }
  reportState.displayedContent = reportState.fullContent;
  reportState.activeSectionTitle = "";
  renderReportContent(reportState.fullContent, reportState.path);
}

function focusReportSection(sectionIndex) {
  const section = reportState.sections[sectionIndex];
  if (!section) {
    return;
  }
  reportState.displayedContent = section.content;
  reportState.activeSectionTitle = section.title;
  renderReportContent(section.content, `${reportState.path} | 已定位到 ${section.title}`);
}

export function bindReportHandlers() {
  document.getElementById("report-button").addEventListener("click", async () => {
    const evalRunId = document.getElementById("report-run-select").value;
    const formatName = document.getElementById("report-format-select").value;
    try {
      await loadReport(evalRunId, formatName);
    } catch (error) {
      setMessage("report-meta", error.message, true);
    }
  });

  document.getElementById("report-restore-button").addEventListener("click", () => {
    restoreFullReport();
  });

  document.getElementById("report-outline-output").addEventListener("click", (event) => {
    const button = event.target.closest(".outline-button");
    if (!button) {
      return;
    }
    focusReportSection(Number(button.dataset.reportSectionIndex));
  });
}
