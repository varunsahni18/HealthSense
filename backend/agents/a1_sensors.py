"""Synthetic 5-modal biosignal generator.

Generates physiologically plausible (not clinically accurate) waveforms for the demo:
  - ECG  (Lead II, 250 Hz) — sinus rhythm with switchable AFib / VT / PVC injection
  - PPG  (100 Hz)          — pulse with HR-coupled morphology
  - EEG  (250 Hz, Cz)      — alpha-dominant background; switchable theta on drowsy
  - EMG  (500 Hz)          — low-amplitude white noise; bursts on stress
  - IMU  (100 Hz, accel)   — gentle gait modulation

Each generator advances on calls to `step(dt)` and returns the latest sample;
internally it keeps a ~4-second ring buffer per channel for the inference engine.

This module is the source of truth for "what sensors saw"; downstream agents
(a2_panluna, a3_biotrain) consume the rolling buffers, never raw streams.
"""
from __future__ import annotations

import math
import random
import threading
import time
from collections import deque

import numpy as np

# Sample rates (Hz)
SR = {"ecg": 250, "ppg": 100, "eeg": 250, "emg": 500, "imu": 100}
BUF_SECONDS = 6.0  # keep 6 s per channel


def _ecg_beat(n_samples: int, fs: int = 250, hr: float = 72.0,
              shape: str = "normal", rng: np.random.Generator | None = None
              ) -> np.ndarray:
    """One beat at HR bpm, shape ∈ {normal, afib, vt, pvc}."""
    rng = rng or np.random.default_rng()
    rr_s = 60.0 / max(30.0, hr)
    n = max(8, int(rr_s * fs))
    t = np.linspace(0, rr_s, n, endpoint=False)
    p_amp = 0.10 if shape != "vt" else 0.0
    q_amp = -0.10
    r_amp = 1.0 if shape != "vt" else 0.55
    s_amp = -0.20
    t_amp = 0.30 if shape != "vt" else -0.40
    centre = rr_s * 0.4
    p_c = centre - 0.18 * rr_s
    q_c = centre - 0.04 * rr_s
    r_c = centre
    s_c = centre + 0.04 * rr_s
    tw = centre + 0.22 * rr_s
    pw, qw, rw, sw, tw_w = 0.045, 0.012, 0.018, 0.020, 0.07

    def gauss(c, w, a):
        return a * np.exp(-((t - c) ** 2) / (2 * w * w))

    sig = (gauss(p_c, pw, p_amp) + gauss(q_c, qw, q_amp) +
           gauss(r_c, rw, r_amp) + gauss(s_c, sw, s_amp) +
           gauss(tw, tw_w, t_amp))
    if shape == "afib":
        sig += rng.normal(0, 0.04, n)         # fibrillatory baseline
        sig = sig - sig.mean()
        sig *= rng.uniform(0.85, 1.15)         # beat-to-beat amplitude variation
    elif shape == "pvc":
        # Wide bizarre QRS, no P wave
        sig = (gauss(centre, 0.05, 1.4) + gauss(centre + 0.07, 0.06, -0.6))
    elif shape == "vt":
        # Already shaped above (no P, wide QRS, inverted T)
        pass
    sig += rng.normal(0, 0.005, n)             # sensor noise
    if n_samples and n != n_samples:
        # Resample with linear interp
        idx = np.linspace(0, n - 1, n_samples)
        sig = np.interp(idx, np.arange(n), sig)
    return sig.astype(np.float32)


class BiosignalEngine:
    """Single-instance, thread-safe synthetic 5-modal source."""

    def __init__(self):
        self.rng = np.random.default_rng(7)
        self._lock = threading.Lock()
        self.scenario = "normal"          # normal · afib · vt · stress · drowsy
        self.hr = 72.0
        self.hr_target = 72.0
        self.respiration_phase = 0.0
        self.gait_phase = 0.0
        self.t = 0.0
        # Ring buffers (np arrays)
        self._buf: dict[str, deque] = {
            k: deque(maxlen=int(BUF_SECONDS * fs))
            for k, fs in SR.items()
        }
        # ECG state machine: schedule beats
        self._next_beat_t = 0.0
        self._beat_seq = []  # queued shapes
        # Pre-compute anchor sinus beat
        self._beat_cache: dict[str, np.ndarray] = {}

    # ---- public ----
    def set_scenario(self, name: str):
        with self._lock:
            self.scenario = name
            if name == "afib":
                self.hr_target = 130.0
            elif name == "vt":
                self.hr_target = 165.0
            elif name == "stress":
                self.hr_target = 95.0
            elif name == "drowsy":
                self.hr_target = 58.0
            else:
                self.hr_target = 72.0

    def step(self, dt: float):
        """Advance all channels by `dt` seconds. Pushes samples into ring buffers."""
        with self._lock:
            self.t += dt
            # Drift HR towards target
            self.hr += (self.hr_target - self.hr) * min(1.0, dt * 0.6)
            self._fill_ecg(dt)
            self._fill_ppg(dt)
            self._fill_eeg(dt)
            self._fill_emg(dt)
            self._fill_imu(dt)

    def snapshot(self, modality: str, seconds: float = 4.0) -> np.ndarray:
        with self._lock:
            buf = self._buf[modality]
            n = int(seconds * SR[modality])
            if not buf:
                return np.zeros(n, dtype=np.float32)
            arr = np.fromiter(buf, dtype=np.float32, count=len(buf))
            if len(arr) >= n:
                return arr[-n:].copy()
            pad = np.zeros(n - len(arr), dtype=np.float32)
            return np.concatenate([pad, arr])

    def latest_n(self, modality: str, n: int) -> list[float]:
        """For SSE — last n samples as plain list."""
        with self._lock:
            buf = self._buf[modality]
            if len(buf) <= n:
                return list(buf)
            return list(buf)[-n:]

    # ---- internal generators ----
    def _fill_ecg(self, dt: float):
        fs = SR["ecg"]
        n = int(dt * fs)
        if n <= 0:
            return
        out = np.zeros(n, dtype=np.float32)
        sample_dt = 1.0 / fs
        for i in range(n):
            self.t += 0  # cosmetic
            if not self._beat_seq:
                # schedule next beat using current hr
                rr_s = 60.0 / max(30.0, self.hr)
                shape = "normal"
                if self.scenario == "afib":
                    rr_s = rr_s * self.rng.uniform(0.55, 1.45)
                    shape = "afib" if self.rng.random() < 0.85 else "pvc"
                elif self.scenario == "vt":
                    shape = "vt"
                    rr_s = 60.0 / 165.0
                elif self.scenario == "stress" and self.rng.random() < 0.04:
                    shape = "pvc"
                self._next_beat_t = rr_s
                self._beat_seq.append((shape, rr_s, 0.0))
            shape, rr_s, elapsed = self._beat_seq[0]
            # generate per-beat waveform once
            key = f"{shape}_{int(self.hr)}_{int(rr_s*1000)}"
            if key not in self._beat_cache:
                self._beat_cache[key] = _ecg_beat(int(rr_s * fs), fs=fs,
                                                   hr=60.0 / rr_s, shape=shape,
                                                   rng=self.rng)
                if len(self._beat_cache) > 256:
                    self._beat_cache.pop(next(iter(self._beat_cache)))
            beat = self._beat_cache[key]
            idx = int(elapsed * fs)
            if idx < len(beat):
                out[i] = beat[idx]
            elapsed += sample_dt
            if elapsed >= rr_s:
                self._beat_seq.pop(0)
            else:
                self._beat_seq[0] = (shape, rr_s, elapsed)
        # baseline drift + noise
        out += 0.02 * np.sin(2 * np.pi * 0.25 * (self.t + np.arange(n) * sample_dt))
        out += self.rng.normal(0, 0.01, n).astype(np.float32)
        self._buf["ecg"].extend(out.tolist())

    def _fill_ppg(self, dt: float):
        fs = SR["ppg"]
        n = int(dt * fs)
        if n <= 0:
            return
        sample_dt = 1.0 / fs
        t0 = self.t
        # PPG morphology — systolic + dicrotic peak
        f_hr = self.hr / 60.0
        out = np.zeros(n, dtype=np.float32)
        for i in range(n):
            tt = t0 + i * sample_dt
            phase = (tt * f_hr) % 1.0
            primary = math.exp(-((phase - 0.18) ** 2) / 0.006)
            dicrotic = 0.4 * math.exp(-((phase - 0.52) ** 2) / 0.012)
            noise = self.rng.normal(0, 0.02)
            out[i] = primary + dicrotic + noise
        if self.scenario == "afib":
            out *= 0.6 + 0.4 * np.sin(2 * np.pi * 0.4 * (t0 + np.arange(n) * sample_dt))
        self._buf["ppg"].extend(out.tolist())

    def _fill_eeg(self, dt: float):
        fs = SR["eeg"]
        n = int(dt * fs)
        if n <= 0:
            return
        sample_dt = 1.0 / fs
        t0 = self.t
        tt = t0 + np.arange(n) * sample_dt
        if self.scenario == "drowsy":
            # theta-dominant
            sig = 0.7 * np.sin(2 * np.pi * 5 * tt) + 0.2 * np.sin(2 * np.pi * 8 * tt)
        elif self.scenario == "stress":
            # beta-dominant
            sig = 0.4 * np.sin(2 * np.pi * 22 * tt) + 0.3 * np.sin(2 * np.pi * 18 * tt)
        else:
            # alpha-dominant
            sig = 0.6 * np.sin(2 * np.pi * 10 * tt) + 0.2 * np.sin(2 * np.pi * 12 * tt)
        sig += self.rng.normal(0, 0.15, n)
        self._buf["eeg"].extend(sig.astype(np.float32).tolist())

    def _fill_emg(self, dt: float):
        fs = SR["emg"]
        n = int(dt * fs)
        if n <= 0:
            return
        burst = (self.scenario == "stress")
        amp = 0.25 if burst else 0.05
        out = self.rng.normal(0, amp, n).astype(np.float32)
        if burst and self.rng.random() < 0.3:
            out *= 1.8
        self._buf["emg"].extend(out.tolist())

    def _fill_imu(self, dt: float):
        fs = SR["imu"]
        n = int(dt * fs)
        if n <= 0:
            return
        sample_dt = 1.0 / fs
        tt = self.t + np.arange(n) * sample_dt
        gait_f = 1.6 if self.scenario != "drowsy" else 0.6
        sig = 0.5 * np.sin(2 * np.pi * gait_f * tt)
        sig += self.rng.normal(0, 0.05, n)
        self._buf["imu"].extend(sig.astype(np.float32).tolist())


engine = BiosignalEngine()


def runner_loop(stop_event: threading.Event, hz: int = 50):
    """Background driver for the engine. Steps the engine at `hz` Hz."""
    period = 1.0 / hz
    last = time.time()
    while not stop_event.is_set():
        now = time.time()
        dt = now - last
        last = now
        engine.step(dt)
        time.sleep(max(0.0, period - (time.time() - now)))
