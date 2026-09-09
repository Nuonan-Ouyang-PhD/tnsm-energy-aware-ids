"""Create factual summaries, full manifest, self-tested final evidence ZIP."""
from __future__ import annotations

from collections import defaultdict
import csv
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import zipfile


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
NAME = "TNSM_REVIEWER_REVISION_EVIDENCE_20260909_V1"
DEST = REPO / NAME
ZIP = REPO / f"{NAME}.zip"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""): h.update(block)
    return h.hexdigest()


def write_new(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle: handle.write(text)


def summary(source: Path, destination: Path) -> None:
    rows = list(csv.DictReader(source.open())); grouped = defaultdict(list)
    for row in rows: grouped[row["method"]].append(row)
    fields = ["method", "valid_runs", "mean_energy_j", "mean_power_w", "mean_preceding_idle_power_w", "mean_idle_adjusted_power_w", "mean_f1", "mean_recall", "mean_fpr", "mean_balanced_accuracy"]
    output = []
    for method, values in sorted(grouped.items()):
        mean = lambda key: statistics.mean(float(x[key]) for x in values)
        output.append({
            "method": method, "valid_runs": len(values), "mean_energy_j": mean("energy_j"), "mean_power_w": mean("mean_power_w"),
            "mean_preceding_idle_power_w": mean("preceding_idle_power_w"),
            "mean_idle_adjusted_power_w": statistics.mean(float(x["mean_power_w"])-float(x["preceding_idle_power_w"]) for x in values),
            "mean_f1": mean("f1"), "mean_recall": mean("recall"), "mean_fpr": mean("fpr"), "mean_balanced_accuracy": mean("balanced_accuracy"),
        })
    with destination.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(output)


def copytree(source: Path, destination: Path) -> None:
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store", "controller.lock"))


def main() -> None:
    if DEST.exists() or ZIP.exists(): raise RuntimeError("final package target already exists")
    validation = json.loads((ROOT / "validation" / "final_validation.json").read_text())
    if validation.get("status") != "PASS": raise RuntimeError("final validation not PASS")
    if not (ROOT / "analysis" / "r1_factual_method_summary.csv").exists():
        summary(ROOT / "registries" / "r1_run_registry.csv", ROOT / "analysis" / "r1_factual_method_summary.csv")
    if not (ROOT / "analysis" / "r2_factual_method_summary.csv").exists():
        summary(ROOT / "registries" / "r2_run_registry.csv", ROOT / "analysis" / "r2_factual_method_summary.csv")
    factual = {
        "status": "EVIDENCE_COMPLETE_WITH_R3_NOT_EXECUTED",
        "existing_frozen_evidence": {"V1": "referenced by immutable SHA-256; not modified", "P0_P1": "referenced by immutable SHA-256; not modified"},
        "new_revision_physical_evidence": {"R1_valid_runs": 40, "R2_valid_runs": 60, "R3": "not executed because the predeclared four-state stream was not uniquely identified by the task bundle"},
        "software_only_diagnostics": {"R4A": "validation-selected frozen TinyDT threshold applied once to test"},
        "optional_reference_load": "not available; no improvised calibration source used",
        "interpretation": "factual evidence handoff only; no manuscript conclusion is asserted",
    }
    if not (ROOT / "analysis" / "FACTUAL_RESULTS_SUMMARY.json").exists():
        write_new(ROOT / "analysis" / "FACTUAL_RESULTS_SUMMARY.json", json.dumps(factual, indent=2, allow_nan=False)+"\n")
    readme = """# TNSM reviewer-revision evidence\n\nThis append-only package contains the R0 provenance audit, R1 fixed-rate confidence-cascade physical campaign, R2 prospectively frozen variable-load physical campaign, R4 software-only TinyDT threshold diagnostic, all raw frames/events, registries, validators, failures, hashes, and source/runtime bindings.\n\nThe original V1 and P0/P1 evidence are referenced by their frozen hashes and were neither modified nor rerun. R1 and R2 use the already frozen test pool and are explicitly post-hoc physical robustness experiments, not unseen-detection generalization.\n\nR3 was not executed: the task text requires four original observed-support encoded states, while the frozen observed-support artifact contains eight unique states and supplies no predeclared four-state subset. The stop record is retained. No subset was invented.\n\nR4A is a post-hoc threshold diagnostic. Its validation-selected threshold does not replace the threshold=0.5 primary result. R4B was not executed because no independently specified stable reference-load device was available; the Pi or its power supply was not improvised as a calibration source.\n\nThis is a factual evidence handoff, not a manuscript conclusion.\n"""
    if not (ROOT / "README.md").exists():
        write_new(ROOT / "README.md", readme)

    DEST.mkdir()
    for name in ("README.md", "REVISION_CONFIG_LOCK.json"):
        shutil.copy2(ROOT / name, DEST / name)
    for name in ("r0_source_audit", "r1_cascade_physical", "r2_variable_load", "r3_controller_power", "r4_threshold_and_reference", "registries", "analysis", "validation", "failures"):
        copytree(ROOT / name, DEST / name)
    frozen = DEST / "validation" / "frozen_runtime"
    frozen.mkdir()
    for name in ("worker.py", "controller.py", "measurement.py", "inputs_manifest.json", "inputs_manifest.sha256", "runtime_manifest.json"):
        shutil.copy2(ROOT / name, frozen / name)
    for name in ("config", "scheduler", "policies", "inputs", "traces", "r2_workloads", "protocol", "scripts"):
        copytree(ROOT / name, frozen / name)
    shutil.copy2("/Users/nuonanouyang/Downloads/TNSM_REVIEWER_REQUESTED_REVISION_CODEX_TASK_20260908.zip", DEST / "validation" / "TNSM_REVIEWER_REQUESTED_REVISION_CODEX_TASK_20260908.zip")

    manifest = DEST / "MANIFEST_SHA256.txt"
    content = sorted(path for path in DEST.rglob("*") if path.is_file() and path != manifest)
    with manifest.open("x") as handle:
        for path in content: handle.write(f"{digest(path)}  {path.relative_to(DEST)}\n")
    for line in manifest.read_text().splitlines():
        expected, relative = line.split("  ", 1)
        if digest(DEST / relative) != expected: raise RuntimeError(f"manifest mismatch: {relative}")
    with zipfile.ZipFile(ZIP, "x", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(DEST.rglob("*")):
            if path.is_file(): archive.write(path, f"{NAME}/{path.relative_to(DEST)}")
    with zipfile.ZipFile(ZIP) as archive:
        if archive.testzip() is not None: raise RuntimeError("ZIP CRC self-test failed")
    report = {"status": "PASS", "package": ZIP.name, "sha256": digest(ZIP), "size_bytes": ZIP.stat().st_size, "content_files_excluding_manifest": len(content), "zip_crc": "PASS"}
    print(json.dumps(report, indent=2))


if __name__ == "__main__": main()
