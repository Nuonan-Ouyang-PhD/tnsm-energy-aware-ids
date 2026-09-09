"""Two-step TinyDT validation selection and one-time frozen-test evaluation."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
VAL = REPO / "tnsm_experiments_v1" / "results" / "ton_iot" / "validation_predictions.npz"
TEST = REPO / "tnsm_experiments_v1" / "results" / "ton_iot" / "test_predictions.npz"
OUT = ROOT / "r4_threshold_and_reference"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def confusion(labels: np.ndarray, scores: np.ndarray, threshold: float) -> dict:
    truth, pred = labels.astype(bool), scores >= threshold
    tn = int(np.count_nonzero(~truth & ~pred)); fp = int(np.count_nonzero(~truth & pred))
    fn = int(np.count_nonzero(truth & ~pred)); tp = int(np.count_nonzero(truth & pred))
    recall = tp/(tp+fn) if tp+fn else 0.0
    specificity = tn/(tn+fp) if tn+fp else 0.0
    precision = tp/(tp+fp) if tp+fp else 0.0
    return {"tn": tn, "fp": fp, "fn": fn, "tp": tp, "f1": 2*precision*recall/(precision+recall) if precision+recall else 0.0, "recall": recall, "fpr": fp/(fp+tn) if fp+tn else 0.0, "balanced_accuracy": (recall+specificity)/2}


def arrays(path: Path) -> tuple[np.ndarray, np.ndarray, int]:
    data = np.load(path, allow_pickle=False)
    models = list(map(str, data["models"]))
    index = models.index("TinyDT")
    return data["labels"].astype(np.int8), data["probabilities"][:, index].astype(np.float32), index


def select() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    lock_path = OUT / "tinydt_threshold_lock.json"
    if lock_path.exists(): raise RuntimeError("threshold lock already exists")
    labels, scores, model_index = arrays(VAL)
    unique = np.unique(scores.astype(np.float64))
    candidates = np.concatenate(([np.nextafter(unique[0], -np.inf)], unique, [np.nextafter(unique[-1], np.inf)]))
    rows = []
    best_ba = -1.0; best_threshold = None
    for threshold in candidates:
        metrics = confusion(labels, scores, float(threshold))
        rows.append({"threshold": repr(float(threshold)), **metrics})
        ba = metrics["balanced_accuracy"]
        if ba > best_ba or (ba == best_ba and (best_threshold is None or threshold > best_threshold)):
            best_ba, best_threshold = ba, float(threshold)
    candidate_path = OUT / "tinydt_validation_all_threshold_candidates.csv"
    with candidate_path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)
    selected = confusion(labels, scores, best_threshold)
    lock = {
        "status": "FROZEN_BEFORE_TEST_APPLICATION", "analysis_label": "post-hoc revision analysis; does not replace threshold=0.5 primary result",
        "selection_partition": "validation", "selection_criterion": "maximum balanced_accuracy",
        "tie_break": "highest threshold among exact equal maxima", "threshold": best_threshold,
        "validation_cache": str(VAL.relative_to(REPO)), "validation_cache_sha256": digest(VAL),
        "model_index": model_index, "model_artifact_sha256": "9941090e54203557d63b2f6117622bcba3535019796f7dfefb955293d085c2f2",
        "candidate_count": len(rows), "candidate_metrics_sha256": digest(candidate_path), "validation_metrics": selected,
        "validation_auroc": float(roc_auc_score(labels, scores)), "validation_average_precision": float(average_precision_score(labels, scores)),
        "test_accessed_during_selection": False,
    }
    with lock_path.open("x") as handle: json.dump(lock, handle, indent=2, allow_nan=False); handle.write("\n")
    print(json.dumps({"status": "PASS", "threshold": best_threshold, "balanced_accuracy": best_ba, "lock_sha256": digest(lock_path)}, indent=2))


def apply() -> None:
    lock_path = OUT / "tinydt_threshold_lock.json"
    result_path = OUT / "tinydt_frozen_threshold_test_result.json"
    if result_path.exists(): raise RuntimeError("test result already exists")
    lock = json.loads(lock_path.read_text())
    if lock.get("status") != "FROZEN_BEFORE_TEST_APPLICATION" or digest(VAL) != lock["validation_cache_sha256"]:
        raise RuntimeError("threshold lock binding failed")
    labels, scores, model_index = arrays(TEST)
    if model_index != lock["model_index"]: raise RuntimeError("TinyDT model index changed")
    result = {
        "status": "PASS", "analysis_label": lock["analysis_label"], "threshold": lock["threshold"],
        "threshold_lock_sha256": digest(lock_path), "test_cache": str(TEST.relative_to(REPO)), "test_cache_sha256": digest(TEST),
        "metrics": confusion(labels, scores, float(lock["threshold"])), "auroc": float(roc_auc_score(labels, scores)),
        "average_precision": float(average_precision_score(labels, scores)), "test_applications": 1,
    }
    with result_path.open("x") as handle: json.dump(result, handle, indent=2, allow_nan=False); handle.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("mode", choices=["select", "apply"]); args = parser.parse_args()
    select() if args.mode == "select" else apply()
