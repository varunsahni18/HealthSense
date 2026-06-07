"""HealthSense Flask backend.

Endpoints
  GET  /api/health
  GET  /api/state                bus snapshot
  GET  /api/events               SSE stream of bus events
  GET  /api/stream               SSE waveform stream (5 modalities @ STREAM_HZ)
  POST /api/scenario             {type: normal|afib|vt|stress|drowsy}
  POST /api/personalize/start    begin 30-s baseline capture
  POST /api/personalize/run      run fine-tune
  POST /api/cloud/clinician      opt-in clinician summary
  GET  /api/egress/log           current egress totals + recent events
  POST /api/session/export       download session JSON
"""
from __future__ import annotations

import json
import os
import queue
import sys
import threading
import time

# allow `python backend/server.py` from project root
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from flask import Flask, Response, jsonify, request, send_from_directory

from backend.config import FLASK_DEBUG, FLASK_PORT, STREAM_HZ
from backend.orchestrator.zeroclaw_bus import bus
from backend.agents import a1_sensors, a2_panluna, a3_biotrain, a4_explainer

app = Flask(__name__, static_folder=os.path.join(ROOT, "frontend"),
            static_url_path="")

# ---------------------------------------------------------------------------
# Static frontend
# ---------------------------------------------------------------------------
@app.get("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


# ---------------------------------------------------------------------------
# Background workers
# ---------------------------------------------------------------------------
_stop = threading.Event()


def _sensor_runner():
    a1_sensors.runner_loop(_stop, hz=50)


def _inference_runner():
    """Run PanLUNA inference at ~5 Hz; publish INFER_RESULT."""
    while not _stop.is_set():
        try:
            res = a2_panluna.infer()
            bus.publish("INFER_RESULT", res)
            # Local-only egress accounting for transparency
            bus.publish("EGRESS",
                        {"dest": "local",
                         "bytes": len(json.dumps(res).encode()),
                         "kind": "infer"})
            # Auto-narration for high-severity events
            if res["cardiac_severity"] > 0.7:
                msg = a4_explainer.explain_cardiac(
                    res["cardiac_label"], res["cardiac_conf"], res["hr"])
                bus.publish("ALERT", {
                    "level":   "high",
                    "label":   res["cardiac_label"],
                    "msg":     msg,
                    "ts":      time.time(),
                })
                bus.publish("SESSION_EVENT",
                            {"kind": "cardiac_alert",
                             "label": res["cardiac_label"],
                             "ts": time.time()})
        except Exception as e:
            print(f"[infer] {e}")
        time.sleep(0.2)


threading.Thread(target=_sensor_runner, daemon=True).start()
threading.Thread(target=_inference_runner, daemon=True).start()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "ts": time.time()})


@app.get("/api/state")
def state():
    return jsonify(bus.get_state())


@app.get("/api/events")
def events():
    """SSE stream of every bus event."""
    q: queue.Queue = queue.Queue(maxsize=200)
    bus.add_sse_client(q)

    def gen():
        try:
            yield f"data: {json.dumps({'event': 'HELLO', 'ts': time.time()})}\n\n"
            while True:
                try:
                    msg = q.get(timeout=10)
                    yield f"data: {msg}\n\n"
                except queue.Empty:
                    yield ": keep-alive\n\n"
        finally:
            bus.remove_sse_client(q)

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


@app.get("/api/stream")
def stream():
    """High-rate SSE waveform stream — sends latest 250 ms slice every 1/STREAM_HZ s."""
    def gen():
        period = 1.0 / STREAM_HZ
        # how many samples to send per modality per tick
        slice_s = 1.0 / STREAM_HZ
        last = time.time()
        while not _stop.is_set():
            now = time.time()
            if now - last < period:
                time.sleep(period - (now - last))
                continue
            last = now
            payload = {
                "t":   now,
                "ecg": a1_sensors.engine.latest_n(
                    "ecg", int(slice_s * a1_sensors.SR["ecg"])),
                "ppg": a1_sensors.engine.latest_n(
                    "ppg", int(slice_s * a1_sensors.SR["ppg"])),
                "eeg": a1_sensors.engine.latest_n(
                    "eeg", int(slice_s * a1_sensors.SR["eeg"])),
                "emg": a1_sensors.engine.latest_n(
                    "emg", int(slice_s * a1_sensors.SR["emg"])),
                "imu": a1_sensors.engine.latest_n(
                    "imu", int(slice_s * a1_sensors.SR["imu"])),
            }
            payload_str = json.dumps(payload)
            bus.publish("EGRESS",
                        {"dest": "local",
                         "bytes": len(payload_str.encode()),
                         "kind": "stream"})
            yield f"data: {payload_str}\n\n"

    return Response(gen(), mimetype="text/event-stream",
                    headers={"Cache-Control": "no-cache",
                             "X-Accel-Buffering": "no"})


@app.post("/api/scenario")
def scenario():
    body = request.get_json(force=True) or {}
    name = body.get("type", "normal")
    if name not in ("normal", "afib", "vt", "stress", "drowsy"):
        return jsonify({"error": "bad scenario"}), 400
    a1_sensors.engine.set_scenario(name)
    bus.publish("SCENARIO", {"type": name})
    bus.publish("SESSION_EVENT", {"kind": "scenario", "type": name, "ts": time.time()})
    return jsonify({"ok": True, "scenario": name})


@app.post("/api/personalize/start")
def personalize_start():
    a3_biotrain.collect_baseline_async(seconds=8.0)   # 8 s for stage demo
    return jsonify({"ok": True, "baseline_seconds": 8})


@app.post("/api/personalize/run")
def personalize_run():
    if not a3_biotrain.baseline_ready():
        return jsonify({"error": "baseline not collected"}), 409
    a3_biotrain.run_training_async()
    return jsonify({"ok": True})


@app.post("/api/cloud/clinician")
def clinician():
    opt_in = bool((request.get_json(force=True) or {}).get("opt_in", False))
    snap = bus.get_state()
    res = a4_explainer.cloud_clinician_summary(opt_in, snap)
    bus.publish("SESSION_EVENT", {"kind": "clinician_summary",
                                  "opt_in": opt_in, "ts": time.time()})
    return jsonify(res)


@app.get("/api/egress/log")
def egress_log():
    s = bus.get_state()
    return jsonify({
        "bytes_local":     s["bytes_local"],
        "bytes_to_cloud":  s["bytes_to_cloud"],
        "raw_signal_bytes": 0,   # invariant — never increments
        "session_events":  s["session_events"][-30:],
    })


@app.post("/api/session/export")
def session_export():
    s = bus.get_state()
    payload = {
        "exported_at": time.time(),
        "session": s,
        "note": "No raw biosignal samples are included by design.",
    }
    return jsonify(payload)


@app.post("/api/explain")
def explain():
    s = bus.get_state()
    msg = a4_explainer.explain_cardiac(
        s["cardiac_label"], s["cardiac_conf"], s["heart_rate"])
    return jsonify({"msg": msg, "label": s["cardiac_label"]})


# ---------------------------------------------------------------------------
# Boot
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print(f"[HealthSense] starting on :{FLASK_PORT} (debug={FLASK_DEBUG})")
    app.run(host="127.0.0.1", port=FLASK_PORT,
            debug=FLASK_DEBUG, threaded=True, use_reloader=False)
