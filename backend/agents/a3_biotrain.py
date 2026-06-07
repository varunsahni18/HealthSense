"""BioTrain on-device personalisation simulator.

Models the paper's 30-second-baseline → on-device fine-tune → +35 % gain story.
Runs in a background thread so the dashboard can show a live progress bar.

In the real implementation this would call a small PyTorch loop with GroupNorm
and gradient accumulation; for the demo we emulate the *behaviour* (training
curve and final F1 jump) deterministically so demo-day timing is predictable.
"""
from __future__ import annotations

import threading
import time

from backend.orchestrator.zeroclaw_bus import bus

_state = {"running": False, "baseline_collected": False, "lock": threading.Lock()}


def collect_baseline_async(seconds: float = 30.0):
    """Background thread: 'collect' a baseline, publishing TRAIN_UPDATE ticks."""
    def _run():
        with _state["lock"]:
            if _state["running"]:
                return
            _state["running"] = True
        try:
            steps = 60
            for i in range(steps):
                pct = (i + 1) / steps * 100.0
                bus.publish("TRAIN_UPDATE", {
                    "phase": "baseline",
                    "progress": (i + 1) / steps * 0.4,   # baseline = first 40 %
                    "baseline_pct": pct,
                    "done": False,
                })
                time.sleep(seconds / steps)
            _state["baseline_collected"] = True
            bus.publish("SESSION_EVENT",
                        {"kind": "baseline_complete", "ts": time.time()})
        finally:
            _state["running"] = False
    threading.Thread(target=_run, daemon=True).start()


def run_training_async(epochs: int = 30):
    """Background thread: 'fine-tune' with a deterministic curve."""
    def _run():
        with _state["lock"]:
            if _state["running"]:
                return
            _state["running"] = True
        try:
            f1_before = 0.78
            f1_after_target = 0.91
            for i in range(epochs):
                progress = 0.4 + (i + 1) / epochs * 0.6
                # F1 curve: smooth ramp
                k = (i + 1) / epochs
                f1 = f1_before + (f1_after_target - f1_before) * (1 - (1 - k) ** 2)
                bus.publish("TRAIN_UPDATE", {
                    "phase": "fine_tune",
                    "progress": progress,
                    "stress_f1_live": round(f1, 3),
                    "done": False,
                })
                time.sleep(0.12)
            bus.publish("TRAIN_UPDATE", {
                "phase": "fine_tune",
                "progress": 1.0,
                "stress_f1_after": f1_after_target,
                "stress_f1_before": f1_before,
                "delta_pct": round((f1_after_target - f1_before) / f1_before * 100, 1),
                "done": True,
            })
            bus.publish("SESSION_EVENT", {"kind": "personalised", "ts": time.time()})
        finally:
            _state["running"] = False
    threading.Thread(target=_run, daemon=True).start()


def is_running() -> bool:
    return _state["running"]


def baseline_ready() -> bool:
    return _state["baseline_collected"]
