const API_BASE = "";

/* ============================================================
   Mode indicator (online / offline)
   ============================================================ */
async function updateModeIndicator() {
  const dot = document.getElementById("modeDot");
  const text = document.getElementById("modeText");
  try {
    const res = await fetch(`${API_BASE}/api/status`);
    const data = await res.json();
    if (data.ai_mode === "online") {
      dot.className = "mode-dot online";
      text.textContent = "Online · Granite AI";
    } else {
      dot.className = "mode-dot offline";
      text.textContent = "Offline · Local AI";
    }
  } catch (e) {
    dot.className = "mode-dot";
    text.textContent = "Server unreachable";
  }
}
updateModeIndicator();
setInterval(updateModeIndicator, 15000);

/* ============================================================
   Scan flow: choose photo -> preview -> verify -> seal reveal
   ============================================================ */
const dropZone = document.getElementById("dropZone");
const imageInput = document.getElementById("imageInput");
const chooseBtn = document.getElementById("chooseBtn");
const scanBtn = document.getElementById("scanBtn");
const previewEmpty = document.getElementById("previewEmpty");
const previewImg = document.getElementById("previewImg");
const scanLoading = document.getElementById("scanLoading");
const sealSection = document.getElementById("sealSection");

chooseBtn.addEventListener("click", () => imageInput.click());
dropZone.addEventListener("click", () => imageInput.click());

imageInput.addEventListener("change", () => {
  if (!imageInput.files.length) return;
  const file = imageInput.files[0];
  const url = URL.createObjectURL(file);
  previewImg.src = url;
  previewImg.classList.remove("hidden");
  previewEmpty.classList.add("hidden");
  scanBtn.disabled = false;
});

scanBtn.addEventListener("click", async () => {
  if (!imageInput.files.length) return;

  const formData = new FormData();
  formData.append("image", imageInput.files[0]);

  sealSection.classList.add("hidden");
  scanLoading.classList.remove("hidden");
  scanBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/scan`, { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.detail || "Scan failed");
    }
    const data = await res.json();
    renderSeal(data.result);
    loadHistory();
    loadStats();
  } catch (e) {
    alert(`Scan error: ${e.message}`);
  } finally {
    scanLoading.classList.add("hidden");
    scanBtn.disabled = false;
  }
});

function verdictClass(verdict) {
  if (verdict === "Likely Genuine") return "";
  if (verdict === "Likely Counterfeit") return "verdict-fake";
  return "verdict-caution";
}

function renderSeal(result) {
  const seal = document.getElementById("sealBadge");
  const scoreEl = document.getElementById("sealScore");
  const label = document.getElementById("verdictLabel");
  const matched = document.getElementById("matchedMedicine");
  const reasonsList = document.getElementById("reasonsList");

  const cls = verdictClass(result.verdict);

  seal.classList.remove("verdict-fake", "verdict-caution");
  if (cls) seal.classList.add(cls);
  seal.style.animation = "none";
  void seal.offsetWidth;
  seal.style.animation = "";

  scoreEl.textContent = result.trust_score;
  label.textContent = result.verdict;
  label.className = "verdict-label " + cls;

  matched.textContent = result.matched_medicine
    ? `${result.matched_medicine.name} — ${result.matched_medicine.manufacturer} (${result.matched_medicine.certifying_body})`
    : "No confident match found in verified database.";

  reasonsList.innerHTML = "";
  (result.reasons || []).forEach((r) => {
    const li = document.createElement("li");
    li.textContent = r;
    reasonsList.appendChild(li);
  });

  sealSection.classList.remove("hidden");
  sealSection.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* ============================================================
   Chat
   ============================================================ */
const chatWindow = document.getElementById("chatWindow");
const chatInput = document.getElementById("chatInput");
const chatSendBtn = document.getElementById("chatSendBtn");

function appendChatBubble(text, sender, modeUsed) {
  const row = document.createElement("div");
  row.className = "chat-row " + (sender === "user" ? "user" : "ai");

  const avatar = document.createElement("div");
  avatar.className = "chat-avatar";
  avatar.textContent = sender === "user" ? "YOU" : "GR";

  const bubble = document.createElement("div");
  bubble.className = sender === "user" ? "chat-bubble-user" : "chat-bubble-ai";
  bubble.textContent = modeUsed ? `${text}  ·  ${modeUsed} mode` : text;

  row.appendChild(avatar);
  row.appendChild(bubble);
  chatWindow.appendChild(row);
  chatWindow.scrollTop = chatWindow.scrollHeight;
}

async function sendChat() {
  const query = chatInput.value.trim();
  if (!query) return;

  appendChatBubble(query, "user");
  chatInput.value = "";
  chatSendBtn.disabled = true;

  try {
    const res = await fetch(`${API_BASE}/api/chat`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || "Assistant error");
    appendChatBubble(data.answer, "ai", data.mode_used);
  } catch (e) {
    appendChatBubble(`Could not get a response: ${e.message}`, "ai");
  } finally {
    chatSendBtn.disabled = false;
  }
}

chatSendBtn.addEventListener("click", sendChat);
chatInput.addEventListener("keydown", (e) => { if (e.key === "Enter") sendChat(); });

/* ============================================================
   History (ledger list)
   ============================================================ */
function ledgerVerdictClass(verdict) {
  if (verdict === "Likely Genuine") return "v-genuine";
  if (verdict === "Likely Counterfeit") return "v-fake";
  return "v-caution";
}

async function loadHistory() {
  const historyList = document.getElementById("historyList");
  try {
    const res = await fetch(`${API_BASE}/api/history?limit=10`);
    const data = await res.json();
    if (!data.history.length) {
      historyList.innerHTML = '<div class="ledger-empty">No scans yet — verify a package above to begin the ledger.</div>';
      return;
    }
    historyList.innerHTML = "";
    data.history.forEach((h) => {
      const row = document.createElement("div");
      row.className = "ledger-row";
      row.innerHTML = `
        <span class="ledger-verdict ${ledgerVerdictClass(h.verdict)}">${h.verdict} · ${h.trust_score}/100</span>
        <span class="ledger-time">${new Date(h.scanned_at).toLocaleString()}</span>
      `;
      historyList.appendChild(row);
    });
  } catch (e) {
    historyList.innerHTML = '<div class="ledger-empty">Could not load ledger.</div>';
  }
}
loadHistory();

/* ============================================================
   Dashboard stats + charts
   ============================================================ */
let verdictChartInstance = null;
let trendChartInstance = null;

function animateCount(el, target) {
  const start = 0;
  const duration = 600;
  const startTime = performance.now();
  function tick(now) {
    const progress = Math.min(1, (now - startTime) / duration);
    el.textContent = Math.round(start + (target - start) * progress);
    if (progress < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

async function loadStats() {
  try {
    const res = await fetch(`${API_BASE}/api/stats`);
    const data = await res.json();

    animateCount(document.getElementById("statTotal"), data.total_scans || 0);
    document.getElementById("statAvg").textContent = data.average_score || 0;
    animateCount(document.getElementById("statFlagged"), data.flagged_count || 0);

    renderVerdictChart(data.verdict_breakdown || {});
    renderTrendChart(data.trend || []);
  } catch (e) {
    console.error("Could not load stats", e);
  }
}

function renderVerdictChart(breakdown) {
  const ctx = document.getElementById("verdictChart");
  const labels = Object.keys(breakdown);
  const values = Object.values(breakdown);

  const colorMap = {
    "Likely Genuine": "#2D6A4F",
    "Needs Verification": "#C08A2E",
    "Likely Counterfeit": "#A13D3D",
    "Unknown Product - Not in Verified Database": "#8C9A90",
  };
  const colors = labels.map((l) => colorMap[l] || "#8C9A90");

  if (verdictChartInstance) verdictChartInstance.destroy();

  if (!labels.length) {
    ctx.getContext("2d").clearRect(0, 0, ctx.width, ctx.height);
    return;
  }

  verdictChartInstance = new Chart(ctx, {
    type: "doughnut",
    data: {
      labels,
      datasets: [{ data: values, backgroundColor: colors, borderWidth: 0 }],
    },
    options: {
      plugins: {
        legend: { position: "bottom", labels: { font: { family: "IBM Plex Sans", size: 11 }, boxWidth: 10, padding: 12 } },
      },
      cutout: "62%",
    },
  });
}

function renderTrendChart(trend) {
  const ctx = document.getElementById("trendChart");

  if (trendChartInstance) trendChartInstance.destroy();

  if (!trend.length) {
    ctx.getContext("2d").clearRect(0, 0, ctx.width, ctx.height);
    return;
  }

  const labels = trend.map((_, i) => `#${i + 1}`);
  const scores = trend.map((t) => t.score);

  trendChartInstance = new Chart(ctx, {
    type: "line",
    data: {
      labels,
      datasets: [{
        data: scores,
        borderColor: "#1B4332",
        backgroundColor: "rgba(27,67,50,0.08)",
        fill: true,
        tension: 0.35,
        pointRadius: 3,
        pointBackgroundColor: "#C08A2E",
      }],
    },
    options: {
      plugins: { legend: { display: false } },
      scales: {
        y: { min: 0, max: 100, ticks: { font: { family: "IBM Plex Mono", size: 10 } } },
        x: { ticks: { font: { family: "IBM Plex Mono", size: 10 } } },
      },
    },
  });
}

loadStats();