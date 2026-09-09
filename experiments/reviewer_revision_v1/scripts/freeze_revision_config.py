"""Validate immutable inputs and create the one-time R0 revision lock/manifests."""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
import subprocess
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SEEDS = [11, 23, 37, 53, 71, 89, 107, 131, 157, 191]
EXPECTED_MODELS = {
    "TinyDT.joblib": "9941090e54203557d63b2f6117622bcba3535019796f7dfefb955293d085c2f2",
    "LightLR.joblib": "a6cafb1426058f0268dd9da065fa3848b95c0a5531b3ec5c1b65987e5ca5268f",
    "MedRF.joblib": "35bc9b8674c5ae3b7c163ab29d7fd3d3abfe61dfaa1d26323530f9d14a2b2688",
    "HeavyMLP.pt": "2999008343be15af0374bc647af6764e010bebc841b953b0307a10ebbc26b8a0",
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def write_new(path: Path, value) -> None:
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def write_or_match(path: Path, value) -> None:
    if path.exists():
        if json.loads(path.read_text()) != value:
            raise RuntimeError(f"existing immutable record differs: {path}")
        return
    write_new(path, value)


def package_check(path: Path) -> dict:
    with zipfile.ZipFile(path) as archive:
        corrupt = archive.testzip()
        if corrupt is not None:
            raise RuntimeError(f"ZIP CRC failure: {path}: {corrupt}")
        names = archive.namelist()
    return {"path": str(path), "sha256": digest(path), "size_bytes": path.stat().st_size, "zip_crc": "PASS", "entries": len(names)}


def relative_files(paths: list[Path]) -> dict[str, str]:
    return {str(path.relative_to(ROOT)): digest(path) for path in sorted(paths)}


def main() -> None:
    for target in (ROOT / "REVISION_CONFIG_LOCK.json", ROOT / "inputs_manifest.json", ROOT / "runtime_manifest.json"):
        if target.exists():
            raise RuntimeError(f"freeze target already exists: {target}")
    for name, expected in EXPECTED_MODELS.items():
        actual = digest(ROOT / "inputs" / name)
        if actual != expected:
            raise RuntimeError(f"model hash mismatch: {name}: {actual}")
    policy_meta = {}
    for name in ("tabular-frozen", "dqn-frozen"):
        data = json.loads((ROOT / "policies" / name / "metadata.json").read_text())
        weight = ROOT / "policies" / name / data["weights_file"]
        if not data["frozen"] or digest(weight) != data["weights_sha256"]:
            raise RuntimeError(f"policy binding failed: {name}")
        policy_meta[name] = {
            "identity_sha256": data["policy_identity_sha256"],
            "weights_sha256": data["weights_sha256"],
            "metadata_sha256": digest(ROOT / "policies" / name / "metadata.json"),
        }

    recovered = []
    csv_path = REPO / "adaptive_scheduler_v1" / "p0_archive" / "expected_vs_recovered.csv"
    for row in csv.DictReader(csv_path.open()):
        path = REPO / "adaptive_scheduler_v1" / "p0_archive" / "executed_source" / row["path"]
        actual = digest(path)
        if actual != row["expected_sha256"] or actual != row["recovered_sha256"]:
            raise RuntimeError(f"executed-source mismatch: {row['path']}")
        recovered.append({"path": row["path"], "sha256": actual})
    if len(recovered) != 6:
        raise RuntimeError("expected six recovered source files")

    packages = [
        package_check(REPO / "TNSM_ADAPTIVE_SCHEDULER_20260907_V1.zip"),
        package_check(REPO / "TNSM_P0_P1_STRENGTHENING_20260908_V1.zip"),
        package_check(Path("/Users/nuonanouyang/Downloads/TNSM_REVIEWER_REQUESTED_REVISION_CODEX_TASK_20260908.zip")),
    ]
    write_or_match(ROOT / "r0_source_audit" / "frozen_package_checks.json", {"status": "PASS", "read_only_checks": packages})

    cost_registry = REPO / "adaptive_scheduler_v1" / "cost_registry" / "cost_registry.csv"
    medrf = next(row for row in csv.DictReader(cost_registry.open()) if row["dataset"] == "ton_iot" and row["model"] == "MedRF")
    l95 = float(medrf["tight_loop_batch_ms_p95"]) / 1000
    mapping = {str(rate): ("MedRF" if ((rate + 99) // 100) * l95 <= 1.0 else "LightLR") for rate in (50, 100, 4000)}
    if set(mapping.values()) != {"MedRF", "LightLR"}:
        raise RuntimeError("DeadlineGuard does not instantiate both actions")
    deadline_guard = {
        "source_artifact": str(cost_registry.relative_to(REPO)), "source_artifact_sha256": digest(cost_registry),
        "source_field": "tight_loop_batch_ms_p95", "medrf_p95_seconds_per_100_rows": l95,
        "formula": "ceil(N_t/100) * L95_MedRF <= 1.0 seconds => MedRF else LightLR",
        "predeclared_mapping": mapping,
    }
    write_or_match(ROOT / "r0_source_audit" / "deadline_guard_preflight.json", {"status": "PASS", **deadline_guard})

    r3_artifact = REPO / "adaptive_scheduler_v1" / "p1b_replacement_runtime" / "p1b_observed_states.json"
    r3_precondition = json.loads((ROOT / "r0_source_audit" / "r3_state_stream_precondition.json").read_text())
    r3_precondition["observed_frozen_artifact_sha256"] = digest(r3_artifact)
    # Preserve the already-created report and bind its source in the lock; no rewrite.

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip()
    status = subprocess.check_output(["git", "status", "--porcelain=v1"], cwd=REPO)
    lock = {
        "lock_id": "TNSM-REVIEWER-REVISION-20260909-V2-PREVALIDATION-CORRECTED",
        "status": "FROZEN_BEFORE_FIRST_VALID_FORMAL_RUN",
        "supersedes_prevalidation_lock_sha256": "2d8480f8d440f4ef5d37df6e692c610cb9df0621f8a2a2aca674152ccf089130",
        "supersession_reason": "The first attempted formal segment was interrupted and retained as INVALID after pre-validation found missing scheduler-selection telemetry; no valid formal run completed under the superseded lock.",
        "git_commit": commit,
        "git_worktree_status_sha256_at_freeze": hashlib.sha256(status).hexdigest(),
        "source_pool_decision": json.loads((ROOT / "r0_source_audit" / "audit.json").read_text())["decision"],
        "experiment_label": "post-hoc physical robustness on frozen test pool",
        "frozen_package_checks": packages,
        "six_recovered_executed_source_identities": recovered,
        "models": {name.removesuffix(Path(name).suffix): sha for name, sha in EXPECTED_MODELS.items()},
        "policies": policy_meta,
        "scheduler_config_sha256": digest(ROOT / "config" / "scheduler_experiment_v1.json"),
        "cascade_rule_sha256": digest(ROOT / "config" / "cascade_rule_0p3_0p7.json"),
        "cascade_band_inclusive": [0.3, 0.7],
        "workload_generator_source_sha256": digest(ROOT / "scripts" / "prepare_revision_runtime.py"),
        "r2_workload_registry_sha256": digest(ROOT / "r2_workloads" / "registry.json"),
        "method_order_schedule_sha256": digest(ROOT / "protocol" / "PREDECLARED_METHOD_ORDERS.csv"),
        "power_meter_parser_sha256": digest(ROOT / "measurement.py"),
        "worker_sha256": digest(ROOT / "worker.py"),
        "controller_sha256": digest(ROOT / "controller.py"),
        "deadline_guard": deadline_guard,
        "validity_rules": {
            "meter_serial": "075356", "meter_vid": "0x5FC9", "meter_pid": "0x0063",
            "voltage_envelope_v": [4.75, 5.50], "maximum_temperature_c_exclusive": 70,
            "required_throttle_flag": "throttled=0x0", "clock_offset_bound_seconds": 0.25,
            "failed_attempt_rule": "retain INVALID; no scientific-outcome retry; replacement only for predeclared instrument/harness validity failure with new ID and replacement_for",
        },
        "idle_reference_semantics": {
            "duration_seconds": 60, "immediately_precedes_each_method_run": True,
            "four_detector_artifacts_resident_and_warmed": True, "telemetry_active": True,
            "detector_inference_during_idle": False, "raw_energy_primary": True,
            "idle_adjustment_is_sensitivity_not_replacement": True,
        },
        "r3_precondition": r3_precondition,
        "labels_absent_from_pi_runtime": True,
        "test_driven_selection": False,
    }
    write_new(ROOT / "REVISION_CONFIG_LOCK.json", lock)

    remote_paths = [ROOT / "worker.py", ROOT / "REVISION_CONFIG_LOCK.json", ROOT / "config" / "scheduler_experiment_v1.json", ROOT / "config" / "cascade_rule_0p3_0p7.json"]
    remote_paths += sorted((ROOT / "scheduler").glob("*.py"))
    remote_paths += sorted((ROOT / "inputs").glob("*.joblib")) + [ROOT / "inputs" / "HeavyMLP.pt", ROOT / "inputs" / "test_X.npy", ROOT / "inputs" / "validation_X.npy", ROOT / "inputs" / "warm_X.npy"]
    remote_paths += sorted((ROOT / "policies").glob("*/*"))
    remote_paths += [ROOT / "traces" / f"formal_test_{seed}.indices.npy" for seed in SEEDS]
    for block in range(1, 11):
        remote_paths += [ROOT / "r2_workloads" / f"block_{block:02d}.{kind}.npy" for kind in ("indices", "arrivals", "offsets")]
    remote_files = relative_files(remote_paths)
    traces = {f"formal_test_{seed}": {"x_file": "inputs/test_X.npy", "indices_file": f"traces/formal_test_{seed}.indices.npy"} for seed in SEEDS}
    r2_registry = json.loads((ROOT / "r2_workloads" / "registry.json").read_text())["blocks"]
    r2_remote = {block: {k: v for k, v in item.items() if k in ("indices_file", "arrivals_file", "offsets_file")} for block, item in r2_registry.items()}
    inputs_manifest = {
        "status": "FROZEN_LABEL_FREE_PI_RUNTIME", "config_sha256": lock["scheduler_config_sha256"],
        "files": remote_files, "traces": traces, "r2_blocks": r2_remote,
        "deadline_guard": deadline_guard, "labels_present_on_pi": False,
    }
    write_new(ROOT / "inputs_manifest.json", inputs_manifest)
    with (ROOT / "inputs_manifest.sha256").open("x") as handle:
        for relative, sha in sorted(remote_files.items()): handle.write(f"{sha}  {relative}\n")

    static_local = remote_paths + [ROOT / "controller.py", ROOT / "measurement.py", ROOT / "inputs" / "test_y.npy", ROOT / "inputs" / "test_source_ids.npy"]
    static_local += sorted((ROOT / "protocol").glob("*")) + sorted((ROOT / "r0_source_audit").glob("*")) + sorted((ROOT / "scripts").glob("*.py"))
    static_local += sorted((ROOT / "r2_workloads").glob("*.labels.npy")) + sorted((ROOT / "r2_workloads").glob("*.source_ids.npy")) + sorted((ROOT / "r2_workloads").glob("*.schedule.json")) + [ROOT / "r2_workloads" / "registry.json"]
    write_new(ROOT / "runtime_manifest.json", {"status": "FROZEN", "files": relative_files(list(dict.fromkeys(static_local)))})
    print(json.dumps({"status": "PASS", "lock_sha256": digest(ROOT / "REVISION_CONFIG_LOCK.json"), "remote_files": len(remote_files), "runtime_files": len(json.loads((ROOT / "runtime_manifest.json").read_text())["files"]), "deadline_guard_mapping": mapping}, indent=2))


if __name__ == "__main__":
    main()
