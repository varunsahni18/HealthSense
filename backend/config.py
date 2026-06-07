"""HealthSense backend config — small, .env-driven, mirrors cabinai/backend/config.py."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Load .env if present
def _load_env():
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        os.environ.setdefault(k.strip(), v.strip())

_load_env()

FLASK_PORT  = int(os.environ.get("FLASK_PORT", "5005"))   # 5005 to avoid cabinai conflict
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "false").lower() == "true"

# Cloud (opt-in only — clinician summary)
CLOUD_LLM_ENABLED  = os.environ.get("CLOUD_LLM_ENABLED", "false").lower() == "true"
CLOUD_LLM_API_KEY  = os.environ.get("CLOUD_LLM_API_KEY", "")
CLOUD_LLM_ENDPOINT = os.environ.get("CLOUD_LLM_ENDPOINT", "")
CLOUD_LLM_MODEL    = os.environ.get("CLOUD_LLM_MODEL", "anthropic::claude-4-5-sonnet")

# Sensor sample rates (Hz)
SR = {"ecg": 250, "ppg": 100, "eeg": 250, "emg": 500, "imu": 100}
WINDOW_S = 4.0  # 4-second analysis window
STREAM_HZ = 25  # SSE frames per second
