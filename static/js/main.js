// ── State ──
let selectedFile = null;
let charts = {};

// ── File handling ──
const dropZone  = document.getElementById("drop-zone");
const fileInput = document.getElementById("file-input");

dropZone.addEventListener("dragover", (e) => {
  e.preventDefault();
  dropZone.classList.add("drag-over");
});
dropZone.addEventListener("dragleave", () => dropZone.classList.remove("drag-over"));
dropZone.addEventListener("drop", (e) => {
  e.preventDefault();
  dropZone.classList.remove("drag-over");
  const file = e.dataTransfer.files[0];
  if (file) handleFileSelect(file);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) handleFileSelect(fileInput.files[0]);
});

function handleFileSelect(file) {
  selectedFile = file;
  document.getElementById("file-name").textContent = file.name;
  document.getElementById("file-size").textContent = formatBytes(file.size);
  document.getElementById("file-selected").classList.remove("hidden");
  document.getElementById("trim-controls").classList.remove("hidden");
  document.getElementById("analyze-btn").classList.remove("hidden");
  document.getElementById("drop-zone").classList.add("opacity-50", "pointer-events-none");
  hideError();
}

function clearFile() {
  selectedFile = null;
  fileInput.value = "";
  document.getElementById("file-selected").classList.add("hidden");
  document.getElementById("trim-controls").classList.add("hidden");
  document.getElementById("analyze-btn").classList.add("hidden");
  document.getElementById("drop-zone").classList.remove("opacity-50", "pointer-events-none");
  document.getElementById("results").classList.add("hidden");
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

// ── Analysis ──
async function analyzeServe() {
  if (!selectedFile) return;

  // Show loading, hide button
  document.getElementById("analyze-btn").classList.add("hidden");
  document.getElementById("loading").classList.remove("hidden");
  document.getElementById("results").classList.add("hidden");
  hideError();

  // Animate progress bar through fake stages
  setProgress(10, "Uploading video...");
  await sleep(800);
  setProgress(30, "Running pose detection...");
  await sleep(1000);
  setProgress(55, "Extracting joint angles...");

  // Build form data
  const formData = new FormData();
  formData.append("video", selectedFile);

  const startFrame = document.getElementById("start-frame").value;
  const endFrame   = document.getElementById("end-frame").value;
  if (startFrame) formData.append("start_frame", startFrame);
  if (endFrame)   formData.append("end_frame",   endFrame);

  try {
    setProgress(70, "Analyzing mechanics...");

    const response = await fetch("/analyze", {
      method: "POST",
      body: formData,
    });

    setProgress(90, "Building charts...");
    await sleep(400);

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error || "Analysis failed.");
    }

    const data = await response.json();
    setProgress(100, "Done!");
    await sleep(300);

    renderResults(data);

  } catch (err) {
    showError(err.message);
    document.getElementById("loading").classList.add("hidden");
    document.getElementById("analyze-btn").classList.remove("hidden");
  }
}

function setProgress(pct, text) {
  document.getElementById("progress-bar").style.width  = pct + "%";
  document.getElementById("loading-text").textContent  = text;
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

// ── Render results ──
function renderResults(data) {
  document.getElementById("loading").classList.add("hidden");
  document.getElementById("results").classList.remove("hidden");
  document.getElementById("results").scrollIntoView({ behavior: "smooth", block: "start" });

  const { chart_data, summary, atp_benchmarks } = data;

  renderSummaryCards(summary, atp_benchmarks);
  renderCharts(chart_data, atp_benchmarks);
}

// ── Summary cards ──
function renderSummaryCards(summary, atp) {
  const container = document.getElementById("summary-cards");
  container.innerHTML = "";

  const cards = [
    {
      label:   "Avg Elbow Angle",
      value:   summary.r_elbow_avg + "°",
      sub:     `ATP avg: ${atp.r_elbow_angle.avg}°`,
      color:   getRangeColor(summary.r_elbow_avg, atp.r_elbow_angle.range_low, atp.r_elbow_angle.range_high),
      icon:    "💪",
    },
    {
      label:   "Peak Shoulder Angle",
      value:   summary.r_shoulder_max + "°",
      sub:     `ATP avg: ${atp.r_shoulder_angle.avg}°`,
      color:   getRangeColor(summary.r_shoulder_max, atp.r_shoulder_angle.range_low, atp.r_shoulder_angle.range_high),
      icon:    "🔄",
    },
    {
      label:   "Shoulder Tilt",
      value:   summary.shoulder_tilt_avg,
      sub:     `ATP avg: ${atp.shoulder_tilt.avg}`,
      color:   getRangeColor(summary.shoulder_tilt_avg, atp.shoulder_tilt.range_low, atp.shoulder_tilt.range_high),
      icon:    "📐",
    },
    {
      label:   "Frames Analyzed",
      value:   summary.frames_analyzed,
      sub:     `${summary.duration_sec}s of motion`,
      color:   "text-accent",
      icon:    "🎞️",
    },
  ];

  cards.forEach((card, i) => {
    const div = document.createElement("div");
    div.className = "bg-panel border border-border rounded-2xl p-5 fade-up";
    div.style.animationDelay = (i * 0.1) + "s";
    div.innerHTML = `
      <div class="flex items-center justify-between mb-3">
        <span class="text-2xl">${card.icon}</span>
        <span class="text-xs text-slate-500 bg-slate-800 px-2 py-1 rounded-full">${card.sub}</span>
      </div>
      <p class="text-3xl font-bold ${card.color} mb-1">${card.value}</p>
      <p class="text-sm text-slate-400">${card.label}</p>
    `;
    container.appendChild(div);
  });
}

function getRangeColor(val, low, high) {
  if (val >= low && val <= high) return "text-green";
  if (val >= low * 0.9 && val <= high * 1.1) return "text-yellow";
  return "text-red";
}

// ── Charts ──
function renderCharts(data, atp) {
  const t = data.time;

  // Destroy existing charts if re-rendering
  Object.values(charts).forEach(c => c.destroy());
  charts = {};

  const chartDefaults = {
    responsive: true,
    plugins: {
      legend: { display: false },
      tooltip: {
        backgroundColor: "#1e293b",
        borderColor: "#334155",
        borderWidth: 1,
        titleColor: "#e2e8f0",
        bodyColor: "#94a3b8",
      },
    },
    scales: {
      x: {
        ticks:  { color: "#64748b", maxTicksLimit: 6 },
        grid:   { color: "#1e293b" },
        title:  { display: true, text: "Time (seconds)", color: "#64748b" },
      },
      y: {
        ticks: { color: "#64748b" },
        grid:  { color: "#334155" },
      },
    },
  };

  // Helper: make a dashed ATP average line dataset
  function atpLine(value, color) {
    return {
      label: "ATP avg",
      data: t.map(() => value),
      borderColor: color,
      borderWidth: 1.5,
      borderDash: [6, 4],
      pointRadius: 0,
      tension: 0,
    };
  }

  // Helper: make a player data dataset
  function playerLine(values, color) {
    return {
      label: "Your serve",
      data: values,
      borderColor: color,
      backgroundColor: color + "20",
      borderWidth: 2.5,
      pointRadius: 0,
      tension: 0.3,
      fill: true,
    };
  }

  // ── Elbow ──
  charts.elbow = new Chart(document.getElementById("chart-elbow"), {
    type: "line",
    data: {
      labels: t,
      datasets: [
        playerLine(data.r_elbow_angle, "#38bdf8"),
        atpLine(atp.r_elbow_angle.avg, "#38bdf880"),
      ],
    },
    options: {
      ...chartDefaults,
      plugins: {
        ...chartDefaults.plugins,
        legend: { display: true, labels: { color: "#94a3b8", boxWidth: 12 } },
      },
      scales: {
        ...chartDefaults.scales,
        y: { ...chartDefaults.scales.y, min: 100, max: 200,
             title: { display: true, text: "Degrees (°)", color: "#64748b" } },
      },
    },
  });

  // ── Shoulder ──
  charts.shoulder = new Chart(document.getElementById("chart-shoulder"), {
    type: "line",
    data: {
      labels: t,
      datasets: [
        playerLine(data.r_shoulder_angle, "#818cf8"),
        atpLine(atp.r_shoulder_angle.avg, "#818cf880"),
      ],
    },
    options: {
      ...chartDefaults,
      plugins: {
        ...chartDefaults.plugins,
        legend: { display: true, labels: { color: "#94a3b8", boxWidth: 12 } },
      },
      scales: {
        ...chartDefaults.scales,
        y: { ...chartDefaults.scales.y, min: 50, max: 200,
             title: { display: true, text: "Degrees (°)", color: "#64748b" } },
      },
    },
  });

  // ── Toss arm ──
  charts.toss = new Chart(document.getElementById("chart-toss"), {
    type: "line",
    data: {
      labels: t,
      datasets: [ playerLine(data.l_wrist_height, "#2a9d8f") ],
    },
    options: {
      ...chartDefaults,
      scales: {
        ...chartDefaults.scales,
        y: { ...chartDefaults.scales.y,
             title: { display: true, text: "Relative height", color: "#64748b" } },
      },
    },
  });

  // ── Shoulder tilt ──
  charts.tilt = new Chart(document.getElementById("chart-tilt"), {
    type: "line",
    data: {
      labels: t,
      datasets: [
        playerLine(data.shoulder_tilt, "#e9c46a"),
        atpLine(atp.shoulder_tilt.avg, "#e9c46a80"),
      ],
    },
    options: {
      ...chartDefaults,
      plugins: {
        ...chartDefaults.plugins,
        legend: { display: true, labels: { color: "#94a3b8", boxWidth: 12 } },
      },
      scales: {
        ...chartDefaults.scales,
        y: { ...chartDefaults.scales.y,
             title: { display: true, text: "Tilt value", color: "#64748b" } },
      },
    },
  });
}

// ── Error helpers ──
function showError(msg) {
  document.getElementById("error-msg").textContent = msg;
  document.getElementById("error-box").classList.remove("hidden");
}
function hideError() {
  document.getElementById("error-box").classList.add("hidden");
}