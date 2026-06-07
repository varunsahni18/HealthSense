"""ZeroClaw bus — pub/sub + SSE fan-out.

Adapted from cabinai/backend/orchestrator/zeroclaw_bus.py. Same shape, healthsense topics:
  SENSOR_FRAME · INFER_RESULT · ALERT · TRAIN_UPDATE · EGRESS · SESSION_EVENT
"""
import threading
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Callable


@dataclass
class BusState:
    # Inference outputs
    cardiac_label:    str   = "Sinus rhythm"
    cardiac_conf:     float = 0.95
    cardiac_severity: float = 0.0   # 0..1, drives safety pre-empt
    sleep_stage:      str   = "Wake"
    sleep_conf:       float = 0.92
    stress_level:     float = 0.18  # 0..1
    stress_f1:        float = 0.78  # before personalisation
    eeg_label:        str   = "Normal"
    eeg_conf:         float = 0.94
    # Vitals (derived from synth)
    heart_rate:       float = 72.0
    hrv_rmssd:        float = 45.0
    spo2:             float = 98.0
    resp_rate:        float = 14.0
    # Performance
    last_latency_ms:  float = 0.0
    last_energy_mj:   float = 0.0
    inference_count:  int   = 0
    # Personalisation
    personalised:     bool  = False
    baseline_pct:     float = 0.0
    train_progress:   float = 0.0
    # Privacy
    bytes_to_cloud:   int   = 0
    bytes_local:      int   = 0
    # Mode
    scenario:         str   = "normal"
    safety_active:    bool  = False
    # Session
    session_events:   list  = field(default_factory=list)


class ZeroClawBus:
    def __init__(self):
        self._state = BusState()
        self._lock = threading.RLock()
        self._subs: dict[str, list[Callable]] = {}
        self._sse_clients: list = []

    def publish(self, event: str, data: Any):
        with self._lock:
            self._apply(event, data)
            msg = {"event": event, "data": data, "ts": time.time()}
        for h in self._subs.get(event, []):
            try:
                h(data)
            except Exception:
                pass
        self._push_sse(msg)

    def subscribe(self, event: str, h: Callable):
        self._subs.setdefault(event, []).append(h)

    def get_state(self) -> dict:
        with self._lock:
            return asdict(self._state)

    def add_sse_client(self, q):
        self._sse_clients.append(q)

    def remove_sse_client(self, q):
        self._sse_clients = [c for c in self._sse_clients if c is not q]

    def _push_sse(self, msg):
        import json
        dead = []
        for q in self._sse_clients:
            try:
                q.put_nowait(json.dumps(msg))
            except Exception:
                dead.append(q)
        for d in dead:
            self.remove_sse_client(d)

    def _apply(self, event: str, data: Any):
        s = self._state
        if event == "INFER_RESULT" and isinstance(data, dict):
            s.cardiac_label    = data.get("cardiac_label", s.cardiac_label)
            s.cardiac_conf     = data.get("cardiac_conf", s.cardiac_conf)
            s.cardiac_severity = data.get("cardiac_severity", s.cardiac_severity)
            s.sleep_stage      = data.get("sleep_stage", s.sleep_stage)
            s.sleep_conf       = data.get("sleep_conf", s.sleep_conf)
            s.stress_level     = data.get("stress_level", s.stress_level)
            s.eeg_label        = data.get("eeg_label", s.eeg_label)
            s.eeg_conf         = data.get("eeg_conf", s.eeg_conf)
            s.last_latency_ms  = data.get("latency_ms", s.last_latency_ms)
            s.last_energy_mj   = data.get("energy_mj", s.last_energy_mj)
            s.inference_count += 1
            s.heart_rate       = data.get("hr", s.heart_rate)
            s.hrv_rmssd        = data.get("hrv", s.hrv_rmssd)
            s.spo2             = data.get("spo2", s.spo2)
            s.resp_rate        = data.get("resp", s.resp_rate)
            # Safety pre-empt
            if s.cardiac_severity > 0.7 and not s.safety_active:
                s.safety_active = True
            elif s.cardiac_severity < 0.4:
                s.safety_active = False
        elif event == "TRAIN_UPDATE" and isinstance(data, dict):
            s.train_progress = data.get("progress", s.train_progress)
            s.baseline_pct   = data.get("baseline_pct", s.baseline_pct)
            if data.get("done"):
                s.personalised = True
                s.stress_f1    = data.get("stress_f1_after", 0.91)
        elif event == "EGRESS" and isinstance(data, dict):
            n = int(data.get("bytes", 0))
            if data.get("dest") == "cloud":
                s.bytes_to_cloud += n
            else:
                s.bytes_local += n
        elif event == "SCENARIO" and isinstance(data, dict):
            s.scenario = data.get("type", "normal")
        elif event == "SESSION_EVENT":
            s.session_events.append(data)
            if len(s.session_events) > 100:
                s.session_events = s.session_events[-100:]


bus = ZeroClawBus()
