export const compareState = {
  payload: null,
  baseRun: null,
  targetRun: null,
  baseReport: null,
  targetReport: null,
  activeCaseKey: "",
};

export const documentState = {
  payload: null,
  focusChunkId: "",
  filterText: "",
};

export const replayState = {
  selectedCase: null,
  experiments: [],
};

export const featureState = {
  flags: {
    evals: true,
    replay_experiments: true,
  },
};

export async function requestJson(url, options = {}) {
  const response = await fetch(url, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.detail || "请求失败");
  }
  return payload;
}

export function setFeatureFlags(flags = {}) {
  featureState.flags = {
    evals: flags.evals !== false,
    replay_experiments: flags.replay_experiments !== false,
  };
}

export function isFeatureEnabled(name) {
  return featureState.flags[name] !== false;
}

export function setControlsDisabled(ids, disabled) {
  ids.forEach((id) => {
    const element = document.getElementById(id);
    if (element) {
      element.disabled = disabled;
    }
  });
}

export function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

export function setMessage(id, message, isError = false) {
  const element = document.getElementById(id);
  element.textContent = message;
  element.classList.toggle("error", isError);
}

export function fillOptions(selectId, items, labelBuilder) {
  const select = document.getElementById(selectId);
  select.innerHTML = '<option value="">请选择</option>';
  items.forEach((item) => {
    const option = document.createElement("option");
    option.value = item.value;
    option.textContent = labelBuilder(item);
    select.appendChild(option);
  });
}

export function formatMetricValue(value) {
  if (typeof value === "number") {
    return Number.isInteger(value)
      ? String(value)
      : value.toFixed(4).replace(/0+$/, "").replace(/\.$/, "");
  }
  return String(value);
}

export function formatSnapshotValue(value) {
  if (typeof value === "string") {
    return value || "空";
  }
  return JSON.stringify(value);
}

export function statusClass(status) {
  if (status === "improved") return "status-improved";
  if (status === "regressed") return "status-regressed";
  if (status === "mixed") return "status-mixed";
  return "status-unchanged";
}
