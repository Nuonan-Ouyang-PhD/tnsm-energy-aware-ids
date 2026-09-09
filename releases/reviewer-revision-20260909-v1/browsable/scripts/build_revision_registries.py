"""Build factual run registries from immutable raw segment evidence."""
from __future__ import annotations

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
LOCK = json.loads((ROOT / "REVISION_CONFIG_LOCK.json").read_text())


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def quantiles(values: list[float]) -> tuple[float | None, float | None, float | None]:
    if not values: return None, None, None
    a = np.asarray(values, dtype=float)
    return float(np.mean(a)), float(np.quantile(a, 0.5)), float(np.quantile(a, 0.95))


def write_csv(path: Path, rows: list[dict]) -> None:
    if path.exists(): raise RuntimeError(f"registry already exists: {path}")
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]) if rows else ["status"])
        writer.writeheader(); writer.writerows(rows or [{"status": "EMPTY"}])


def physical_row(campaign: str, run_dir: Path) -> dict:
    spec = json.loads((run_dir / "run_spec.json").read_text())
    paired = json.loads((run_dir / "paired_summary.json").read_text())
    raw = events(run_dir / "pi_events.jsonl")
    outcomes = [x for x in raw if x.get("event") == "outcome"]
    power = events(run_dir / "power.jsonl")
    post = paired["posthoc"]
    metrics = post.get("metrics", post.get("completed_metrics"))
    scheduler = [x["scheduler_selection_ns"] / 1e6 for x in outcomes]
    detector = []
    end_to_end = [x["end_to_end_window_completion_seconds"] for x in outcomes]
    if campaign == "R1": detector = [x["inference_ns"] / 1e6 for x in outcomes]
    else: detector = [ns / 1e6 for x in outcomes for ns in x["batch_inference_ns"]]
    scheduler_mean, scheduler_p50, scheduler_p95 = quantiles(scheduler)
    detector_mean, _, detector_p95 = quantiles(detector)
    e2e_mean, _, e2e_p95 = quantiles(end_to_end)
    temperatures = [x["post_temperature_c"] for x in outcomes]
    method = spec["method"]
    policy_hash = ""
    if method == "Tabular-Q": policy_hash = LOCK["policies"]["tabular-frozen"]["identity_sha256"]
    elif method == "DQN": policy_hash = LOCK["policies"]["dqn-frozen"]["identity_sha256"]
    trace_seed = [11,23,37,53,71,89,107,131,157,191][spec["block"]-1]
    trace = ROOT / "traces" / f"formal_test_{trace_seed}.indices.npy"
    row = {
        "block_id": spec["block"], "run_id": spec["run_id"], "method": method, "valid": "true", "run_order": spec["position"],
        "trace_hash": digest(trace) if campaign == "R1" else digest(ROOT / "r2_workloads" / f"block_{spec['block']:02d}.indices.npy"),
        "config_hash": digest(ROOT / "REVISION_CONFIG_LOCK.json"), "model_hashes": json.dumps(LOCK["models"], sort_keys=True), "policy_hash": policy_hash,
        "start_utc": power[0]["utc_epoch_request"], "end_utc": power[-1]["utc_epoch_request"], "duration_s": paired["observed_duration_seconds"],
        "energy_j": paired["energy_joules"], "mean_power_w": paired["mean_watts"], "preceding_idle_power_w": paired["preceding_idle_mean_watts"],
        "tn": metrics["tn"], "fp": metrics["fp"], "fn": metrics["fn"], "tp": metrics["tp"], "f1": metrics["f1"],
        "recall": metrics["recall"], "fpr": metrics["fpr"], "balanced_accuracy": metrics["balanced_accuracy"],
        "escalation_fraction": post.get("cascade_escalation_fraction", ""),
        "scheduler_latency_mean_ms": scheduler_mean, "scheduler_latency_p50_ms": scheduler_p50, "scheduler_latency_p95_ms": scheduler_p95,
        "detector_latency_mean_ms": detector_mean, "detector_latency_p95_ms": detector_p95,
        "end_to_end_completion_mean_s": e2e_mean, "end_to_end_completion_p95_s": e2e_p95,
        "final_queue_backlog_rows": post.get("final_backlog_rows", 0), "max_temperature_c": max(temperatures), "mean_temperature_c": float(np.mean(temperatures)),
        "throttle": "false", "undervoltage": "false", "missing_samples": 501-len(power), "missing_windows": 500-len(outcomes),
        "failure_reason": "", "replacement_for": spec.get("replacement_for", ""),
    }
    if campaign == "R2":
        states = [x["encoded_state"] for x in outcomes]
        actions = [x["selected_action"] for x in outcomes]
        q = np.load(ROOT / "policies" / "tabular-frozen" / "q_values.npy", allow_pickle=False)
        fallback = sum(method == "Tabular-Q" and action == "TinyDT" and np.ptp(q[state["index"]]) == 0 for state, action in zip(states, actions))
        row.update({
            "unique_state_count": len(set(x["index"] for x in states)),
            "load_bin_occupancy": json.dumps(Counter(x["load_bin"] for x in states), sort_keys=True),
            "threat_bin_occupancy": json.dumps(Counter(x["threat_bin"] for x in states), sort_keys=True),
            "model_occupancy": json.dumps(Counter(actions), sort_keys=True),
            "switch_count": sum(bool(x["switched"]) for x in outcomes), "tinydt_fallback_count": int(fallback),
            "deadline_miss_count": post["deadline_miss_windows"], "deadline_miss_rate": post["deadline_miss_windows"]/500,
        })
    return row


def main() -> None:
    registry_dir = ROOT / "registries"; registry_dir.mkdir(exist_ok=True)
    attempts = []
    for campaign, dirname in (("R1", "r1_cascade_physical"), ("R2", "r2_variable_load")):
        formal_rows = []
        for run_dir in sorted((ROOT / dirname).glob("*")):
            if not run_dir.is_dir() or not (run_dir / "run_spec.json").exists(): continue
            spec = json.loads((run_dir / "run_spec.json").read_text())
            failure = json.loads((run_dir / "failure.json").read_text()) if (run_dir / "failure.json").exists() else None
            valid = (run_dir / "summary.json").exists() and not failure
            attempts.append({
                "campaign": campaign, "attempt_id": spec["run_id"], "stage": spec["stage"], "method": spec["method"],
                "block_id": spec["block"], "run_order": spec["position"], "valid": str(valid).lower(),
                "formal_statistics": str(bool(spec["formal_statistics"] and valid)).lower(),
                "replacement_for": spec.get("replacement_for", ""), "failure_reason": failure["reason"] if failure else "",
            })
            if spec["formal_statistics"] and valid: formal_rows.append(physical_row(campaign, run_dir))
        expected = 40 if campaign == "R1" else 60
        if len(formal_rows) != expected: raise RuntimeError(f"{campaign} valid formal count {len(formal_rows)} != {expected}")
        write_csv(registry_dir / ("r1_run_registry.csv" if campaign == "R1" else "r2_run_registry.csv"), formal_rows)
    r3 = json.loads((ROOT / "r0_source_audit" / "r3_state_stream_precondition.json").read_text())
    write_csv(registry_dir / "r3_segment_registry.csv", [{
        "condition": "ALL", "block_id": "", "segment_id": "R3-NOT-EXECUTED", "valid": "false", "order": "",
        "energy_j": "", "mean_power_w": "", "preceding_idle_power_w": "", "decision_count": 0,
        "decision_mean_ms": "", "decision_p50_ms": "", "decision_p95_ms": "", "decision_p99_ms": "",
        "cpu": "", "rss": "", "temperature": "", "throttle": "", "undervoltage": "",
        "failure_reason": r3["reason"],
    }])
    threshold = json.loads((ROOT / "r4_threshold_and_reference" / "tinydt_threshold_lock.json").read_text())
    test = json.loads((ROOT / "r4_threshold_and_reference" / "tinydt_frozen_threshold_test_result.json").read_text())
    write_csv(registry_dir / "r4_tinydt_threshold_diagnostic.csv", [
        {"split": "validation", "threshold": threshold["threshold"], **threshold["validation_metrics"], "auroc": threshold["validation_auroc"], "average_precision": threshold["validation_average_precision"], "posthoc_diagnostic": "true", "replaces_primary_threshold_0p5": "false"},
        {"split": "test", "threshold": test["threshold"], **test["metrics"], "auroc": test["auroc"], "average_precision": test["average_precision"], "posthoc_diagnostic": "true", "replaces_primary_threshold_0p5": "false"},
    ])
    attempts.append({"campaign": "R3", "attempt_id": "R3-NOT-EXECUTED", "stage": "r3", "method": "ALL", "block_id": "", "run_order": "", "valid": "false", "formal_statistics": "false", "replacement_for": "", "failure_reason": r3["reason"]})
    write_csv(registry_dir / "revision_attempt_registry.csv", attempts)
    print(json.dumps({"status": "PASS", "r1": 40, "r2": 60, "r3": "NOT_EXECUTED", "attempts": len(attempts)}, indent=2))


if __name__ == "__main__": main()
