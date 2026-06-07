"""Local alert explainer (a4) + clinician summary (a5/a6 cloud, opt-in).

`a4_explain` is a deterministic template-driven explainer. In production this
would be Ollama qwen2:7b; for demo determinism we use templates that read the
exact bus state — same UX, no model warmup.

`cloud_clinician_summary` is the ONLY function in HealthSense that emits bytes
to the cloud. It accepts an opt-in flag, builds a metadata-only payload (alert
label, confidence, timestamp, optional 16-d embedding hash), and either calls
Cloud LLM if enabled or returns a deterministic stub. Either way it logs the byte
count to the bus EGRESS topic so the privacy inspector can show it.
"""
from __future__ import annotations

import hashlib
import json
import os
import time

from backend.orchestrator.zeroclaw_bus import bus

ALERT_TEMPLATES = {
    "Atrial fibrillation": (
        "Your heart just showed an irregular rhythm consistent with atrial "
        "fibrillation (AFib). It is not immediately dangerous, but please sit "
        "down, breathe slowly, and contact your doctor if it persists more than "
        "30 minutes."
    ),
    "Ventricular tachycardia": (
        "Warning: ventricular tachycardia detected — a fast rhythm from the "
        "lower heart chambers. Sit or lie down NOW. If you feel chest pain, "
        "shortness of breath, or faintness, call emergency services immediately."
    ),
    "Sinus tachycardia": (
        "Your heart rate is elevated but the rhythm is normal. Common causes are "
        "exertion, stress, or caffeine. Try slow breathing for 60 seconds."
    ),
    "Sinus bradycardia": (
        "Your heart rate is on the lower side but the rhythm is normal. If you "
        "feel light-headed or short of breath, sit down and contact your doctor."
    ),
    "Sinus rhythm": (
        "Heart rhythm normal. All clear."
    ),
}


def explain_cardiac(label: str, conf: float, hr: float) -> str:
    base = ALERT_TEMPLATES.get(label, f"{label} detected (confidence {conf:.0%}).")
    if label != "Sinus rhythm":
        base += f" Heart rate {hr:.0f} bpm, model confidence {conf:.0%}."
    return base


def cloud_clinician_summary(opt_in: bool, snapshot: dict) -> dict:
    """Build a metadata-only payload and emit it (or stub it) to the cloud."""
    if not opt_in:
        return {"sent": False, "reason": "wearer did not opt in"}

    embedding_seed = json.dumps({
        "label": snapshot.get("cardiac_label"),
        "hr": round(snapshot.get("hr", 0.0)),
        "stage": snapshot.get("sleep_stage"),
    }, sort_keys=True)
    fingerprint = hashlib.sha256(embedding_seed.encode()).hexdigest()[:32]

    payload = {
        "alert": {
            "label":      snapshot.get("cardiac_label"),
            "confidence": round(snapshot.get("cardiac_conf", 0.0), 3),
            "ts":         time.time(),
        },
        "embedding_hash": fingerprint,    # 32-char hex of a privacy fingerprint
        "schema_version": "1.0",
    }
    n_bytes = len(json.dumps(payload).encode())

    # Egress accounting BEFORE making the call so privacy panel updates atomically
    bus.publish("EGRESS", {"dest": "cloud", "bytes": n_bytes,
                           "kind": "clinician_summary"})

    cloud_llm_enabled = os.environ.get("CLOUD_LLM_ENABLED", "false").lower() == "true"
    explanation: str
    if cloud_llm_enabled and os.environ.get("CLOUD_LLM_API_KEY"):
        try:
            import requests
            resp = requests.post(
                os.environ["CLOUD_LLM_ENDPOINT"].rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {os.environ['CLOUD_LLM_API_KEY']}"},
                json={
                    "model": os.environ.get("CLOUD_LLM_MODEL",
                                            "anthropic::claude-4-5-sonnet"),
                    "messages": [
                        {"role": "system",
                         "content": "You are a cardiology nurse explaining an "
                                    "alert to a clinician in two sentences."},
                        {"role": "user",
                         "content": json.dumps(payload["alert"])},
                    ],
                    "max_tokens": 120,
                    "temperature": 0.2,
                },
                timeout=4.0,
            )
            explanation = (resp.json()
                           .get("choices", [{}])[0]
                           .get("message", {})
                           .get("content", "Clinician summary unavailable."))
        except Exception as e:
            explanation = f"Clinician summary (Cloud LLM unreachable: {e})."
    else:
        explanation = (
            "Wearer flagged a non-sinus event. Embedding fingerprint logged; "
            "raw waveform retained on device for clinician review on consent. "
            "Recommend follow-up if event recurs in next 24 h."
        )

    return {
        "sent":          True,
        "bytes":         n_bytes,
        "payload":       payload,
        "explanation":   explanation,
        "cloud_llm_used":   cloud_llm_enabled,
    }
