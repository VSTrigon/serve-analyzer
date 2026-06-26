// ── State ──
let selectedFile = null;
let charts = {};
let videoFPS = 30;
let videoDuration = 0;

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
  if (e.dataTransfer.files[0]) handleFileSelect(e.dataTransfer.files[0]);
});
fileInput.addEventListener("change", () => {
  if (fileInput.files[0]) handleFileSelect(fileInput.files[0]);
});

function handleFileSelect(file) {
  selectedFile = file;
  document.getElementById("file-name").textContent = file.name;
  document.getElementById("file-size").textContent = formatBytes(file.size);
  document.getElementById("file-selected").classList.add("visible");
  document.getElementById("drop-zone").style.opacity = "0.4";
  document.getElementById("drop-zone").style.pointerEvents = "none";
  hideError();
  initTrimmer(file);
}

function clearFile() {
  selectedFile = null;
  fileInput.value = "";
  window._previewFilename = null;
  document.getElementById("file-selected").classList.remove("visible");
  document.getElementById("preview-wrap").classList.remove("visible");
  document.getElementById("trim-wrap").classList.remove("visible");
  document.getElementById("analyze-btn").classList.remove("visible");
  document.getElementById("drop-zone").style.opacity = "";
  document.getElementById("drop-zone").style.pointerEvents = "";
  document.getElementById("results-section").classList.remove("visible");
  hideError();
}

function formatBytes(bytes) {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
  return (bytes / (1024 * 1024)).toFixed(1) + " MB";
}

// ── Trimmer ──
function initTrimmer(file) {
  const video = document.getElementById("preview-video");

  const previewData = new FormData();
  previewData.append("video", file);

  fetch("/upload_preview", { method: "POST", body: previewData })
    .then(res => res.json())
    .then(data => {
      if (data.preview_url) {
        video.src = data.preview_url;
        window._previewFilename = data.filename;
        document.getElementById("preview-wrap").classList.add("visible");
      }
    })
    .catch(() => {
      // If preview upload fails, still show sliders
      document.getElementById("preview-wrap").classList.remove("visible");
    });

  video.addEventListener("loadedmetadata", () => {
    videoDuration = video.duration;

    const name = file.name.toLowerCase();
    if      (name.includes("240")) videoFPS = 240;
    else if (name.includes("120")) videoFPS = 120;
    else if (name.includes("60"))  videoFPS = 60;
    else                           videoFPS = 30;

    const startSlider = document.getElementById("start-slider");
    const endSlider   = document.getElementById("end-slider");

    startSlider.max   = videoDuration;
    startSlider.value = 0;
    endSlider.max     = videoDuration;
    endSlider.value   = videoDuration;

    updateTrimLabels(0, videoDuration);

    document.getElementById("trim-wrap").classList.add("visible");
    document.getElementById("analyze-btn").classList.add("visible");
  });

  // If metadata never fires (some formats), still show button
  setTimeout(() => {
    document.getElementById("analyze-btn").classList.add("visible");
  }, 3000);
}

function onStartSlider(val) {
  val = parseFloat(val);
  const endVal = parseFloat(document.getElementById("end-slider").value);
  if (val >= endVal) {
    val = endVal - 0.1;
    document.getElementById("start-slider").value = val;
  }
  const video = document.getElementById("preview-video");
  if (video.readyState >= 1) video.currentTime = val;
  updateTrimLabels(val, endVal);
}

function onEndSlider(val) {
  val = parseFloat(val);
  const startVal = parseFloat(document.getElementById("start-slider").value);
  if (val <= startVal) {
    val = startVal + 0.1;
    document.getElementById("end-slider").value = val;
  }
  const video = document.getElementById("preview-video");
  if (video.readyState >= 1) video.currentTime = val;
  updateTrimLabels(startVal, val);
}

function updateTrimLabels(startSec, endSec) {
  const startFrame = Math.round(startSec * videoFPS);
  const endFrame   = Math.round(endSec   * videoFPS);
  const duration   = (endSec - startSec).toFixed(2);

  document.getElementById("start-time-label").textContent =
    `${startSec.toFixed(2)}s — frame ${startFrame}`;
  document.getElementById("end-time-label").textContent =
    `${endSec.toFixed(2)}s — frame ${endFrame}`;
  document.getElementById("trim-summary").textContent =
    `${startSec.toFixed(2)}s → ${endSec.toFixed(2)}s  (${duration}s)`;

  document.getElementById("start-frame").value = startFrame;
  document.getElementById("end-frame").value   = endFrame;
}

// ── Analysis ──
async function analyzeServe() {
  if (!selectedFile) return;

  showLoading(10, "UPLOADING", "sending video to server...");
  document.getElementById("analyze-btn").classList.remove("visible");
  document.getElementById("results-section").classList.remove("visible");
  hideError();

  const formData = new FormData();
  if (window._previewFilename) {
    formData.append("preview_filename", window._previewFilename);
  } else {
    formData.append("video", selectedFile);
  }

  const startFrame = document.getElementById("start-frame").value;
  const endFrame   = document.getElementById("end-frame").value;
  if (startFrame) formData.append("start_frame", startFrame);
  if (endFrame)   formData.append("end_frame",   endFrame);

  try {
    await sleep(600);
    setLoading(30, "DETECTING", "running mediapipe pose detection...");
    await sleep(800);
    setLoading(55, "EXTRACTING", "computing joint angles per frame...");

    const response = await fetch("/analyze", {
      method: "POST",
      body: formData,
    });

    setLoading(80, "ANALYZING", "building your results...");
    await sleep(500);

    if (!response.ok) {
      const err = await response.json();
      throw new Error(err.error || "Analysis failed.");
    }

    const data = await response.json();
    setLoading(100, "COMPLETE", "rendering charts...");
    await sleep(400);

    hideLoading();
    renderResults(data);

  } catch (err) {
    hideLoading();
    showError(err.message);
    document.getElementById("analyze-btn").classList.add("visible");
  }
}

// ── Loading overlay ──
function showLoading(pct, stage, text) {
  document.getElementById("loading-overlay").classList.add("visible");
  setLoading(pct, stage, text);
}
function setLoading(pct, stage, text) {
  document.getElementById("loading-bar").style.width   = pct + "%";
  document.getElementById("loading-stage").textContent = stage;
  document.getElementById("loading-text").textContent  = text;
}
function hideLoading() {
  document.getElementById("loading-overlay").classList.remove("visible");
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

// ── Render results ──
function renderResults(data) {
  const section = document.getElementById("results-section");
  section.classList.add("visible");
  section.scrollIntoView({ behavior: "smooth", block: "start" });

  const { chart_data, summary, atp_benchmarks } = data;

  renderSummaryCards(summary, atp_benchmarks);
  renderCharts(chart_data, atp_benchmarks);
}

// ── Summary cards ──
function renderSummaryCards(summary, atp) {
  const grid = document.getElementById("summary-grid");
  grid.innerHTML = "";

  const cards = [
    {
      icon:  "💪",
      val:   summary.r_elbow_avg + "°",
      label: "Avg Elbow Angle",
      atp:   `ATP avg: ${atp.r_elbow_angle.avg}°`,
      color: getRangeColor(summary.r_elbow_avg, atp.r_elbow_angle.range_low, atp.r_elbow_angle.range_high),
    },
    {
      icon:  "🔄",
      val:   summary.r_shoulder_max + "°",
      label: "Peak Shoulder",
      atp:   `ATP avg: ${atp.r_shoulder_angle.avg}°`,
      color: getRangeColor(summary.r_shoulder_max, atp.r_shoulder_angle.range_low, atp.r_shoulder_angle.range_high),
    },
    {
      icon:  "📐",
      val:   summary.shoulder_tilt_avg,
      label: "Shoulder Tilt",
      atp:   `ATP avg: ${atp.shoulder_tilt.avg}`,
      color: getRangeColor(summary.shoulder_tilt_avg, atp.shoulder_tilt.range_low, atp.shoulder_tilt.range_high),
    },
    {
      icon:  "🎞",
      val:   summary.frames_analyzed,
      label: "Frames analyzed",
      atp:   `${summary.duration_sec}s window`,
      color: "ok",
    },
  ];

  cards.forEach((card, i) => {
    const div = document.createElement("div");
    div.className = "summary-card";
    div.innerHTML = `
      <div class="card-icon">${card.icon}</div>
      <div class="card-val ${card.color}">${card.val}</div>
      <div class="card-label">${card.label}</div>
      <div class="card-atp">${card.atp}</div>
    `;
    grid.appendChild(div);

    // Staggered reveal
    setTimeout(() => div.classList.add("revealed"), i * 100);
  });
}

function getRangeColor(val, low, high) {
  if (val >= low && val <= high)               return "good";
  if (val >= low * 0.93 && val <= high * 1.07) return "ok";
  return "off";
}

// ── Charts ──
function renderCharts(data, atp) {
  Object.values(charts).forEach(c => c.destroy());
  charts = {};

  const t = data.time;

  const baseOptions = {
    responsive: true,
    animation: { duration: 1200, easing: "easeInOutQuart" },
    plugins: {
      legend: {
        display: true,
        labels: { color: "#666", boxWidth: 10, font: { size: 11, family: "'JetBrains Mono'" } },
      },
      tooltip: {
        backgroundColor: "#1A1A1A",
        borderColor: "#2A2A2A",
        borderWidth: 1,
        titleColor: "#F0F0F0",
        bodyColor: "#666",
        titleFont: { family: "'JetBrains Mono'", size: 11 },
      },
    },
    scales: {
      x: {
        ticks: { color: "#444", maxTicksLimit: 5, font: { size: 10, family: "'JetBrains Mono'" } },
        grid:  { color: "#1A1A1A" },
        title: { display: true, text: "seconds", color: "#444", font: { size: 10 } },
      },
      y: {
        ticks: { color: "#444", font: { size: 10, family: "'JetBrains Mono'" } },
        grid:  { color: "#1F1F1F" },
      },
    },
  };

  function playerDataset(values, color, label = "Your serve") {
    return {
      label,
      data: values,
      borderColor: color,
      backgroundColor: color + "15",
      borderWidth: 2,
      pointRadius: 0,
      tension: 0.4,
      fill: true,
    };
  }

  function atpDataset(value, color, label = "ATP avg") {
    return {
      label,
      data: t.map(() => value),
      borderColor: color + "60",
      borderWidth: 1,
      borderDash: [5, 4],
      pointRadius: 0,
      tension: 0,
      fill: false,
    };
  }

  // Elbow
  charts.elbow = new Chart(document.getElementById("chart-elbow"), {
    type: "line",
    data: { labels: t, datasets: [
      playerDataset(data.r_elbow_angle, "#C8F000"),
      atpDataset(atp.r_elbow_angle.avg, "#C8F000"),
    ]},
    options: { ...baseOptions, scales: { ...baseOptions.scales,
      y: { ...baseOptions.scales.y, min: 80, max: 200,
           title: { display: true, text: "degrees", color: "#444", font: { size: 10 } } },
    }},
  });

  // Shoulder
  charts.shoulder = new Chart(document.getElementById("chart-shoulder"), {
    type: "line",
    data: { labels: t, datasets: [
      playerDataset(data.r_shoulder_angle, "#00CC88"),
      atpDataset(atp.r_shoulder_angle.avg, "#00CC88"),
    ]},
    options: { ...baseOptions, scales: { ...baseOptions.scales,
      y: { ...baseOptions.scales.y, min: 40, max: 200,
           title: { display: true, text: "degrees", color: "#444", font: { size: 10 } } },
    }},
  });

  // Toss
  charts.toss = new Chart(document.getElementById("chart-toss"), {
    type: "line",
    data: { labels: t, datasets: [
      playerDataset(data.l_wrist_height, "#818CF8", "Toss height"),
    ]},
    options: { ...baseOptions, plugins: { ...baseOptions.plugins, legend: { display: false } },
      scales: { ...baseOptions.scales,
        y: { ...baseOptions.scales.y,
             title: { display: true, text: "relative height", color: "#444", font: { size: 10 } } },
    }},
  });

  // Tilt
  charts.tilt = new Chart(document.getElementById("chart-tilt"), {
    type: "line",
    data: { labels: t, datasets: [
      playerDataset(data.shoulder_tilt, "#FF8C42"),
      atpDataset(atp.shoulder_tilt.avg, "#FF8C42"),
    ]},
    options: { ...baseOptions, scales: { ...baseOptions.scales,
      y: { ...baseOptions.scales.y,
           title: { display: true, text: "tilt value", color: "#444", font: { size: 10 } } },
    }},
  });

  // Reveal chart cards with stagger
  ["card-elbow","card-shoulder","card-toss","card-tilt"].forEach((id, i) => {
    setTimeout(() => document.getElementById(id).classList.add("revealed"), 300 + i * 150);
  });
}

// ── Error helpers ──
function showError(msg) {
  const box = document.getElementById("error-box");
  document.getElementById("error-msg").textContent = msg;
  box.classList.add("visible");
}
function hideError() {
  document.getElementById("error-box").classList.remove("visible");
}