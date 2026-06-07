# HealthSense — Implementation Plan

**SparQ 2026 | Track: Edge + Cloud AI by Industry — Healthcare | Idea #02**

> On-wearable multimodal biosignal AI with PanLUNA + BioTrain — zero raw biosignal egress.
> Reference paper: PanLUNA — *arXiv:2604.04297*; on-device fine-tune — *BioTrain, arXiv:2604.13359*.

---

## 1. Goals (judged against the official rubric)

| Rubric item | How HealthSense earns it |
|---|---|
| Innovation & Problem Relevance | First on-wearable multimodal biosignal foundation model demo on Snapdragon — fuses EEG+ECG+PPG+EMG+IMU in one encoder. Personalisation happens *on the device*, not in the cloud. |
| Real-world applicability | Continuous cardiac arrhythmia, sleep-stage, stress, and EEG abnormality screening on a smartwatch / chest patch — markets already worth >$60B (CGM, Holter, sleep, stress). |
| Technical Execution | INT8 PanLUNA on Hexagon NPU via Qualcomm AI Hub; full backprop on-device under 50 mW (BioTrain). |
| Code Quality | Clean Python/Flask backend mirroring CabinAI patterns; typed APIs; ZeroClaw-style pub/sub bus; ruff-clean. |
| Architecture quality | Edge-first: model on NPU, fine-tuner on CPU, optional clinician dashboard via QGenie cloud — *no raw biosignal ever leaves the device*. |
| Correct framework use | python-pptx, ReportLab, ONNX Runtime QNN-EP, Qualcomm AI Hub Compile/Profile/Deploy jobs, Flask + SSE. |
| On-device performance | 325.6 ms / 18.8 mJ per 12-lead ECG (paper's GAP9 baseline). Target on Snapdragon Hexagon: ≤100 ms, ≥17 samples/s for EEG. |
| Demo quality | Live biosignal stream → real-time multi-task classification overlay. Personalisation toggle that visibly improves accuracy in 30 s. |
| Completeness | Plan, PPT, speech notes, working backend skeleton, exportable session JSON, judging-criteria mapping. |

---

## 2. Architecture

```
┌─────────────────── ON-WEARABLE EDGE (Snapdragon W5 / X Elite / SA8775P) ─────────────────┐
│                                                                                          │
│  Sensor layer ────────────────────────────────────────────────────────────────────────  │
│   • EEG (1–8 ch, 250 Hz)        • EMG (4 ch, 1 kHz)                                     │
│   • ECG (1 / 12 lead, 500 Hz)   • IMU (6-DoF, 100 Hz)                                   │
│   • PPG (3 ch, 100 Hz)                                                                   │
│                                                                                          │
│  Pre-processing (CPU LITTLE cluster) ─────────────────────────────────────────────────  │
│   Bandpass, notch, resampling, segmentation into 4–10 s windows.                         │
│                                                                                          │
│  PanLUNA Encoder (Hexagon NPU, INT8) ─────────────────────────────────────────────────  │
│   5.4 M params · sensor-type embeddings · cross-modal Transformer.                       │
│   Heads: cardiac arrhythmia · sleep stage · stress · EEG abnormality.                    │
│                                                                                          │
│  BioTrain on-device fine-tuner (CPU big cluster) ─────────────────────────────────────  │
│   Full back-prop under 50 mW · 0.67 MB RAM · GroupNorm replacement · gradient            │
│   accumulation · compiler-driven tiling. +35 % personalisation gain.                     │
│                                                                                          │
│  ZeroClaw bus (pub/sub, thread-safe) ─────────────────────────────────────────────────  │
│   Topics: sensor.*, infer.*, alert.*, train.*. Safety pre-emption when                   │
│   alert.cardiac_severity > 0.7 (mirrors CabinAI safety pre-emption).                     │
│                                                                                          │
│  Local UI / TTS ──────────────────────────────────────────────────────────────────────  │
│   Kokoro-ONNX local TTS for spoken alerts; on-watch glanceable card.                     │
│                                                                                          │
└──────────────────────────────────────────────────────────────────────────────────────────┘
                              ↕  ONLY metadata + alerts (encrypted, opt-in)
┌─────────────────── OPTIONAL CLOUD (Hydra AIC100 / QGenie) ────────────────────────────────┐
│  • Clinician summary dashboard  (gpt-oss-20b explains the alert)                          │
│  • Federated weight delta upload (DP-SGD ε=8) — never raw signal                          │
└───────────────────────────────────────────────────────────────────────────────────────────┘
```

### 2.1 Why this beats the obvious "cloud ECG model" baseline
1. **Privacy** — raw EEG/ECG never leaves the wrist. HIPAA / GDPR-friendly by construction.
2. **Latency** — 100 ms wrist-to-alert vs 1–3 s cloud round-trip. Critical for arrhythmia.
3. **Battery** — 18.8 mJ/inference means ~weeks of continuous monitoring on a coin cell.
4. **Personalisation** — every wearer's baseline differs; on-device fine-tune captures it.

---

## 3. Module Breakdown (mirrors CabinAI 7-agent layout)

| Agent | Role | Backend | Latency | Where it runs |
|---|---|---|---|---|
| **A1 Perception** | Sensor ingest, filtering, windowing | numpy / scipy | <5 ms | CPU LITTLE |
| **A2 PanLUNA** | Multimodal foundation encoder + 4 heads | ONNX QNN-EP, INT8 | ~100 ms | Hexagon NPU |
| **A3 BioTrain** | On-device personalisation (LoRA-style) | Custom PyTorch loop, CPU | ~50 mW | CPU BIG |
| **A4 Edge LLM** | Local explanations of alerts | Ollama qwen2:7b (fallback to QGenie) | ~3 s | Local CPU / cloud fallback |
| **A5 Proactive** | 5-min trend forecaster (e.g. AFib likely in 15 min) | Qwen3-VL-32B via QGenie | async | Cloud (opt-in) |
| **A6 Complex** | Clinician Q&A, multi-turn coaching | gpt-oss-20b | async | Cloud (opt-in) |
| **A7 RAG** | Local cardiology / sleep guideline corpus | BGE-small ONNX + ChromaDB | <50 ms | CPU |

`Orchestrator/zeroclaw_bus.py` is reused verbatim from CabinAI; `query_router.py` is renamed to
`alert_router.py` with cardiac-severity > 0.7 as the new pre-emption trigger.

---

## 4. Repository Layout

```
healthsense/
├── .env                        # copied from cabinai
├── .venv312/                   # Junction → cabinai/.venv312
├── requirements.txt            # adds: pyedflib, mne, neurokit2, pywavelets
├── backend/
│   ├── server.py               # Flask + SSE (mirrors cabinai)
│   ├── config.py
│   ├── agents/
│   │   ├── a1_perception.py    # sensor preproc
│   │   ├── a2_panluna.py       # ONNX QNN-EP wrapper
│   │   ├── a3_biotrain.py      # on-device fine-tune
│   │   ├── a4_edge_llm.py      # Ollama / QGenie
│   │   ├── a5_proactive.py     # cloud trend
│   │   ├── a6_complex.py       # cloud Q&A
│   │   └── a7_rag.py           # local guideline RAG
│   └── orchestrator/
│       ├── zeroclaw_bus.py     # reused
│       └── alert_router.py     # cardiac safety pre-emption
├── frontend/
│   ├── index.html              # biosignal dashboard
│   ├── css/healthsense.css
│   └── js/
│       ├── main.js
│       ├── sensors/            # WebSerial / WebBluetooth ingest + simulators
│       ├── charts/             # uPlot real-time waveforms
│       └── orchestrator/       # SSE client, ZeroClaw mirror
├── models/                     # downloaded artefacts
│   ├── panluna_int8.qnn.onnx   # (target) compiled via AI Hub
│   ├── panluna_fp32.onnx       # source
│   ├── kokoro-v1.0.onnx        # symlink to cabinai
│   ├── voices.bin
│   └── bge_small_en/
├── scripts/
│   ├── compile_panluna.py      # qai_hub compile job (Hexagon target)
│   ├── profile_panluna.py      # qai_hub profile job
│   ├── synth_biosignal.py      # offline generator for demo when no sensor
│   └── export_models.py        # mirrors cabinai
├── submissions/
│   ├── HealthSense_Slides.pptx
│   ├── HealthSense_SpeechNotes.pdf
│   └── HealthSense_Architecture.png
├── docs/
│   └── idea-02-healthsense.docx
├── pdfs/
│   └── idea-02-healthsense.html / .pdf
├── README.md
├── CODEBASE_STATE.md
└── IMPLEMENTATION_PLAN.md      # this file
```

---

## 5. Phase Plan (4 sprints × 2 days each = 8 days to demo-ready)

### Phase 0 — Bootstrap (Day 0, ~2 h)  ✅ DONE
- [x] Mirror CabinAI: `.env`, `.venv312` junction, `requirements.txt`.
- [x] Write `IMPLEMENTATION_PLAN.md`, slide deck, speech PDF.
- [x] Read AI Hub model registry — confirm we will *upload* PanLUNA (not in default zoo).

### Phase 1 — Sensor & Sim (Day 1–2)
- [ ] `scripts/synth_biosignal.py` — generates realistic EEG/ECG/PPG/EMG/IMU streams from
      MIT-BIH, Sleep-EDF, PulseDB, MIMIC-IV samples (CC-licensed slices).
- [ ] `frontend/js/sensors/sim_source.js` — WebSocket source feeding 250/500 Hz to charts.
- [ ] uPlot real-time strip charts (5 stacked panels, 10 s rolling window).
- [ ] Optional: WebBluetooth shim for Polar H10 ECG / Empatica E4 PPG.

### Phase 2 — PanLUNA on NPU (Day 3–4)
- [ ] `models/panluna_fp32.onnx` — pull reference impl, sanity-check vs paper benchmarks.
- [ ] `scripts/compile_panluna.py` —
      ```python
      job = qai_hub.submit_compile_job(
          model="models/panluna_fp32.onnx",
          device=qai_hub.Device("Snapdragon X Elite CRD"),
          options="--target_runtime qnn --quantize_full_type w8a8")
      ```
- [ ] `scripts/profile_panluna.py` — log latency, throughput, RAM, mJ.
- [ ] `backend/agents/a2_panluna.py` — `onnxruntime` w/ QNN-EP loader.
- [ ] Wire to ZeroClaw bus; publish `infer.cardiac`, `infer.sleep`, `infer.stress`,
      `infer.eeg_abn`.

### Phase 3 — BioTrain personalisation (Day 5)
- [ ] `backend/agents/a3_biotrain.py` — last-2-block fine-tune; GroupNorm swap; gradient
      accumulation; <50 mW budget.
- [ ] UI toggle: "Personalise to me" — collects 30 s baseline, fine-tunes, rebinds head.
- [ ] Show before/after accuracy delta on the dashboard.

### Phase 4 — Cloud opt-in & Polish (Day 6–7)
- [ ] A5/A6/A7 wired through QGenie (CabinAI keys reused) for clinician summary.
- [ ] Federated DP-SGD weight-delta upload stub (no raw signals).
- [ ] Alert-router pre-emption test (cardiac > 0.7 silences other agents).
- [ ] Session export JSON (timestamped events, *no waveforms*).
- [ ] Demo dry-runs; record 90-second video for backup.

### Phase 5 — Submission (Day 8)
- [ ] Update PPT with final numbers, push slides + speech PDF + arch PNG to `submissions/`.
- [ ] Final code-review pass; ruff clean; README quick-start verified.

---

## 6. Datasets used (for pre-train + eval, all public)

| Dataset | Modality | Size | Use |
|---|---|---|---|
| TUEG / TUAB | EEG | ~26 k recordings | EEG abnormality eval |
| MIMIC-IV-ECG | ECG | ~800 k 10-s strips | ECG pre-train + arrhythmia eval |
| CODE-15% | ECG | ~300 k strips | Arrhythmia eval |
| PulseDB | PPG + ABP | ~5.2 M segments | PPG pre-train, BP regression |
| HMC sleep | EEG+ECG+EMG+EOG | 154 nights | Sleep-staging eval (SOTA target) |
| Sleep-EDF | EEG+EMG | 197 nights | Sleep-staging eval |

---

## 7. Risks & Mitigations

| Risk | Likelihood | Mitigation |
|---|---|---|
| PanLUNA reference weights not redistributable | Medium | Train a smaller equivalent on public data (TUEG + MIMIC-IV) and clearly cite "PanLUNA-style" in slides. Demo flow does not depend on official checkpoint. |
| QNN-EP quantisation accuracy drop | Medium | Mixed-precision (FP16 first then a8w8 selectively); calibrate on 1 k-sample subset. |
| Live BLE sensors flaky on demo day | High | Always fall back to `sim_source.js` from recorded patient slices. |
| Judges question "where is PanLUNA's official repo" | Medium | Ship our open clone + clearly mark; reference both arXiv IDs in deck. |
| Cloud component perceived as required | Low | Slide #6 explicitly: cloud is *clinician-only* and *metadata-only*. |

---

## 8. Improvements over the original idea (from web sweep + first-principles)

These extend the proposal beyond the baseline doc:

1. **DP-SGD federated update path** — every wearer optionally uploads model deltas with
   ε=8 differential privacy. Improves population model without raw data.
2. **Latent-space alert hashing** — alerts are semantic embeddings, not waveforms; even the
   clinician dashboard never sees raw signals.
3. **Sensor-dropout robustness** — train PanLUNA with random modality dropout so it still
   works when, e.g., only PPG is available (consumer smartwatch case).
4. **Wake-word style zero-shot anomaly** — repurpose the foundation encoder for one-shot
   arrhythmia matching against a wearer's "normal" template (anchor + contrastive head).
5. **Proactive forecasting** — Agent 5 predicts AFib episodes 5–15 min before onset using
   Qwen3-VL-32B over sliding-window embeddings (literature precedent: AFib episodes have
   subtle PPG/HRV precursors detectable minutes earlier).
6. **Explainable alerts via local LLM** — Agent 4 turns "VT, 0.92" into
   "*Your heart just showed a fast rhythm consistent with ventricular tachycardia. Sit
   down and call 911 if it doesn't pass in 30 seconds.*" — accessibility for non-experts.
7. **Glucose proxy via PPG** — recent literature shows non-invasive glycaemic estimation
   from PPG morphology; we add an experimental head as a stretch goal.
8. **Continuous evaluation harness** — every PR runs a 1 k-sample regression vs golden
   benchmarks; prevents accuracy regressions from sneaking in.

---

## 9. Demo Script (90 s)

1. **0–10 s**  — Wearable streams 5 modalities; charts come alive.
2. **10–25 s** — PanLUNA infers cardiac rhythm (Sinus), sleep stage (Wake), stress (low),
                 EEG (normal). Latency badge: *97 ms · 19 mJ*.
3. **25–45 s** — Inject AFib-like ECG sample → arrhythmia head fires; A4 narrates
                 "*possible AFib, recommend rest*"; A5 forecasts 30-min trend.
4. **45–65 s** — Click "Personalise" → 30 s baseline capture → BioTrain runs on-device →
                 stress baseline shifts; before/after F1 jumps from 0.78 → 0.91.
5. **65–80 s** — Clinician dashboard (cloud) gets *only* "AFib, conf 0.92, 12:04 UTC" —
                 inspector shows literally 0 bytes of raw signal in the cloud payload.
6. **80–90 s** — Tagline: "*Your data stays on your wrist. Your insights don't.*"

---

## 10. Acceptance Tests

| Test | Pass criterion |
|---|---|
| `pytest tests/test_panluna_latency.py` | p95 < 150 ms on Snapdragon X Elite |
| `pytest tests/test_zero_egress.py` | tcpdump capture during 60 s demo shows 0 bytes of raw biosignal egress |
| `pytest tests/test_personalisation.py` | F1 improves ≥ +20 % after BioTrain on a held-out user |
| `pytest tests/test_alert_router.py` | Severity > 0.7 silences A4/A5/A6 within 1 cycle |
| Demo dry-run | <90 s end-to-end; no manual restarts |

---
**Last updated:** 2026-06-04
