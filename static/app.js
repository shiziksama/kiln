const series = [
  {
    field: "ambient_temperature",
    label: "Температура",
    unit: "°C",
    color: "#f2b84b",
    minSpan: 10,
    hardMin: -20,
    hardMax: 80,
    axis: "left",
  },
  {
    field: "humidity",
    label: "Вологість",
    unit: "%",
    color: "#61c3ff",
    minSpan: 20,
    hardMin: 0,
    hardMax: 100,
    axis: "right-inner",
  },
  {
    field: "kiln_temperature",
    label: "Пічка",
    unit: "°C",
    color: "#ff5a63",
    minSpan: 50,
    hardMin: 0,
    hardMax: 1300,
    axis: "right",
  },
];

const visibleSeries = new Set(
  JSON.parse(localStorage.getItem("kiln-visible-series") || "null") ||
    series.map((item) => item.field)
);

function formatValue(value, unit) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "--";
  }
  return `${Number(value).toFixed(1)}${unit}`;
}

function formatTime(timestamp, precision = "seconds") {
  if (!timestamp) {
    return "--";
  }
  return new Date(timestamp).toLocaleTimeString("uk-UA", {
    hour: "2-digit",
    minute: "2-digit",
    ...(precision === "seconds" ? { second: "2-digit" } : {}),
  });
}

function setLatest(reading) {
  document.getElementById("ambient-temperature").textContent = formatValue(
    reading?.ambient_temperature,
    "°"
  );
  document.getElementById("humidity").textContent = formatValue(reading?.humidity, "%");
  document.getElementById("kiln-temperature").textContent = formatValue(
    reading?.kiln_temperature,
    "°"
  );
  document.getElementById("source").textContent = reading?.source || "source";
  document.getElementById("last-seen").textContent = formatTime(reading?.timestamp);
  document.getElementById("status").textContent = reading
    ? `Останнє оновлення ${formatTime(reading.timestamp)}`
    : "Дані ще не зібрані";
  document.getElementById("display-crop").src = `/static/latest-display.jpg?t=${Date.now()}`;
}

function drawChart(canvas, readings, options = {}) {
  const ctx = canvas.getContext("2d");
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
  canvas.width = Math.floor(width * ratio);
  canvas.height = Math.floor(height * ratio);
  ctx.scale(ratio, ratio);
  ctx.clearRect(0, 0, width, height);

  const padding = { top: 20, right: 98, bottom: 46, left: 58 };
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const activeSeries = series.filter((item) => visibleSeries.has(item.field));
  const ranges = Object.fromEntries(activeSeries.map((item) => [item.field, getRange(readings, item)]));

  drawGrid(ctx, width, height, padding);
  drawTimeAxis(ctx, readings, width, height, padding, options.timeFormat || "seconds");
  drawAxes(ctx, height, padding, ranges, activeSeries);

  if (activeSeries.length === 0) {
    ctx.fillStyle = "#7e8984";
    ctx.font = "14px system-ui";
    ctx.fillText("Всі лінії вимкнені", padding.left, padding.top + 28);
    return;
  }

  if (!activeSeries.some((item) => hasValues(readings, item.field))) {
    ctx.fillStyle = "#7e8984";
    ctx.font = "14px system-ui";
    ctx.fillText("Немає даних", padding.left, padding.top + 28);
    return;
  }

  activeSeries.forEach((item) =>
    drawSeries(ctx, readings, item, ranges[item.field], padding, plotWidth, plotHeight)
  );
}

function drawSeries(ctx, readings, config, range, padding, plotWidth, plotHeight) {
  const points = readings
    .map((reading, index) => {
      const value = reading[config.field];
      if (value === null || value === undefined || Number.isNaN(value)) {
        return null;
      }
      const x =
        padding.left + (readings.length <= 1 ? plotWidth : (index / (readings.length - 1)) * plotWidth);
      const y = padding.top + plotHeight - ((value - range.min) / (range.max - range.min)) * plotHeight;
      return { x, y };
    })
    .filter(Boolean);

  if (points.length === 0) {
    return;
  }

  ctx.strokeStyle = config.color;
  ctx.lineWidth = 2;
  ctx.beginPath();
  points.forEach((point, index) => {
    if (index === 0) {
      ctx.moveTo(point.x, point.y);
    } else {
      ctx.lineTo(point.x, point.y);
    }
  });
  ctx.stroke();

  const last = points[points.length - 1];
  ctx.fillStyle = config.color;
  ctx.beginPath();
  ctx.arc(last.x, last.y, 4, 0, Math.PI * 2);
  ctx.fill();
}

function drawGrid(ctx, width, height, padding) {
  const plotHeight = height - padding.top - padding.bottom;
  ctx.strokeStyle = "#29332f";
  ctx.lineWidth = 1;
  for (let i = 0; i <= 4; i += 1) {
    const y = padding.top + (plotHeight / 4) * i;
    ctx.beginPath();
    ctx.moveTo(padding.left, y);
    ctx.lineTo(width - padding.right, y);
    ctx.stroke();
  }
}

function drawTimeAxis(ctx, readings, width, height, padding, timeFormat) {
  const plotWidth = width - padding.left - padding.right;
  const plotHeight = height - padding.top - padding.bottom;
  const tickCount = Math.min(5, readings.length);
  if (tickCount === 0) {
    return;
  }

  ctx.strokeStyle = "#33403b";
  ctx.fillStyle = "#9fa9a4";
  ctx.font = "12px system-ui";
  ctx.textAlign = "center";
  ctx.textBaseline = "top";

  const usedIndexes = new Set();
  for (let tick = 0; tick < tickCount; tick += 1) {
    const index =
      tickCount === 1 ? 0 : Math.round((tick / (tickCount - 1)) * (readings.length - 1));
    if (usedIndexes.has(index)) {
      continue;
    }
    usedIndexes.add(index);

    const x = padding.left + (readings.length <= 1 ? plotWidth : (index / (readings.length - 1)) * plotWidth);
    const y = padding.top + plotHeight;
    ctx.beginPath();
    ctx.moveTo(x, padding.top);
    ctx.lineTo(x, y + 5);
    ctx.stroke();
    ctx.fillText(formatTime(readings[index]?.timestamp, timeFormat), x, y + 10);
  }

  ctx.textAlign = "left";
  ctx.textBaseline = "alphabetic";
}

function drawAxes(ctx, height, padding, ranges, activeSeries) {
  const plotHeight = height - padding.top - padding.bottom;
  activeSeries.forEach((item) => {
    const range = ranges[item.field];
    const x = axisX(item.axis, padding, ctx.canvas.clientWidth);
    ctx.fillStyle = item.color;
    ctx.font = "12px system-ui";
    ctx.textAlign = item.axis === "left" ? "right" : "left";
    ctx.fillText(formatAxisValue(range.max, item.unit), x, padding.top + 4);
    ctx.fillText(formatAxisValue(range.min, item.unit), x, padding.top + plotHeight);
  });
  ctx.textAlign = "left";
}

function axisX(axis, padding, width) {
  if (axis === "left") {
    return padding.left - 8;
  }
  if (axis === "right-inner") {
    return width - padding.right + 8;
  }
  return width - 44;
}

function getRange(readings, config) {
  const values = readings
    .map((reading) => reading[config.field])
    .filter((value) => value !== null && value !== undefined && !Number.isNaN(value));

  if (values.length === 0) {
    return { min: config.hardMin, max: Math.min(config.hardMax, config.hardMin + config.minSpan) };
  }

  let min = Math.min(...values);
  let max = Math.max(...values);
  const span = Math.max(max - min, config.minSpan);
  const center = (min + max) / 2;
  min = center - span / 2;
  max = center + span / 2;

  const padding = span * 0.12;
  min = Math.max(config.hardMin, min - padding);
  max = Math.min(config.hardMax, max + padding);

  if (max - min < config.minSpan) {
    max = Math.min(config.hardMax, min + config.minSpan);
  }
  return { min, max };
}

function hasValues(readings, field) {
  return readings.some((reading) => {
    const value = reading[field];
    return value !== null && value !== undefined && !Number.isNaN(value);
  });
}

function formatAxisValue(value, unit) {
  return `${Math.round(value)}${unit === "%" ? "%" : "°"}`;
}

async function refresh() {
  if (document.hidden) {
    return;
  }
  const [readingsResponse, minuteResponse] = await Promise.all([
    fetch("/api/readings", { cache: "no-store" }),
    fetch("/api/readings/minutely", { cache: "no-store" }),
  ]);
  const readings = await readingsResponse.json();
  const minuteReadings = await minuteResponse.json();
  const visible = readings.slice(-120);
  const visibleMinutes = minuteReadings.slice(-180);
  setLatest(visible.at(-1));
  drawChart(document.getElementById("readings-chart"), visible);
  drawChart(document.getElementById("minute-chart"), visibleMinutes, { timeFormat: "minutes" });
}

function setupLegend() {
  document.querySelectorAll("[data-series]").forEach((button) => {
    const field = button.dataset.series;
    button.classList.toggle("active", visibleSeries.has(field));
    button.setAttribute("aria-pressed", visibleSeries.has(field) ? "true" : "false");
    button.addEventListener("click", () => {
      if (visibleSeries.has(field)) {
        visibleSeries.delete(field);
      } else {
        visibleSeries.add(field);
      }
      localStorage.setItem("kiln-visible-series", JSON.stringify([...visibleSeries]));
      button.classList.toggle("active", visibleSeries.has(field));
      button.setAttribute("aria-pressed", visibleSeries.has(field) ? "true" : "false");
      refresh();
    });
  });
}

setupLegend();
refresh().catch(() => {
  document.getElementById("status").textContent = "Не вдалося отримати дані";
});
setInterval(() => {
  if (document.hidden) {
    return;
  }
  refresh().catch(() => {
    document.getElementById("status").textContent = "Не вдалося отримати дані";
  });
}, 3000);
window.addEventListener("resize", refresh);
document.addEventListener("visibilitychange", () => {
  if (!document.hidden) {
    refresh().catch(() => {
      document.getElementById("status").textContent = "Не вдалося отримати дані";
    });
  }
});
