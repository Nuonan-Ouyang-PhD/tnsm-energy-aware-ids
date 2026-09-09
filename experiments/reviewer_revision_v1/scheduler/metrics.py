"""Binary window metrics used only with legally available labels."""

from __future__ import annotations

from typing import Sequence

from .reward import RewardError, balanced_accuracy


def binary_metrics(labels: Sequence[int], predictions: Sequence[int]) -> dict[str, float | int]:
    if len(labels) != len(predictions) or not labels:
        raise RewardError("labels and predictions must have equal non-zero length")
    pairs = [(int(y), int(p)) for y, p in zip(labels, predictions)]
    if any(y not in (0, 1) or p not in (0, 1) for y, p in pairs):
        raise RewardError("binary metrics require values in {0,1}")
    tn = sum(y == 0 and p == 0 for y, p in pairs)
    fp = sum(y == 0 and p == 1 for y, p in pairs)
    fn = sum(y == 1 and p == 0 for y, p in pairs)
    tp = sum(y == 1 and p == 1 for y, p in pairs)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2.0 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "samples": len(pairs),
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "tp": tp,
        "accuracy": (tp + tn) / len(pairs),
        "balanced_accuracy": balanced_accuracy(
            [item[0] for item in pairs], [item[1] for item in pairs]
        ),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "false_positive_rate": fp / (fp + tn) if fp + tn else 0.0,
    }

