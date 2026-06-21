export async function requestJson(url, options = {}) {
  const response = await fetch(url, options);

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }

  return response.json();
}

export function captureUrl(capture) {
  return `/api/captures/${capture.node_id}/${capture.archive_date}/${capture.period}/${capture.filename}`;
}

export function formatBytes(bytes) {
  if (!Number.isFinite(bytes)) return "-";

  if (bytes < 1024) return `${bytes} B`;

  const units = ["KB", "MB", "GB"];
  let value = bytes / 1024;

  for (const unit of units) {
    if (value < 1024 || unit === "GB") {
      return `${value.toFixed(value >= 10 ? 0 : 1)} ${unit}`;
    }

    value /= 1024;
  }

  return `${bytes} B`;
}

export function formatDateTime(value) {
  if (!value) return "-";

  return new Intl.DateTimeFormat(undefined, {
    dateStyle: "medium",
    timeStyle: "medium"
  }).format(new Date(value));
}

export function formatCaptureName(capture) {
  if (!capture) return "";

  const date = capture.archive_date || "unknown date";
  const period = capture.period || "capture";
  const node = capture.node_id || "node";
  const time = capture.modified_at
    ? new Intl.DateTimeFormat(undefined, {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit"
      }).format(new Date(capture.modified_at))
    : "";

  return [date, time, period, node].filter(Boolean).join(" - ");
}

export function preloadImage(url) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = resolve;
    image.onerror = reject;
    image.src = url;
  });
}
