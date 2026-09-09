"""Fail-closed validator for complete R0-R4 reviewer-revision evidence."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def rows(path: Path) -> list[dict]:
    return list(csv.DictReader(path.open()))


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def require(condition: bool, message: str) -> None:
    if not condition: raise RuntimeError(message)


def main() -> None:
    lock = json.loads((ROOT / "REVISION_CONFIG_LOCK.json").read_text())
    require(lock["cascade_band_inclusive"] == [0.3, 0.7], "cascade band changed")
    require(digest(ROOT / "worker.py") == lock["worker_sha256"], "worker changed after lock")
    require(digest(ROOT / "controller.py") == lock["controller_sha256"], "controller changed after lock")
    require(digest(ROOT / "measurement.py") == lock["power_meter_parser_sha256"], "meter parser changed")
    require(digest(ROOT / "protocol" / "PREDECLARED_METHOD_ORDERS.csv") == lock["method_order_schedule_sha256"], "order schedule changed")
    for package in lock["frozen_package_checks"][:2]:
        require(digest(Path(package["path"])) == package["sha256"], "frozen V1/P1 package changed")
    for name, meta in lock["policies"].items():
        directory = ROOT / "policies" / name
        data = json.loads((directory / "metadata.json").read_text())
        require(data["policy_identity_sha256"] == meta["identity_sha256"], "policy identity changed")
        require(digest(directory / data["weights_file"]) == meta["weights_sha256"], "policy weights changed")
        require(data["frozen"] and not data["test_data_accessed"], "policy freeze/isolation flags invalid")
    input_manifest = json.loads((ROOT / "inputs_manifest.json").read_text())
    require(input_manifest["labels_present_on_pi"] is False, "Pi label flag changed")
    require(all("label" not in path.lower() and "source_id" not in path.lower() for path in input_manifest["files"]), "label/source IDs listed for Pi")

    order = rows(ROOT / "protocol" / "PREDECLARED_METHOD_ORDERS.csv")
    checks = {}
    for campaign, directory, expected_runs, methods in (
        ("R1", "r1_cascade_physical", 40, {"Static-LightLR", "ConfidenceCascade_0p3_0p7", "Tabular-Q", "Static-MedRF"}),
        ("R2", "r2_variable_load", 60, {"Static-LightLR", "ConfidenceCascade_0p3_0p7", "Tabular-Q", "DQN", "Static-MedRF", "DeadlineGuard"}),
    ):
        formal_dirs = []
        for path in sorted((ROOT / directory).glob("*")):
            if not path.is_dir() or not (path / "run_spec.json").exists(): continue
            spec = json.loads((path / "run_spec.json").read_text())
            if spec["formal_statistics"] and (path / "paired_summary.json").exists() and not (path / "failure.json").exists(): formal_dirs.append(path)
        require(len(formal_dirs) == expected_runs, f"{campaign} valid formal run count")
        for block in range(1, 11):
            found = [json.loads((p / "run_spec.json").read_text()) for p in formal_dirs if json.loads((p / "run_spec.json").read_text())["block"] == block]
            require({x["method"] for x in found} == methods, f"{campaign} block method set {block}")
            expected_order = next(x for x in order if x["campaign"] == campaign and int(x["block"]) == block)
            sequence = [expected_order[f"position{i}"] for i in range(1, 7) if expected_order[f"position{i}"]]
            require([x["method"] for x in sorted(found, key=lambda x: x["position"])] == sequence, f"{campaign} order mismatch {block}")
        for path in formal_dirs:
            spec = json.loads((path / "run_spec.json").read_text())
            ev = jsonl(path / "pi_events.jsonl")
            outcomes = [x for x in ev if x.get("event") == "outcome"]
            require(len(outcomes) == 500, f"window count: {spec['run_id']}")
            require(all("scheduler_selection_ns" in x and x["scheduler_selection_ns"] >= 0 for x in outcomes), "scheduler latency missing")
            require(all(x.get("labels_available") is False for x in outcomes), "label leakage flag")
            require(all(x.get("throttled") == "throttled=0x0" for x in outcomes), "throttle event")
            power = jsonl(path / "power.jsonl")
            require(len(power) == 501, f"power frames: {spec['run_id']}")
            paired = json.loads((path / "paired_summary.json").read_text())
            idle = ROOT / directory / spec["preceding_idle_run_id"]
            require(idle.exists() and (idle / "summary.json").exists(), "preceding idle missing")
            require(paired["preceding_idle_mean_watts"] == json.loads((idle / "summary.json").read_text())["mean_watts"], "idle linkage mismatch")
            if campaign == "R1" and spec["method"] == "ConfidenceCascade_0p3_0p7":
                require(all(x["decision_detail"]["inclusive_band"] == [0.3, 0.7] for x in outcomes), "cascade band event changed")
            if campaign == "R2":
                require(all(x["arrivals"] in (50, 100, 4000) for x in outcomes), "R2 arrivals changed")
                require(sum(x["arrivals"] for x in outcomes) == 627500, "R2 total arrivals changed")
        checks[campaign] = {"valid_formal_runs": len(formal_dirs), "blocks": 10, "status": "PASS"}

    invalid = ROOT / "r1_cascade_physical" / "r1-b01-p1-Static-MedRF"
    require((invalid / "failure.json").exists(), "historical invalid attempt missing")
    replacement = ROOT / "r1_cascade_physical" / "r1v2-b01-p1-Static-MedRF" / "run_spec.json"
    require(json.loads(replacement.read_text()).get("replacement_for") == "r1-b01-p1-Static-MedRF", "replacement linkage missing")
    r2_invalid = ROOT / "r2_variable_load" / "r2v2-b03-p2-Tabular-Q"
    require((r2_invalid / "failure.json").exists(), "R2 infrastructure-invalid attempt missing")
    r2_replacement = ROOT / "r2_variable_load" / "r2v2-b03-p2-Tabular-Q-retry1" / "run_spec.json"
    require(json.loads(r2_replacement.read_text()).get("replacement_for") == "r2v2-b03-p2-Tabular-Q", "R2 replacement linkage missing")
    paused_idle = ROOT / "r2_variable_load" / "r2v2-b04-p6-Static-LightLR-idle"
    require((paused_idle / "failure.json").exists(), "R2 paused prestart idle missing")
    replacement_idle = ROOT / "r2_variable_load" / "r2v2-b04-p6-Static-LightLR-resume1-idle" / "run_spec.json"
    require(json.loads(replacement_idle.read_text()).get("replacement_for") == "r2v2-b04-p6-Static-LightLR-idle", "R2 idle replacement linkage missing")
    r3 = json.loads((ROOT / "r0_source_audit" / "r3_state_stream_precondition.json").read_text())
    require(r3["status"].startswith("STOP_R3"), "R3 stop record missing")
    r3_entries = sorted(path.name for path in (ROOT / "r3_controller_power").glob("*"))
    require(r3_entries == ["R3_NOT_EXECUTED.json"], "R3 unexpectedly executed")
    r3_stop = json.loads((ROOT / "r3_controller_power" / "R3_NOT_EXECUTED.json").read_text())
    require(r3_stop["status"] == r3["status"], "R3 stop records disagree")
    threshold = json.loads((ROOT / "r4_threshold_and_reference" / "tinydt_threshold_lock.json").read_text())
    test = json.loads((ROOT / "r4_threshold_and_reference" / "tinydt_frozen_threshold_test_result.json").read_text())
    require(threshold["test_accessed_during_selection"] is False and test["test_applications"] == 1, "R4 test isolation failed")
    require(test["threshold_lock_sha256"] == digest(ROOT / "r4_threshold_and_reference" / "tinydt_threshold_lock.json"), "R4 lock mismatch")
    require((ROOT / "r4_threshold_and_reference" / "REFERENCE_LOAD_NOT_AVAILABLE.json").exists(), "reference-load inventory missing")
    for name, expected in (("r1_run_registry.csv", 40), ("r2_run_registry.csv", 60), ("r3_segment_registry.csv", 1), ("r4_tinydt_threshold_diagnostic.csv", 2)):
        require(len(rows(ROOT / "registries" / name)) == expected, f"registry count: {name}")
    report = {
        "status": "PASS", "R0": "PASS", **checks, "R3": "NOT_EXECUTED_PREDECLARED_AMBIGUITY",
        "R4": "PASS", "no_test_driven_selection": True, "no_policy_retraining": True,
        "frozen_v1_p1_unchanged": True, "all_attempts_retained": True, "replacement_linkage": "PASS",
    }
    out = ROOT / "validation" / "final_validation.json"
    if out.exists(): raise RuntimeError("validation output already exists")
    with out.open("x") as handle: json.dump(report, handle, indent=2, allow_nan=False); handle.write("\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()
