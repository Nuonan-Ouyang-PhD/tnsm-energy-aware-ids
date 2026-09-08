"""Validate and collect the frozen software and 40-run physical campaign."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import shutil
import statistics


ROOT = Path(__file__).resolve().parent
METHODS = ("Static-MedRF", "CFSM", "Tabular-Q", "DQN")
T95_DF9 = 2.2621571627409915


def load(path: Path):
    with path.open() as handle:
        return json.load(handle)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def interval(values: list[float]) -> tuple[float, float, float, float]:
    mean = statistics.mean(values)
    sd = statistics.stdev(values)
    half = T95_DF9 * sd / math.sqrt(len(values))
    return mean, sd, mean - half, mean + half


def write_csv(path: Path, rows: list[dict]) -> None:
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def line_event_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    with path.open() as handle:
        for line in handle:
            event = json.loads(line)["event"]
            counts[event] = counts.get(event, 0) + 1
    return counts


def validate_physical(runtime: Path, schedule: dict) -> list[dict]:
    execution = runtime / "execution"
    if any(execution.rglob("failure.json")):
        raise RuntimeError("physical campaign contains failure.json")
    formal = load(execution / "formal_summary.json")
    if formal.get("status") != "PASS" or formal.get("formal_runs") != 40:
        raise RuntimeError("formal campaign is not complete")
    events = [json.loads(line) for line in (execution / "events.jsonl").read_text().splitlines()]
    if sum(item.get("event") == "formal_campaign_complete" for item in events) != 1:
        raise RuntimeError("missing unique formal_campaign_complete event")
    pilot_gate = load(runtime / "pilot_gate.json")
    runtime_manifest = load(runtime / "runtime_manifest.json")
    pilot_summary = execution / "pilot-001-round-robin" / "summary.json"
    if pilot_gate.get("status") != "PASS" or sha256(pilot_summary) != pilot_gate.get("pilot_summary_sha256"):
        raise RuntimeError("pilot gate is invalid")
    for field in ("config_sha256", "authorization_sha256", "schedule_sha256", "frozen_policy_identities"):
        if pilot_gate.get(field) != runtime_manifest.get(field):
            raise RuntimeError(f"pilot/runtime binding mismatch: {field}")
    rows = []
    formal_by_id = {item["run_id"]: item for item in formal["runs"]}
    for expected in schedule["runs"]:
        run_dir = execution / expected["run_id"]
        summary = load(run_dir / "summary.json")
        spec = load(run_dir / "run_spec.json")
        for field in ("run_id", "block", "position", "trace_seed", "method", "seconds", "rows"):
            if summary.get(field) != expected[field] or spec.get(field) != expected[field]:
                raise RuntimeError(f"schedule mismatch in {expected['run_id']}: {field}")
        required = {
            "status": "PASS", "power_samples": 501, "telemetry_windows": 500,
            "decision_windows": 500, "missing_power_samples": 0,
            "missing_telemetry_windows": 0, "throttle_events": 0,
        }
        if any(summary.get(key) != value for key, value in required.items()):
            raise RuntimeError(f"invalid run summary: {expected['run_id']}")
        if sum(1 for _ in (run_dir / "power.jsonl").open()) != 501:
            raise RuntimeError(f"power sample count mismatch: {expected['run_id']}")
        counts = line_event_counts(run_dir / "pi_events.jsonl")
        if counts.get("decision") != 500 or counts.get("outcome") != 500 or counts.get("ready") != 1 or counts.get("complete") != 1:
            raise RuntimeError(f"Pi event count mismatch: {expected['run_id']}")
        registered = formal_by_id.get(expected["run_id"])
        if registered is None or registered["energy_joules"] != summary["energy_joules"]:
            raise RuntimeError(f"formal summary mismatch: {expected['run_id']}")
        metrics = summary["posthoc"]["metrics"]
        rows.append({
            **{key: expected[key] for key in ("run_id", "block", "position", "trace_seed", "method")},
            "energy_joules": summary["energy_joules"],
            "mean_watts": summary["mean_watts"],
            "f1": metrics["f1"],
            "accuracy": metrics["accuracy"],
            "fpr": metrics["fpr"],
            "switches": summary["posthoc"]["switches"],
            "max_temperature_c": summary["maximum_temperature_c"],
        })
    if len(rows) != 40 or {row["method"] for row in rows} != set(METHODS):
        raise RuntimeError("wrong physical run set")
    return rows


def summarize(rows: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    method_rows = []
    for method in METHODS:
        selected = [row for row in rows if row["method"] == method]
        item = {"method": method, "n": len(selected)}
        for metric in ("energy_joules", "mean_watts", "f1", "accuracy", "fpr", "switches", "max_temperature_c"):
            mean, sd, low, high = interval([float(row[metric]) for row in selected])
            item.update({f"{metric}_mean": mean, f"{metric}_sd": sd, f"{metric}_ci95_low": low, f"{metric}_ci95_high": high})
        method_rows.append(item)
    paired_rows = []
    by_block = {(row["block"], row["method"]): row for row in rows}
    for method in METHODS[1:]:
        item = {"method": method, "reference": "Static-MedRF", "paired_blocks": 10}
        for metric in ("energy_joules", "mean_watts", "f1", "accuracy", "fpr", "switches"):
            values = [float(by_block[block, method][metric]) - float(by_block[block, "Static-MedRF"][metric]) for block in range(1, 11)]
            mean, sd, low, high = interval(values)
            item.update({f"delta_{metric}_mean": mean, f"delta_{metric}_sd": sd, f"delta_{metric}_ci95_low": low, f"delta_{metric}_ci95_high": high})
        paired_rows.append(item)
    position_rows = []
    for method in METHODS:
        for position in range(1, 5):
            selected = [row for row in rows if row["method"] == method and row["position"] == position]
            position_rows.append({
                "method": method, "position": position, "n": len(selected),
                "energy_joules_mean": statistics.mean(row["energy_joules"] for row in selected) if selected else "",
                "mean_watts_mean": statistics.mean(row["mean_watts"] for row in selected) if selected else "",
                "f1_mean": statistics.mean(row["f1"] for row in selected) if selected else "",
            })
    return method_rows, paired_rows, position_rows


def collect_software(runtime_root: Path, destination: Path) -> None:
    source = runtime_root / "software"
    destination.mkdir()
    names = (
        "tabular-trained", "tabular-frozen", "tabular-trained.training.jsonl",
        "tabular-train.stdout.json", "tabular-train.stderr.log", "tabular-frozen.inspect.json",
        "dqn-trained", "dqn-frozen", "dqn-trained.training.jsonl",
        "dqn-train.stdout.json", "dqn-train.stderr.log", "dqn-frozen.inspect.json",
    )
    for name in names:
        item = source / name
        if item.is_dir():
            shutil.copytree(item, destination / name)
        else:
            shutil.copy2(item, destination / name)


def summarize_software() -> list[dict]:
    software = ROOT / "results_v2" / "software"
    directories = (
        "test-static-tinydt", "test-static-lightlr", "test-static-medrf",
        "test-static-heavymlp", "test-cfsm", "test-tabular", "test-dqn",
    )
    rows = []
    for directory in directories:
        summary = load(software / directory / "summary.json")
        metrics = summary["posthoc_metrics"]
        if summary.get("status") != "software_test_schedule_complete" or len(metrics) != 10:
            raise RuntimeError(f"software result is incomplete: {directory}")
        item = {"method": summary["method"], "test_traces": 10}
        for metric in ("f1", "accuracy", "false_positive_rate", "switches"):
            mean, sd, low, high = interval([float(row[metric]) for row in metrics])
            item.update({f"{metric}_mean": mean, f"{metric}_sd": sd, f"{metric}_ci95_low": low, f"{metric}_ci95_high": high})
        rows.append(item)
    offline = load(software / "test-offline-reference" / "summary.json")
    if offline.get("oracle") is not False or offline.get("globally_optimal") is not False or offline.get("test_labels_used_posthoc") is not True:
        raise RuntimeError("offline reference claim boundary is invalid")
    return rows


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--runtime-root", type=Path, required=True)
    args = parser.parse_args()
    physical_runtime = args.runtime_root / "physical-r3"
    schedule = load(ROOT / "physical_schedule_v1.json")
    rows = validate_physical(physical_runtime, schedule)
    physical_out = ROOT / "results_v2" / "physical"
    training_out = ROOT / "results_v2" / "training"
    if physical_out.exists() or training_out.exists():
        raise RuntimeError("final result destination already exists")
    method_rows, paired_rows, position_rows = summarize(rows)
    software_rows = summarize_software()
    physical_out.mkdir(parents=True)
    write_csv(physical_out / "run_results.csv", rows)
    write_csv(physical_out / "method_summary_t95.csv", method_rows)
    write_csv(physical_out / "paired_vs_static_t95.csv", paired_rows)
    write_csv(physical_out / "position_sensitivity.csv", position_rows)
    write_csv(ROOT / "results_v2" / "software_method_summary_t95.csv", software_rows)
    shutil.copytree(physical_runtime / "execution", physical_out / "raw_execution")
    for name in ("pilot_gate.json", "runtime_manifest.json", "inputs_manifest.json", "inputs_manifest.sha256"):
        shutil.copy2(physical_runtime / name, physical_out / name)
    collect_software(args.runtime_root, training_out)
    validation = {
        "status": "PASS", "pilot_runs": 1, "formal_runs": 40, "paired_blocks": 10,
        "methods": list(METHODS), "automatic_retries": 0,
        "t_interval": {"confidence": 0.95, "df": 9, "critical_value": T95_DF9},
        "scope": "TON-IoT on the identified Raspberry Pi 4B 8GB with KM003C USB load-side measurement",
        "cross_dataset_power_claim": False,
        "runtime_source": str(args.runtime_root),
    }
    (physical_out / "VALIDATION.json").write_text(json.dumps(validation, indent=2) + "\n")
    print(json.dumps(validation, indent=2))


if __name__ == "__main__":
    main()
