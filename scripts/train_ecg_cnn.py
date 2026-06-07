"""Train a small 1D CNN to classify 4-second ECG windows.

Generates labelled training data by driving the same biosignal engine the demo
uses, then trains a tiny PyTorch CNN, exports to ONNX, and writes the file to
`models/ecg_cnn.onnx`.

Classes:
  0 = Sinus rhythm
  1 = Atrial fibrillation
  2 = Ventricular tachycardia
  3 = Sinus tachycardia (stress proxy)
  4 = Sinus bradycardia (drowsy proxy)
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.agents.a1_sensors import BiosignalEngine, SR  # noqa: E402

OUT = ROOT / "models" / "ecg_cnn.onnx"
OUT.parent.mkdir(parents=True, exist_ok=True)

DEVICE = "cpu"
WIN_S = 4
FS = SR["ecg"]
WIN_N = WIN_S * FS  # 1000 samples

LABELS = ["Sinus rhythm", "Atrial fibrillation", "Ventricular tachycardia",
          "Sinus tachycardia", "Sinus bradycardia"]

SCENARIO_TO_LABEL = {
    "normal": 0,   # sinus
    "afib":   1,
    "vt":     2,
    "stress": 3,   # sinus tach
    "drowsy": 4,   # sinus brad
}


def gen_dataset(n_per_class: int = 200, seed: int = 7):
    print(f"[train] generating {n_per_class * len(LABELS)} windows...")
    rng = np.random.default_rng(seed)
    X, y = [], []
    for sc, lbl in SCENARIO_TO_LABEL.items():
        eng = BiosignalEngine()
        eng.set_scenario(sc)
        # warm up so the buffer fills with the right rhythm
        for _ in range(120):
            eng.step(0.1)
        for _ in range(n_per_class):
            for _ in range(2):  # shift forward 0.2 s between samples
                eng.step(0.1)
            x = eng.snapshot("ecg", WIN_S)
            x = (x - x.mean()) / (x.std() + 1e-6)   # per-window z-norm
            X.append(x.astype(np.float32))
            y.append(lbl)
    X = np.stack(X)[:, None, :]   # (N, 1, WIN_N)
    y = np.array(y, dtype=np.int64)
    p = rng.permutation(len(X))
    return X[p], y[p]


class ECGCNN(nn.Module):
    """~50 k params — small enough to run on a watch."""

    def __init__(self, n_classes: int = 5):
        super().__init__()
        self.net = nn.Sequential(
            nn.Conv1d(1,  16, kernel_size=15, stride=2, padding=7),
            nn.BatchNorm1d(16), nn.ReLU(),
            nn.Conv1d(16, 32, kernel_size=11, stride=2, padding=5),
            nn.BatchNorm1d(32), nn.ReLU(),
            nn.Conv1d(32, 32, kernel_size=7,  stride=2, padding=3),
            nn.BatchNorm1d(32), nn.ReLU(),
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(32, 32), nn.ReLU(),
            nn.Linear(32, n_classes),
        )

    def forward(self, x):
        return self.net(x)


def main():
    t0 = time.perf_counter()
    X, y = gen_dataset(n_per_class=300)
    n_test = max(1, int(0.15 * len(X)))
    Xtr, ytr = X[:-n_test], y[:-n_test]
    Xte, yte = X[-n_test:], y[-n_test:]
    print(f"[train] train={len(Xtr)} test={len(Xte)} shape={Xtr.shape}")

    model = ECGCNN().to(DEVICE)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"[train] params: {n_params:,}")

    opt = torch.optim.AdamW(model.parameters(), lr=2e-3, weight_decay=1e-4)
    crit = nn.CrossEntropyLoss()
    bs = 64
    Xtr_t = torch.from_numpy(Xtr)
    ytr_t = torch.from_numpy(ytr)
    Xte_t = torch.from_numpy(Xte)
    yte_t = torch.from_numpy(yte)

    for epoch in range(8):
        model.train()
        perm = np.random.permutation(len(Xtr_t))
        ep_loss = 0.0
        for i in range(0, len(perm), bs):
            idx = perm[i:i + bs]
            xb = Xtr_t[idx]; yb = ytr_t[idx]
            opt.zero_grad()
            out = model(xb)
            loss = crit(out, yb)
            loss.backward()
            opt.step()
            ep_loss += loss.item() * len(idx)
        ep_loss /= len(Xtr_t)
        model.eval()
        with torch.no_grad():
            pred = model(Xte_t).argmax(dim=1)
            acc = (pred == yte_t).float().mean().item()
        print(f"  epoch {epoch + 1:>2}: loss={ep_loss:.4f}  test_acc={acc:.3f}")

    # Confusion matrix
    print("[train] per-class accuracy on test set:")
    with torch.no_grad():
        pred = model(Xte_t).argmax(dim=1).numpy()
    for c, name in enumerate(LABELS):
        mask = yte == c
        if mask.sum() == 0:
            continue
        ca = (pred[mask] == c).mean()
        print(f"    {name:<24} n={mask.sum():>3}  acc={ca:.2%}")

    # ── export ONNX ──
    model.eval()
    dummy = torch.randn(1, 1, WIN_N)
    torch.onnx.export(
        model, dummy, str(OUT),
        input_names=["ecg_window"], output_names=["logits"],
        dynamic_axes={"ecg_window": {0: "batch"},
                      "logits":     {0: "batch"}},
        opset_version=17,
    )
    sz = OUT.stat().st_size
    print(f"[train] exported {OUT.relative_to(ROOT)} ({sz:,} B = {sz / 1024:.1f} KB) "
          f"in {time.perf_counter() - t0:.1f} s")
    # Also save labels next to the model
    (OUT.parent / "ecg_cnn_labels.txt").write_text("\n".join(LABELS))

    # quick onnxruntime sanity check
    import onnxruntime as ort
    sess = ort.InferenceSession(str(OUT), providers=["CPUExecutionProvider"])
    test_logits = sess.run(None, {"ecg_window": Xte[:8].astype(np.float32)})[0]
    pred_ort = test_logits.argmax(axis=1)
    print(f"[train] ORT smoke: {pred_ort.tolist()} (true: {yte[:8].tolist()})")


if __name__ == "__main__":
    main()
