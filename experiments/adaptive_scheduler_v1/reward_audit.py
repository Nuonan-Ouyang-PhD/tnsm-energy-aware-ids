"""Reproduce the validation-only pairwise reward audit without test leakage."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from scheduler.config import load_config
from scheduler.isolation import DataUse, Partition
from scheduler.reward import balanced_accuracy
from scheduler.state import ACTION_ORDER
from scheduler.trace_io import load_npz_episode


ROOT = Path(__file__).resolve().parent
DEFAULT_OUTPUT = ROOT / "reward_audit_v1"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _normalise(value: float, low: float, high: float) -> float:
    return max(0.0, min(1.0, (value - low) / (high - low)))


def _balanced_accuracy_from_confusion(matrix: list[list[int]]) -> float:
    tn, fp = matrix[0]
    fn, tp = matrix[1]
    return 0.5 * (tn / (tn + fp) + tp / (tp + fn))


def build_audit() -> tuple[dict, list[dict]]:
    config_path = ROOT / "config" / "scheduler_experiment_v1.json"
    loaded = load_config(config_path)
    config = loaded.data
    trace_dir = ROOT / "policy_inputs"
    trace_manifest_path = trace_dir / "manifest.json"
    trace_manifest = json.loads(trace_manifest_path.read_text(encoding="utf-8"))
    threshold = float(config["actions"]["prediction_threshold"])

    per_action: dict[str, list[float]] = {action.value: [] for action in ACTION_ORDER}
    validation_hashes: dict[str, str] = {}
    windows = 0
    for seed in trace_manifest["validation_trace_seeds"]:
        name = f"validation_drift_{seed}.npz"
        episode = load_npz_episode(
            trace_dir / name,
            partition=Partition.VALIDATION,
            config=config,
            expected_sha256=trace_manifest["output_sha256"][name],
            load_labels=True,
        )
        validation_hashes[name] = episode.sha256
        for window_index in range(episode.windows):
            labels = episode.labels_for_reward(
                window_index, use=DataUse.CHECKPOINT_SELECTION
            )
            for action in ACTION_ORDER:
                probabilities = episode.outcome_for_action(window_index, action).attack_probabilities
                predictions = (probabilities >= threshold).astype(int)
                per_action[action.value].append(
                    balanced_accuracy(labels.tolist(), predictions.tolist())
                )
            windows += 1

    reward = config["reward"]
    weights = reward["weights"]
    power_bounds = (
        float(reward["power_component"]["lower_watts"]),
        float(reward["power_component"]["upper_watts"]),
    )
    latency_bounds = (
        float(reward["latency_component"]["lower_batch_ms"]),
        float(reward["latency_component"]["upper_batch_ms"]),
    )
    penalties: dict[str, float] = {}
    for action in ACTION_ORDER:
        cost = config["resource_cost_registry"]["models"][action.value]
        penalties[action.value] = (
            float(weights["power"])
            * _normalise(float(cost["mean_watts"]), *power_bounds)
            + float(weights["latency"])
            * _normalise(float(cost["mean_batch_latency_ms_median"]), *latency_bounds)
        )

    rows: list[dict] = []
    for action_a in ACTION_ORDER:
        for action_b in ACTION_ORDER:
            if action_a is action_b:
                continue
            differences = np.asarray(per_action[action_a.value]) - np.asarray(
                per_action[action_b.value]
            )
            tau = (penalties[action_a.value] - penalties[action_b.value]) / float(
                weights["detection"]
            )
            delta_min = float(differences.min())
            delta_max = float(differences.max())
            rows.append(
                {
                    "action_a": action_a.value,
                    "action_b": action_b.value,
                    "tau_ab": tau,
                    "validation_delta_ba_min": delta_min,
                    "validation_delta_ba_max": delta_max,
                    "strict_reversal_attainable": delta_min < tau < delta_max,
                    "validation_windows": windows,
                }
            )

    aggregate_path = ROOT / "reward_audit_inputs" / "static_classifier_confusion_counts.json"
    aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))
    validation_gap = _balanced_accuracy_from_confusion(
        aggregate["models"]["MedRF"]["validation_confusion_matrix"]
    ) - _balanced_accuracy_from_confusion(
        aggregate["models"]["LightLR"]["validation_confusion_matrix"]
    )
    test_gap = _balanced_accuracy_from_confusion(
        aggregate["models"]["MedRF"]["test_confusion_matrix"]
    ) - _balanced_accuracy_from_confusion(
        aggregate["models"]["LightLR"]["test_confusion_matrix"]
    )
    medrf_lightlr = next(
        row
        for row in rows
        if row["action_a"] == "MedRF" and row["action_b"] == "LightLR"
    )
    audit = {
        "status": "PASS",
        "scope": "validation-only pairwise reward audit",
        "test_used_for_reward_audit": False,
        "config_sha256": loaded.sha256,
        "policy_input_manifest_sha256": sha256_file(trace_manifest_path),
        "validation_trace_sha256": validation_hashes,
        "validation_traces": len(validation_hashes),
        "validation_windows": windows,
        "prediction_threshold": threshold,
        "thermal_treatment": (
            "excluded from action differences because compact software traces provide no "
            "action-attributable post-action temperature; frozen inputs use a constant "
            "35C predecision proxy and the executed thermal component is zero"
        ),
        "medrf_minus_lightlr": medrf_lightlr,
        "static_classifier_aggregate_diagnostic": {
            "input_snapshot": str(aggregate_path.relative_to(ROOT)),
            "input_snapshot_sha256": sha256_file(aggregate_path),
            "original_source_artifact": aggregate["original_source_artifact"],
            "original_source_sha256": aggregate["original_source_sha256"],
            "validation_balanced_accuracy_gap_medrf_minus_lightlr": validation_gap,
            "test_balanced_accuracy_gap_medrf_minus_lightlr": test_gap,
            "test_gap_role": "posthoc descriptive only; not used for validation audit",
        },
    }
    return audit, rows


def write_outputs(output_dir: Path) -> None:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise FileExistsError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    audit, rows = build_audit()
    (output_dir / "reward_audit.json").write_text(
        json.dumps(audit, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with (output_dir / "pairwise_validation_audit.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    (output_dir / "README.md").write_text(
        "# Validation-only reward audit\n\n"
        "Generated by `python3 reward_audit.py`. The audit opens only the five "
        "hash-bound validation traces. Test aggregate metrics are retained solely as "
        "a labelled post-hoc diagnostic recomputed from the tracked confusion-count "
        "snapshot and do not enter the pairwise decision. "
        "The thermal term is excluded from action differences because the compact "
        "software traces contain no action-attributable post-action temperature.\n",
        encoding="utf-8",
    )
    content = sorted(path for path in output_dir.iterdir() if path.name != "MANIFEST_SHA256.txt")
    (output_dir / "MANIFEST_SHA256.txt").write_text(
        "".join(f"{sha256_file(path)}  {path.name}\n" for path in content), encoding="utf-8"
    )


def check_outputs(output_dir: Path) -> None:
    with TemporaryDirectory() as temporary:
        expected = Path(temporary) / "reward_audit_v1"
        write_outputs(expected)
        expected_names = sorted(path.name for path in expected.iterdir())
        actual_names = sorted(path.name for path in output_dir.iterdir())
        if actual_names != expected_names:
            raise RuntimeError("reward audit file set differs from deterministic regeneration")
        for name in expected_names:
            if (expected / name).read_bytes() != (output_dir / name).read_bytes():
                raise RuntimeError(f"reward audit output differs: {name}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    if args.check:
        check_outputs(args.output_dir)
    else:
        write_outputs(args.output_dir)


if __name__ == "__main__":
    main()
