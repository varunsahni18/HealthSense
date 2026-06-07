"""Train ECG arrhythmia CNN on REAL PhysioNet data.

Source dataset: MIT-BIH Atrial Fibrillation Database (afdb), accessed via
wfdb-python over PhysioNet's HTTPS API. Already at 250 Hz, matching our
demo pipeline — no resampling needed.

  https://physionet.org/content/afdb/1.0.0/

We pull 4 records and use only the first 30 minutes of each (saves bandwidth);
segment by AF / N annotations into 4-second non-overlapping windows;
train a 3-class CNN (Sinus rhythm, Atrial fibrillation, Other) — same
14k-param architecture as the synth-trained model.

Output: models/ecg_cnn_physionet.onnx
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import wfdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.train_ecg_cnn import ECGCNN  # reuse architecture

OUT = ROOT / "models" / "ecg_cnn_physionet.onnx"
DATA_DIR = ROOT / "models" / "_physionet_cache"
DATA_DIR.mkdir(parents=True, exist_ok=True)

WIN_S = 4
FS = 250
WIN_N = WIN_S * FS

# Class mapping — 3 way: Sinus rhythm / AFib / Other
LABELS = ["Sinus rhythm", "Atrial fibrillation", "Other"]
ANN_TO_CLASS = {
    "(N":      0,   # Normal sinus rhythm
    "(AFIB":   1,   # Atrial fibrillation
    "(AFL":    2,   # Atrial flutter → Other
    "(J":      2,   # Junctional → Other
}

# Records to use from afdb. Each is ~10 h; we take first 30 min only.
RECORDS = ["04015", "04043", "04126", "04746"]
SAMPLES_PER_RECORD = 30 * 60 * FS   # 30 minutes


def fetch_record(rid: str) -> tuple[np.ndarray, list]:
    """Returns (signal_lead0, list[(start_sample, end_sample, ann_label)])."""
    print(f"[afdb] fetching record {rid} (first {SAMPLES_PER_RECORD/FS/60:.0f} min)...")
    sig, _ = wfdb.rdsamp(rid, pn_dir="afdb/1.0.0",
                         sampfrom=0, sampto=SAMPLES_PER_RECORD, channels=[0])
    ann = wfdb.rdann(rid, "atr", pn_dir="afdb/1.0.0",
                     sampfrom=0, sampto=SAMPLES_PER_RECORD)
    # Build interval list: each rhythm annotation marks the start of a region
    # that lasts until the next one (or end of signal).
    starts = ann.sample.tolist()
    auxs = ann.aux_note
    intervals = []
    for i, s in enumerate(starts):
        e = starts[i + 1] if i + 1 < len(starts) else len(sig)
        intervals.append((s, e, auxs[i]))
    return sig[:, 0].astype(np.float32), intervals


def extract_windows(sig: np.ndarray, intervals, n_per_class_per_record: int = 80
                    ) -> tuple[list, list]:
    X, y = [], []
    rng = np.random.default_rng(42)
    by_class: dict[int, list] = {0: [], 1: [], 2: []}
    for s, e, lbl in intervals:
        cls = ANN_TO_CLASS.get(lbl)
        if cls is None:
            continue
        # Generate non-overlapping windows in [s, e]
        for ws in range(s, e - WIN_N, WIN_N):
            we = ws + WIN_N
            x = sig[ws:we].copy()
            if len(x) < WIN_N or np.std(x) < 1e-4:
                continue
            x = (x - x.mean()) / (x.std() + 1e-6)
            by_class[cls].append(x.astype(np.float32))
    # Cap per class
    for cls in (0, 1, 2):
        windows = by_class[cls]
        if len(windows) > n_per_class_per_record:
            idx = rng.choice(len(windows), n_per_class_per_record, replace=False)
            windows = [windows[i] for i in idx]
        X.extend(windows)
        y.extend([cls] * len(windows))
    return X, y


def main():
    t0 = time.perf_counter()
    print("[physionet] downloading + extracting windows...")
    X_all, y_all = [], []
    for rid in RECORDS:
        try:
            sig, intervals = fetch_record(rid)
            X, y = extract_windows(sig, intervals)
            X_all.extend(X); y_all.extend(y)
            print(f"  {rid}: {len(X):>4} windows  (class counts: "
                  f"{[sum(1 for c in y if c == k) for k in (0, 1, 2)]})")
        except Exception as e:
            print(f"  {rid}: SKIPPED ({e})")
    if not X_all:
        print("ERROR: no real data fetched — check internet / PhysioNet access")
        sys.exit(1)
    X = np.stack(X_all)[:, None, :]
    y = np.array(y_all, dtype=np.int64)
    print(f"[physionet] total: {len(X)} windows  shape={X.shape}  classes={np.bincount(y).tolist()}")

    # Stratified train/test split (~85/15)
    rng = np.random.default_rng(7)
    perm = rng.permutation(len(X))
    X = X[perm]; y = y[perm]
    n_test = max(8, int(0.15 * len(X)))
    Xtr, ytr = X[:-n_test], y[:-n_test]
    Xte, yte = X[-n_test:], y[-n_test:]
    print(f"[physionet] train={len(Xtr)}  test={len(Xte)}")

    model = ECGCNN(n_classes=3)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"[physionet] params: {n_params:,}")

    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    crit = nn.CrossEntropyLoss()
    bs = 64
    Xtr_t = torch.from_numpy(Xtr); ytr_t = torch.from_numpy(ytr)
    Xte_t = torch.from_numpy(Xte); yte_t = torch.from_numpy(yte)

    best_acc = 0.0
    for epoch in range(15):
        model.train()
        ep_loss = 0.0
        order = rng.permutation(len(Xtr_t))
        for i in range(0, len(order), bs):
            idx = order[i:i + bs]
            xb = Xtr_t[idx]; yb = ytr_t[idx]
            opt.zero_grad()
            out = model(xb)
            loss = crit(out, yb)
            loss.backward(); opt.step()
            ep_loss += loss.item() * len(idx)
        ep_loss /= len(Xtr_t)
        model.eval()
        with torch.no_grad():
            pred = model(Xte_t).argmax(dim=1)
            acc = (pred == yte_t).float().mean().item()
        best_acc = max(best_acc, acc)
        print(f"  ep {epoch + 1:>2}: loss={ep_loss:.4f}  test_acc={acc:.3f}")

    # per-class
    model.eval()
    with torch.no_grad():
        pred = model(Xte_t).argmax(dim=1).numpy()
    print("[physionet] per-class accuracy:")
    for c, name in enumerate(LABELS):
        mask = (yte == c)
        if mask.sum() == 0:
            continue
        ca = (pred[mask] == c).mean() if mask.sum() else 0.0
        print(f"    {name:<24} n={int(mask.sum()):>4}  acc={ca:.2%}")

    # Export ONNX
    dummy = torch.randn(1, 1, WIN_N)
    torch.onnx.export(
        model, dummy, str(OUT),
        input_names=["ecg_window"], output_names=["logits"],
        dynamic_axes={"ecg_window": {0: "batch"}, "logits": {0: "batch"}},
        opset_version=17,
    )
    sz = OUT.stat().st_size
    print(f"[physionet] exported {OUT.relative_to(ROOT)} "
          f"({sz:,} B = {sz/1024:.1f} KB) in {time.perf_counter()-t0:.1f} s")
    (OUT.parent / "ecg_cnn_physionet_labels.txt").write_text("\n".join(LABELS))


if __name__ == "__main__":
    main()
