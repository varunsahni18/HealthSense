/* main.js — bootstraps charts + SSE + UI bindings + scenario buttons. */

const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

let LATEST_STATE = {};

// --------------------------- helpers ---------------------------
function setText(id, v)   { const e = document.getElementById(id); if (e) e.textContent = v; }
function setWidth(id, p)  { const e = document.getElementById(id); if (e) e.style.width = `${p}%`; }

function showAlert(msg, severity = "high") {
  const el = $("#alert-banner");
  el.textContent = msg;
  el.classList.add("show");
  el.style.background = severity === "high" ? "var(--red-500)" : "var(--amber-500)";
  setTimeout(() => el.classList.remove("show"), 5000);
}

function updateNetPill(state) {
  const pill = $("#net-pill");
  if ((state.bytes_to_cloud || 0) > 0) {
    pill.className = "pill pill-warn";
    pill.textContent = `● Cloud opt-in (${HSPrivacy.fmtBytes(state.bytes_to_cloud)})`;
  } else {
    pill.className = "pill pill-ok";
    pill.textContent = "● Local-Only (0 cloud bytes)";
  }
  const sp = $("#safety-pill");
  if (state.safety_active) {
    sp.className = "pill pill-bad";
    sp.textContent = "⚠ SAFETY PRE-EMPT ACTIVE";
  } else {
    sp.className = "pill pill-mute";
    sp.textContent = "Safety pre-empt OFF";
  }
}

function updateInferUI(s) {
  setText("v-hr",   s.heart_rate.toFixed(0));
  setText("v-hrv",  s.hrv_rmssd.toFixed(0));
  setText("v-spo2", s.spo2.toFixed(1));
  setText("v-resp", s.resp_rate.toFixed(0));
  setText("badge-lat", s.last_latency_ms.toFixed(1));
  setText("badge-mj",  s.last_energy_mj.toFixed(1));
  setText("badge-n",   s.inference_count);

  // Cardiac
  const cardEl = $(".card-cardiac");
  cardEl.classList.remove("warn", "crit");
  if (s.cardiac_severity > 0.7) cardEl.classList.add("crit");
  else if (s.cardiac_severity > 0.4) cardEl.classList.add("warn");
  setText("h-cardiac", s.cardiac_label);
  setText("h-cardiac-conf", `confidence ${(s.cardiac_conf * 100).toFixed(0)}%  ·  severity ${(s.cardiac_severity * 100).toFixed(0)}%`);
  setWidth("h-cardiac-bar", s.cardiac_severity * 100);

  // Sleep
  setText("h-sleep", s.sleep_stage);
  setText("h-sleep-conf", `confidence ${(s.sleep_conf * 100).toFixed(0)}%`);

  // Stress
  setText("h-stress",
    `${s.stress_level < 0.35 ? "low" : (s.stress_level < 0.65 ? "moderate" : "high")} (${(s.stress_level * 100).toFixed(0)}%)`);
  setWidth("h-stress-bar", s.stress_level * 100);

  // EEG
  setText("h-eeg", s.eeg_label);
  setText("h-eeg-conf", `confidence ${(s.eeg_conf * 100).toFixed(0)}%`);
}

function updateBioTrain(s) {
  setWidth("biotrain-bar", s.train_progress * 100);
  if (s.personalised) {
    setText("biotrain-status", "personalised");
    setText("f1-after", s.stress_f1.toFixed(2));
  } else if (s.train_progress > 0) {
    setText("biotrain-status", `${(s.baseline_pct).toFixed(0)}% baseline · training ${(s.train_progress * 100).toFixed(0)}%`);
  }
}

// --------------------------- API ---------------------------
async function setScenario(name) {
  $$(".sc-btn").forEach(b => b.classList.toggle("active", b.dataset.sc === name));
  await fetch("/api/scenario", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ type: name }),
  });
}

async function startBaseline() {
  $("#btn-baseline").disabled = true;
  setText("biotrain-status", "capturing baseline…");
  await fetch("/api/personalize/start", { method: "POST" });
  // re-enable run button after 8 s (baseline duration)
  setTimeout(() => { $("#btn-finetune").disabled = false; }, 8200);
}

async function runFineTune() {
  $("#btn-finetune").disabled = true;
  setText("biotrain-status", "running BioTrain on-device…");
  await fetch("/api/personalize/run", { method: "POST" });
}

async function callClinician() {
  const optIn = $("#opt-in").checked;
  const r = await fetch("/api/cloud/clinician", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ opt_in: optIn }),
  });
  const data = await r.json();
  if (!data.sent) {
    $("#cloud-result").textContent = "Tick opt-in first — no bytes sent.";
  } else {
    $("#cloud-result").innerHTML =
      `Sent <b>${HSPrivacy.fmtBytes(data.bytes)}</b> to cloud.<br>` +
      `Payload: ${JSON.stringify(data.payload).slice(0, 100)}…<br>` +
      `Cloud reply: <i>${data.explanation.slice(0, 180)}</i>`;
  }
  refreshState();
}

async function exportSession() {
  const r = await fetch("/api/session/export", { method: "POST" });
  const data = await r.json();
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)],
    { type: "application/json" }));
  const a = document.createElement("a");
  a.href = url;
  a.download = `healthsense-session-${Date.now()}.json`;
  a.click();
}

async function reExplain() {
  const r = await fetch("/api/explain", { method: "POST" });
  const d = await r.json();
  $("#explain-card").textContent = d.msg;
}

async function refreshState() {
  const r = await fetch("/api/state");
  LATEST_STATE = await r.json();
  updateInferUI(LATEST_STATE);
  updateBioTrain(LATEST_STATE);
  updateNetPill(LATEST_STATE);
  HSPrivacy.refreshEgressUI(LATEST_STATE);
}

// --------------------------- bind ---------------------------
function bind() {
  $$(".sc-btn").forEach(b => b.addEventListener("click", () => setScenario(b.dataset.sc)));
  $("#btn-baseline").addEventListener("click", startBaseline);
  $("#btn-finetune").addEventListener("click", runFineTune);
  $("#btn-clinician").addEventListener("click", callClinician);
  $("#btn-export").addEventListener("click", exportSession);
  $("#btn-explain").addEventListener("click", reExplain);
}

// --------------------------- redraw loop ---------------------------
let needsRedraw = false;
let waveformCount = 0;
function redrawLoop() {
  // Always redraw at ~30 fps once we've received any data; cheap.
  if (needsRedraw || waveformCount > 0) {
    HealthSenseCharts.redrawAll();
    needsRedraw = false;
  }
  requestAnimationFrame(redrawLoop);
}

// --------------------------- boot ---------------------------
window.addEventListener("DOMContentLoaded", () => {
  HealthSenseCharts.initCharts();
  bind();
  refreshState();
  setInterval(refreshState, 1500);
  redrawLoop();
  HSStream.on("conn",      () => { $("#conn-pill").className = "pill pill-ok"; $("#conn-pill").textContent = "SSE connected"; });
  HSStream.on("error",     () => { $("#conn-pill").className = "pill pill-bad"; $("#conn-pill").textContent = "SSE disconnected"; });
  HSStream.on("waveform",  (p) => {
    waveformCount++;
    HealthSenseCharts.pushFrame(p);
    needsRedraw = true;
    if (waveformCount === 1) console.log("[HealthSense] first waveform frame received");
  });
  HSStream.on("ALERT",     (a) => { showAlert(a.msg, a.level || "high"); });
  HSStream.on("INFER_RESULT", (r) => {
    if (r && r.model) {
      const badge = document.getElementById("badge-model");
      if (badge) badge.textContent = r.model === "onnx_1dcnn" ? "ONNX 1D-CNN" : "Heuristic";
    }
    // re-explain on every new label
    if (r && r.cardiac_label) {
      // local heuristic explainer for snappy UI
      const map = {
        "Sinus rhythm": "Heart rhythm normal. All clear.",
        "Sinus tachycardia": "Heart rate elevated, rhythm regular. Try slow breathing for 60 seconds.",
        "Atrial fibrillation": "Irregular rhythm consistent with AFib. Sit down and breathe slowly. If it persists 30+ min, contact your doctor.",
        "Ventricular tachycardia": "WARNING: ventricular tachycardia detected. Sit or lie down NOW. If you feel chest pain or faintness, call emergency services.",
        "Sinus bradycardia": "Heart rate low but rhythm normal. Sit if light-headed.",
      };
      $("#explain-card").textContent = map[r.cardiac_label] || `Detected: ${r.cardiac_label}.`;
    }
  });
  HSStream.start();

  $("#port-display").textContent = window.location.port || "5000";
});
