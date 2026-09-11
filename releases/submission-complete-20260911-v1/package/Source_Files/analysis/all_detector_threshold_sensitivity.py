#!/usr/bin/env python3
"""Offline threshold diagnostic from frozen TON-IoT prediction arrays.

Validation selects the threshold; test is evaluated once. This script does not
retrain models or touch any physical evidence.
"""
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "tnsm_experiments_v1" / "results" / "ton_iot"
OUT = ROOT / "analysis" / "reviewer_revision" / "all_detector_threshold_sensitivity.csv"

val = np.load(SOURCE / "validation_predictions.npz", allow_pickle=True)
test = np.load(SOURCE / "test_predictions.npz", allow_pickle=True)
rows = []
for j, model in enumerate(val["models"].tolist()):
    yv, sv = val["labels"], val["probabilities"][:, j]
    candidates = np.linspace(0.01, 0.99, 981)
    scores = [balanced_accuracy_score(yv, (sv >= t).astype(int)) for t in candidates]
    best_ba = max(scores)
    tau = max(t for t, ba in zip(candidates, scores) if ba == best_ba)
    yt, st = test["labels"], test["probabilities"][:, j]
    for label, threshold in (("fixed_0p5", 0.5), ("validation_selected", tau)):
        pred = (st >= threshold).astype(int)
        tn = int(((yt == 0) & (pred == 0)).sum())
        fp = int(((yt == 0) & (pred == 1)).sum())
        fn = int(((yt == 1) & (pred == 0)).sum())
        tp = int(((yt == 1) & (pred == 1)).sum())
        rows.append({"model": model, "result": label, "threshold": threshold,
                     "tn": tn, "fp": fp, "fn": fn, "tp": tp,
                     "f1": f1_score(yt, pred),
                     "fpr": fp / (tn + fp), "validation_ba": best_ba})
OUT.parent.mkdir(parents=True, exist_ok=True)
pd.DataFrame(rows).to_csv(OUT, index=False)
print(OUT)
