const SC_HINT = {
  0: "Free run — mild distance wander, two vehicles on the map.",
  1: "Scenario 1 — normal conditions: low fog, safe distance, green.",
  2: "Scenario 2 — fog: humidity/darkness/camera drop → FOG SAFETY MODE, REDUCE SPEED.",
  3: "Scenario 3 — obstacle ahead: LiDAR range falls, warning then crawl/stop advice.",
  4: "Scenario 4 — thermal cluster + mmWave → HIGH CONFIDENCE PRESENCE.",
  5: "Scenario 5 — LiDAR under 1.5 m or US under 1.0 m: cab buzzer + DANGER. Above those, no DANGER label.",
};

function fmtM(m, empty) {
  if (m === null || m === undefined || Number.isNaN(Number(m))) return empty || "—";
  return `${Number(m).toFixed(2)} m`;
}

const map = L.map("map", { zoomControl: true }).setView([18.72, 81.23], 14);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
  maxZoom: 18,
  attribution: "&copy; OpenStreetMap",
}).addTo(map);

const markers = {};
const riskHist = [];
const fogHist = [];
let chart;
let activeSc = 1;

function colorFor(level) {
  const l = (level || "").toUpperCase();
  if (l.includes("UNKNOWN")) return "#8aa0b5";
  if (l.includes("DANGER") || l.includes("CRITICAL")) return "#ff4d4f";
  if (l.includes("HIGH")) return "#ff8a3d";
  if (l.includes("WARNING") || l.includes("CAUTION")) return "#f5c542";
  return "#3ddc84";
}

function zoneClass(z) {
  const l = (z || "").toUpperCase();
  if (l.includes("DANGER")) return "danger";
  if (l.includes("WARNING")) return "warn";
  if (l.includes("UNKNOWN")) return "offline";
  return "";
}

function isDangerHud(v) {
  const z = [v.front_zone, v.left_zone, v.right_zone, v.local_zone, v.cab_zone, v.risk_level]
    .map((x) => String(x || "").toUpperCase());
  return z.some((s) => s.includes("DANGER") || s.includes("CRITICAL"));
}

function paintRange(id, zid, metres, zone, emptyLabel) {
  document.getElementById(id).textContent = fmtM(metres, emptyLabel);
  document.getElementById(zid).textContent = zone || "—";
  document.getElementById(zid).style.color = colorFor(zone);
  const box = document.getElementById(id).parentElement;
  box.classList.remove("warn", "danger", "offline");
  const c = zoneClass(zone);
  if (c) box.classList.add(c);
}

function setArc(score, color) {
  const path = document.getElementById("arcFill");
  const len = 173;
  const off = len * (1 - Math.min(100, Math.max(0, score)) / 100);
  path.style.stroke = color;
  path.style.strokeDasharray = String(len);
  path.style.strokeDashoffset = String(off);
}

function drawHeat(grid) {
  const c = document.getElementById("heat");
  const ctx = c.getContext("2d");
  ctx.fillStyle = "#07090c";
  ctx.fillRect(0, 0, c.width, c.height);
  if (!grid || !grid.length) return;
  const rows = grid.length;
  const cols = grid[0].length;
  const cw = c.width / cols;
  const ch = c.height / rows;
  let min = 1e9, max = -1e9;
  for (const row of grid) for (const v of row) { min = Math.min(min, v); max = Math.max(max, v); }
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      const t = (grid[y][x] - min) / Math.max(0.5, max - min);
      const r = Math.round(20 + 235 * t);
      const g = Math.round(20 + 80 * (1 - t));
      const b = Math.round(90 * (1 - t));
      ctx.fillStyle = `rgb(${r},${g},${b})`;
      ctx.fillRect(x * cw, y * ch, cw + 0.5, ch + 0.5);
    }
  }
}

function ensureChart() {
  if (chart) return;
  const ctx = document.getElementById("chart");
  chart = new Chart(ctx, {
    type: "line",
    data: {
      labels: [],
      datasets: [
        { label: "Risk score", data: [], borderColor: "#ff8a3d", tension: 0.25, pointRadius: 0 },
        { label: "Fog index", data: [], borderColor: "#7aa2ff", tension: 0.25, pointRadius: 0 },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      scales: {
        x: { ticks: { color: "#8aa0b5", maxTicksLimit: 8 }, grid: { color: "#1c2733" } },
        y: { min: 0, max: 100, ticks: { color: "#8aa0b5" }, grid: { color: "#1c2733" } },
      },
      plugins: { legend: { labels: { color: "#c5d4e4" } } },
    },
  });
}

function applyPrimary(v) {
  const color = colorFor(v.risk_level);
  document.getElementById("hudTitle").textContent = `${v.vehicle_id} · operator HUD`;
  document.getElementById("riskNum").textContent = v.risk_score ?? "--";
  document.getElementById("riskLbl").textContent = v.risk_level || "—";
  setArc(v.risk_score || 0, color);
  document.getElementById("adviceMain").textContent = v.speed_advice || "—";
  document.getElementById("adviceMain").style.color = color;
  const tips = [];
  if (v.tilt_alert) tips.push("TILT ALERT");
  if (v.speed_advice === "CRAWL MODE") tips.push("crawl — obstacle nearby");
  if (v.temperature != null) tips.push(`${v.temperature} °C`);
  if (v.recommended_note) tips.push(v.recommended_note);
  if (!tips.length) tips.push("Operator remains in control");
  document.getElementById("adviceSub").textContent = tips.join(" · ");
  paintRange("dFront", "zFront", v.front_distance, v.front_zone, "—");
  paintRange("dLeft", "zLeft", v.left_distance, v.left_zone, v.left_sensor === "offline" ? "NC" : "—");
  paintRange("dRight", "zRight", v.right_distance, v.right_zone, v.right_sensor === "offline" ? "NC" : "—");
  document.getElementById("audioPat").textContent = v.audio || "off";
  const fw = v.firmware ? ` · hub ${v.firmware}` : "";
  const cab = v.cab_zone ? ` · cab ${v.cab_zone}` : "";
  document.getElementById("audioMeta").textContent = `buzzer ON if LiDAR < 1.5 m or US < 1.0 m${cab}${fw}`;
  const presence = v.presence || "CLEAR";
  const chip = document.getElementById("presenceChip");
  chip.textContent = presence;
  chip.classList.toggle("chip-presence", presence.includes("PRESENCE") && !presence.includes("HIGH"));
  chip.classList.toggle("chip-presence-hi", presence.includes("HIGH CONFIDENCE"));
  const presenceOn = !!(v.radar_occupied || v.motion_detected || (presence && presence !== "CLEAR"));
  document.getElementById("presenceBanner").classList.toggle("hidden", !presenceOn);
  document.getElementById("thermalNote").textContent = v.thermal_note || "—";
  const camEl = document.getElementById("camNote");
  if (camEl) {
    const src = v.vision_source || "—";
    const vis = v.visibility_label ? ` · ${v.visibility_label}` : "";
    camEl.textContent = (v.vision_note || src) + vis;
  }
  document.getElementById("fogBanner").classList.toggle("hidden", !v.fog_mode);

  const env = document.getElementById("envGrid");
  if (isDangerHud(v)) {
    env.innerHTML = [
      ["Operator view", "DANGER — weather / visibility hidden"],
      ["Watch", "LiDAR + left/right US only"],
      ["GPS", `${v.gps_status || "—"} · ${v.gps_sats ?? 0} sats`],
      ["Tilt", `${v.pitch_deg ?? "—"}° / ${v.roll_deg ?? "—"}°`],
    ].map(([k, val]) => `<div><span>${k}</span><strong>${val}</strong></div>`).join("");
  } else {
    env.innerHTML = [
      ["Temperature", (v.temperature ?? "—") + (v.temperature != null ? " °C" : "")],
      ["Humidity", (v.humidity ?? "—") + (v.humidity != null ? " %" : "")],
      ["Ambient light", v.light_level ?? "—"],
      ["Fog index", `${v.fog_index ?? "—"} · ${v.fog_label || ""}`],
      ["Visibility", `${v.visibility_label || "—"} (${v.visibility_confidence ?? "n/a"})`],
      ["Vision / thermal", `${v.vision_source || "—"} / ${v.thermal_source || "synth"}`],
      ["24 GHz radar", v.radar_occupied || v.motion_detected ? "HUMAN PRESENT" : "clear"],
      ["Presence", v.presence || "CLEAR"],
      ["GPS", `${v.gps_status || "—"} · ${v.gps_sats ?? 0} sats`],
      ["Pitch / roll", `${v.pitch_deg ?? "—"}° / ${v.roll_deg ?? "—"}°${v.tilt_alert ? " · TILT" : ""}`],
    ].map(([k, val]) => `<div><span>${k}</span><strong>${val}</strong></div>`).join("");
  }

  const notes = v.notes || [];
  document.getElementById("noteList").innerHTML = notes.length
    ? notes.map((n) => `<li>${n}</li>`).join("")
    : "<li>No fusion notes</li>";

  const t = new Date().toLocaleTimeString();
  riskHist.push(v.risk_score || 0);
  fogHist.push(v.fog_index || 0);
  if (riskHist.length > 60) { riskHist.shift(); fogHist.shift(); }
  ensureChart();
  chart.data.labels = riskHist.map((_, i) => i);
  chart.data.datasets[0].data = riskHist;
  chart.data.datasets[1].data = fogHist;
  chart.update("none");
}

function renderFleet(vehicles) {
  const box = document.getElementById("cards");
  box.innerHTML = vehicles.map((v) => `
    <div class="vcard" style="border-left-color:${colorFor(v.risk_level)}">
      <h3>${v.vehicle_id} ${v.is_peer ? "· V2V peer" : ""}</h3>
      <p>${v.risk_level || "—"} · ${v.speed_advice || ""} · fog ${v.fog_mode ? "ON" : "off"}</p>
      <p>front ${fmtM(v.front_distance)} · ${v.presence || ""}</p>
    </div>`).join("");

  for (const v of vehicles) {
    if (v.latitude == null || v.longitude == null) continue;
    const html = `<b>${v.vehicle_id}</b><br>${v.risk_level || ""}`;
    if (!markers[v.vehicle_id]) {
      markers[v.vehicle_id] = L.circleMarker([v.latitude, v.longitude], {
        radius: 9, color: colorFor(v.risk_level), fillColor: colorFor(v.risk_level), fillOpacity: 0.85, weight: 2,
      }).addTo(map).bindPopup(html);
    } else {
      markers[v.vehicle_id].setLatLng([v.latitude, v.longitude]);
      markers[v.vehicle_id].setStyle({ color: colorFor(v.risk_level), fillColor: colorFor(v.risk_level) });
      markers[v.vehicle_id].setPopupContent(html);
    }
  }
}

function renderAlerts(alerts) {
  const ul = document.getElementById("alertList");
  ul.innerHTML = (alerts || []).slice(0, 12).map((a) =>
    `<li class="${a.severity}"><b>${a.severity}</b> · ${a.message}<br><span class="hint">${a.timestamp || ""}</span></li>`
  ).join("") || "<li class='hint'>No alerts yet</li>";
}

async function onSnapshot(msg) {
  const espOk = msg.esp_link === true;
  const link = document.getElementById("linkBadge");
  if (espOk) {
    link.textContent = "ESP LINK OK";
    link.className = "badge live";
  } else {
    link.textContent = "ESP OFFLINE";
    link.className = "badge off";
  }
  document.getElementById("modeBadge").textContent = (msg.mode || "sim").toUpperCase();
  document.getElementById("clock").textContent = new Date().toLocaleString();
  const vehicles = msg.vehicles || [];
  const primary = vehicles.find((v) => !v.is_peer) || vehicles[0];
  if (primary) applyPrimary(primary);
  renderFleet(vehicles);
  renderAlerts(msg.alerts);
  if (msg.heatmap) drawHeat(msg.heatmap);
  const camEl = document.getElementById("camNote");
  if (camEl && msg.vision_note) {
    camEl.textContent = msg.vision_note + (msg.vision_source ? ` · ${msg.vision_source}` : "");
  }
}

function connect() {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws/fleet`);
  ws.onopen = () => {
    const link = document.getElementById("linkBadge");
    if (link.textContent === "LINK DOWN") {
      link.textContent = "WS OK";
      link.className = "badge live";
    }
  };
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.type === "fleet_snapshot") onSnapshot(msg);
  };
  ws.onclose = () => {
    document.getElementById("linkBadge").textContent = "LINK DOWN";
    document.getElementById("linkBadge").className = "badge off";
    setTimeout(connect, 1500);
  };
}

document.querySelectorAll(".demo-btns button").forEach((btn) => {
  btn.addEventListener("click", async () => {
    const sc = Number(btn.dataset.sc);
    activeSc = sc;
    document.querySelectorAll(".demo-btns button").forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    document.getElementById("scHint").textContent = SC_HINT[sc];
    await fetch("/api/v1/demo/scenario", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: sc }),
    });
  });
});

connect();
fetch("/api/v1/health")
  .then((r) => r.json())
  .then((h) => {
    const el = document.getElementById("lanHint");
    if (!el || !h.urls || !h.urls.length) return;
    el.textContent = "This Pi: " + h.urls.join("   ·   ");
  })
  .catch(() => {});
document.querySelector('.demo-btns button[data-sc="1"]').classList.add("active");

function drawCam(img) {
  const c = document.getElementById("cam");
  if (!c || !img.width) return;
  const ctx = c.getContext("2d");
  ctx.imageSmoothingEnabled = false;
  ctx.fillStyle = "#07090c";
  ctx.fillRect(0, 0, c.width, c.height);
  const scale = Math.min(c.width / img.width, c.height / img.height);
  const w = Math.max(1, img.width * scale);
  const h = Math.max(1, img.height * scale);
  ctx.drawImage(img, (c.width - w) / 2, (c.height - h) / 2, w, h);
}

const camImg = new Image();
let camBusy = false;
function refreshCam() {
  if (camBusy) return;
  camBusy = true;
  camImg.src = "/api/v1/camera.jpg?t=" + Date.now();
}
camImg.onload = () => {
  drawCam(camImg);
  camBusy = false;
  setTimeout(refreshCam, 60);
};
camImg.onerror = () => {
  camBusy = false;
  setTimeout(refreshCam, 400);
};
refreshCam();

async function clearAlerts() {
  try {
    await fetch("/api/v1/alerts/clear", { method: "POST" });
  } catch (e) { /* ignore */ }
  renderAlerts([]);
}
document.getElementById("presenceChip").addEventListener("click", clearAlerts);
document.getElementById("clearAlertsBtn").addEventListener("click", clearAlerts);
