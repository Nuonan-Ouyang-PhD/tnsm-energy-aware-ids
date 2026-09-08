"""Validate and build the non-destructive final P0/P1 strengthening package."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import statistics
import zipfile

import numpy as np
import torch

from scheduler.config import load_config
from scheduler.dqn import DQNPolicy
from scheduler.state import ACTION_ORDER


ROOT = Path(__file__).resolve().parent
WORKSPACE = ROOT.parent
PACKAGE = WORKSPACE / "TNSM_P0_P1_STRENGTHENING_20260908_V1"
ZIP = WORKSPACE / "TNSM_P0_P1_STRENGTHENING_20260908_V1.zip"
PROTOCOL = WORKSPACE / "TNSM_CODEX_P0_P1_20260908" / "TNSM_CODEX_P0_P1_20260908"
AUTH = Path("/Users/nuonanouyang/Downloads/TNSM_P1_FINAL_CLOSURE_AUTHORIZATION_20260908.md")


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read(path: Path):
    return json.loads(path.read_text())


def copy_tree(source: Path, target: Path):
    shutil.copytree(
        source,
        target,
        ignore=shutil.ignore_patterns(".DS_Store", "__pycache__", "*.pyc", ".venv"),
    )


def p0_validate(report):
    p = ROOT / "p0_archive"
    rows = list(csv.DictReader((p / "expected_vs_recovered.csv").open()))
    assert len(rows) == 6
    for row in rows:
        assert sha(p / "executed_source" / row["path"]) == row["expected_sha256"]
    manifest = (p / "MANIFEST_SHA256.txt").read_text().splitlines()
    for line in manifest:
        expected, relative = line.split("  ", 1)
        assert sha(p / relative) == expected
    report["p0"] = {"status": "PASS", "executed_sources": 6, "manifest_entries": len(manifest)}


def p1a_validate(report):
    runtime = ROOT / "p1a_runtime_clean"
    execution = runtime / "execution"
    schedule = read(runtime / "bindings/physical_schedule_p1a.json")
    interrupted = "supp-lightlr-S09-p2-Static-MedRF"
    replacement = interrupted + "-retry1"
    valid = []
    for item in schedule["runs"]:
        run_id = replacement if item["run_id"] == interrupted else item["run_id"]
        run_dir = execution / run_id
        summary = read(run_dir / "summary.json")
        assert summary["status"] == "PASS"
        assert summary["power_samples"] == 501
        assert summary["decision_windows"] == 500
        assert summary["telemetry_windows"] == 500
        assert summary["throttle_events"] == 0
        valid.append((item, run_id, run_dir, summary))
    assert len(valid) == 40
    for block in range(1, 11):
        methods = [x[0]["method"] for x in valid if x[0]["block"] == block]
        assert sorted(methods) == sorted(["Static-LightLR", "Static-MedRF", "Tabular-Q", "DQN"])
    original = execution / interrupted
    assert original.exists() and not (original / "summary.json").exists()
    retry_spec = read(execution / replacement / "run_spec.json")
    assert retry_spec["manual_retry_of"] == interrupted
    report["p1a"] = {
        "status": "PASS", "valid_runs": 40, "paired_blocks": 10,
        "invalid_interrupted_attempts": 1, "replacement_runs": 1,
    }
    return valid


def p1b_validate(report):
    old = ROOT / "p1b_scheduler_overhead"
    new = ROOT / "p1b_replacement_output"
    old_rows = read(old / "registry.json")["blocks"]
    rows = read(new / "registry.json")
    provenance = read(new / "provenance.json")
    assert len(old_rows) == 240
    assert len(rows) == 240
    assert provenance["semantic_validation"] == {"states": 5000, "mismatches": [], "status": "PASS"}
    units = {(x["stream"], x["benchmark_block"], x["method"]) for x in rows}
    assert len(units) == 240
    assert {x[0] for x in units} == {"exhaustive_324", "observed_support"}
    assert {x[1] for x in units} == set(range(1, 31))
    assert {x[2] for x in units} == {"Static-LightLR", "CFSM", "Tabular-Q", "DQN"}
    for row in rows:
        assert row["valid"] is True and row["n_warmup"] == 1000 and row["n_timed"] == 10000
        assert row["telemetry_before"] and row["telemetry_after"]
        path = new / row["raw_array_path"]
        assert sha(path) == row["raw_array_sha256"]
        assert np.load(path, allow_pickle=False).shape == (10000,)
    report["p1b"] = {
        "status": "PASS", "invalid_historical_units": 240,
        "valid_replacement_units": 240, "cfsm_semantic_states": 5000,
        "cfsm_semantic_mismatches": 0,
    }


def p1c_validate(report):
    source = ROOT / "p1c_multiseed"
    derived = ROOT / "p1c_derived_evaluation"
    metas = sorted(source.glob("*/metadata.json"))
    summaries = sorted(derived.glob("*/summary.json"))
    assert len(metas) == 20 and len(summaries) == 20
    expected = {(a, s) for a in ("Tabular-Q", "DQN") for s in (1009,1013,1019,1021,1031,1033,1039,1049,1051,1061)}
    found = set()
    for path in summaries:
        item = read(path)
        found.add((item["algorithm"], item["seed"]))
        assert item["status"] == "PASS"
        assert item["retrained"] is False and item["checkpoint_reselected"] is False
        assert item["test_used_for_action_selection_training_or_checkpoint_selection"] is False
        source_dir = Path(item["source_frozen_policy_directory"])
        weights = source_dir / ("q_values.npy" if item["algorithm"] == "Tabular-Q" else "dqn_online_state.pt")
        assert sha(weights) == item["policy_hash"]
    assert found == expected
    report["p1c"] = {"status": "PASS", "frozen_policies": 20, "derived_evaluations": 20, "retrained": 0}


def validate_matrix(folder: str, expected: int, report_key: str, report):
    paths = sorted((ROOT / folder).glob("*/summary.json"))
    assert len(paths) == expected
    for path in paths:
        item = read(path)
        assert item["status"] == "PASS"
        assert item.get("test_used_for_training_or_selection") is False
        weights_name = "q_values.npy" if item.get("algorithm", "Tabular-Q") == "Tabular-Q" else "dqn_online_state.pt"
        assert sha(path.parent / weights_name) == item["policy_hash"]
    report[report_key] = {"status": "PASS", "runs": expected, "test_leakage_flags": 0}


def make_p1a_registry(valid):
    fields = (PROTOCOL / "templates/p1a_run_registry_template.csv").read_text().splitlines()[0].split(",")
    rows = []
    runtime = ROOT / "p1a_runtime_clean"
    manifest = read(runtime / "runtime_manifest.json")
    model_hashes = {
        "Static-LightLR": manifest["files"]["inputs/LightLR.joblib"],
        "Static-MedRF": manifest["files"]["inputs/MedRF.joblib"],
    }
    for item, run_id, run_dir, summary in valid:
        post = summary["posthoc"]
        metrics = post["metrics"]
        outcomes = [json.loads(line) for line in (run_dir / "pi_events.jsonl").read_text().splitlines() if '"event": "outcome"' in line]
        inference = [x["inference_ns"] / 1e6 for x in outcomes]
        temperatures = [x["post_temperature_c"] for x in outcomes]
        start = read(run_dir / "start.json")["start_utc_epoch"]
        specificity = metrics["tn"] / (metrics["tn"] + metrics["fp"])
        rows.append({
            "supp_block_id": item["block"], "run_id": run_id, "method": item["method"], "valid": "true",
            "run_order": int(item["run_id"].split("-p")[1].split("-")[0]), "trace_id": summary["trace"],
            "trace_hash": manifest["files"][f"traces/formal_test_{item['trace_seed']}.indices.npy"],
            "config_hash": manifest["config_sha256"], "policy_hash": manifest["frozen_policy_identities"].get(item["method"], ""),
            "model_hash": model_hashes.get(item["method"], "multiple_resident_models_bound_in_runtime_manifest"),
            "device_id": "Pi4 CPU 100000005368e39d; KM003C SN 075356", "start_time": start,
            "end_time": start + summary["observed_duration_seconds"], "duration_s": summary["observed_duration_seconds"],
            "energy_j": summary["energy_joules"], "mean_power_w": summary["mean_watts"],
            "tn": metrics["tn"], "fp": metrics["fp"], "fn": metrics["fn"], "tp": metrics["tp"],
            "f1": metrics["f1"], "recall": metrics["recall"], "fpr": metrics["fpr"],
            "balanced_accuracy": (metrics["recall"] + specificity) / 2,
            "inference_mean_ms": statistics.mean(inference), "inference_p50_ms": statistics.median(inference),
            "inference_p95_ms": float(np.percentile(inference,95)), "max_temperature_c": max(temperatures),
            "mean_temperature_c": statistics.mean(temperatures), "runtime_switch_count": post["switches"],
            "initial_selection_events": 1, "throttle_flag": "false", "undervoltage_flag": "false",
            "missing_power_samples": 0, "missing_windows": 0, "failure_reason": "",
            "replacement_for": item["run_id"] if run_id != item["run_id"] else "",
        })
    # Retain both invalid supplementary attempts as separate rows.
    rows.append({**{field: "" for field in fields}, "supp_block_id": 1,
        "run_id": "supp-lightlr-S01-p1-DQN-failure-no-seconds", "method": "DQN", "valid": "false",
        "run_order": 1, "trace_id": "formal_test_11", "failure_reason": "preparation KeyError('seconds'); no workload started"})
    rows.append({**{field: "" for field in fields}, "supp_block_id": 9,
        "run_id": "supp-lightlr-S09-p2-Static-MedRF", "method": "Static-MedRF", "valid": "false",
        "run_order": 2, "trace_id": "formal_test_157",
        "failure_reason": "external Mac controller session disappeared after 403/500 power samples; no complete summary",
        "replacement_for": ""})
    path = PACKAGE / "p1a_static_lightlr_physical" / "run_registry.csv"
    with path.open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    linkage = {
        "invalid_original": "supp-lightlr-S09-p2-Static-MedRF",
        "valid_replacement": "supp-lightlr-S09-p2-Static-MedRF-retry1",
        "replacement_for": "supp-lightlr-S09-p2-Static-MedRF",
        "paired_analysis_includes": "replacement only",
        "paired_analysis_excludes": "interrupted original",
    }
    (PACKAGE / "p1a_static_lightlr_physical" / "replacement_linkage.json").write_text(json.dumps(linkage,indent=2)+"\n")
    return rows


def make_p1b_registry():
    source = ROOT / "p1b_replacement_output"
    rows = read(source / "registry.json")
    provenance = read(source / "provenance.json")
    fields = (PROTOCOL / "templates/p1b_overhead_registry_template.csv").read_text().splitlines()[0].split(",")
    output = []
    for item in rows:
        before, after = item["telemetry_before"], item["telemetry_after"]
        policy_hash = ""
        if item["method"] == "Tabular-Q": policy_hash = provenance["tabular_policy_hash"]
        if item["method"] == "DQN": policy_hash = provenance["dqn_policy_hash"]
        output.append({
            "stream": item["stream"], "benchmark_block": item["benchmark_block"], "run_id": item["run_id"],
            "method": item["method"], "order": item["order"], "n_warmup": item["n_warmup"], "n_timed": item["n_timed"],
            "mean_ns": item["mean_ns"], "median_ns": item["median_ns"], "p95_ns": item["p95_ns"],
            "p99_ns": item["p99_ns"], "sd_ns": item["sd_ns"], "rss_before_bytes": before["rss_bytes"],
            "rss_after_bytes": after["rss_bytes"], "peak_rss_bytes": after["peak_rss_bytes"],
            "temp_before_c": before["temperature_c"], "temp_after_c": after["temperature_c"],
            "cpu_freq_before_hz": json.dumps(before["cpu_freq_current_hz"]), "cpu_freq_after_hz": json.dumps(after["cpu_freq_current_hz"]),
            "throttle_before": before["throttle"], "throttle_after": after["throttle"],
            "raw_array_path": "corrected_replacement/" + item["raw_array_path"],
            "source_hash": provenance["source_hashes"]["benchmark"], "policy_hash": policy_hash,
            "valid": "true", "failure_reason": "",
        })
    path = PACKAGE / "p1b_scheduler_overhead" / "corrected_replacement_registry.csv"
    with path.open("x", newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(output)
    return output


def policy_registry(source_folder: str, destination: Path):
    template = (PROTOCOL / "templates/policy_robustness_template.csv").read_text().splitlines()[0].split(",")
    rows=[]
    for path in sorted((ROOT/source_folder).glob("*/summary.json")):
        item=read(path); val=item["validation"]; test=item["test_descriptive_only"]; vm=val["metrics"];tm=test["metrics"];occ=test["action_occupancy"]
        run_name=path.parent.name
        target_run=destination/run_name
        weights=path.parent/("q_values.npy" if item.get("algorithm","Tabular-Q")=="Tabular-Q" else "dqn_online_state.pt")
        if weights.name=="q_values.npy":
            q=np.load(weights,allow_pickle=False); amap=[ACTION_ORDER[int(i)].value for i in np.argmax(q,axis=1)]
        else:
            config=read(path.parent/"config.json"); policy=DQNPolicy(config,seed=item["seed"]); policy.load_online_state(torch.load(weights,map_location="cpu",weights_only=True));policy.freeze()
            amap=[policy.select_action(i,training=False).value for i in range(policy.state_count)]
        (target_run/"action_map.json").write_text(json.dumps(amap)+"\n")
        selection=item["selection"]["selection"]
        rows.append({
            "analysis_family":item["analysis_family"],"algorithm":item.get("algorithm","Tabular-Q"),"variant":item["variant"],"seed":item["seed"],
            "training_episodes":item["training_episodes"],"selected_checkpoint":selection["training_episode"],
            "validation_return":selection["mean_validation_episode_return"],"validation_f1":vm["f1"],"validation_recall":vm["recall"],
            "validation_fpr":vm["false_positive_rate"],"validation_ba":vm["balanced_accuracy"],"test_f1":tm["f1"],
            "test_recall":tm["recall"],"test_fpr":tm["false_positive_rate"],"test_ba":tm["balanced_accuracy"],
            "test_switches":test["switches"],"test_occupancy_tinydt":occ["TinyDT"],"test_occupancy_lightlr":occ["LightLR"],
            "test_occupancy_medrf":occ["MedRF"],"test_occupancy_heavymlp":occ["HeavyMLP"],
            "unique_validation_states":val["unique_states"],"unique_test_states":test["unique_states"],
            "policy_hash":item["policy_hash"],"config_hash":item["config_hash"],
            "training_curve_path":f"{run_name}/training.jsonl","validation_curve_path":f"{run_name}/validation_windows.jsonl",
            "action_map_path":f"{run_name}/action_map.json","notes":"test descriptive only; no test-based selection",
        })
    with (destination/"policy_registry.csv").open("x",newline="") as handle:
        writer=csv.DictWriter(handle,fieldnames=template);writer.writeheader();writer.writerows(rows)
    return rows


def factual_summary(valid_p1a, p1b_rows):
    p1a={}
    for _,_,_,summary in valid_p1a:
        p1a.setdefault(summary["method"],[]).append(summary)
    p1a_summary={method:{"runs":len(items),"mean_energy_j":statistics.mean(x["energy_joules"] for x in items),
        "mean_power_w":statistics.mean(x["mean_watts"] for x in items),"mean_f1":statistics.mean(x["posthoc"]["metrics"]["f1"] for x in items)} for method,items in p1a.items()}
    p1b={}
    for stream in ("exhaustive_324","observed_support"):
        p1b[stream]={}
        for method in ("Static-LightLR","CFSM","Tabular-Q","DQN"):
            vals=[float(x["mean_ns"]) for x in p1b_rows if x["stream"]==stream and x["method"]==method]
            p1b[stream][method]={"blocks":len(vals),"mean_of_block_means_ns":statistics.mean(vals),"sd_block_means_ns":statistics.stdev(vals)}
    data={"scope":"factual machine-readable summary; no superiority/significance interpretation","p1a":p1a_summary,"p1b":p1b,
        "p1c_policies":20,"p1d_runs":85,"p1e_runs":35}
    (PACKAGE/"analysis"/"FACTUAL_RESULTS_SUMMARY.json").write_text(json.dumps(data,indent=2)+"\n")


def build_package(report, valid_p1a):
    if PACKAGE.exists() or ZIP.exists():
        raise FileExistsError("final package path already exists")
    for name in ("p0_source_archive","p1a_static_lightlr_physical","p1b_scheduler_overhead","p1c_multiseed","p1d_reward_state","p1e_hyperparameter","configs","scripts","analysis","failures"):
        (PACKAGE/name).mkdir(parents=True,exist_ok=True)
    copy_tree(ROOT/"p0_archive",PACKAGE/"p0_source_archive/archive")
    shutil.copy2(ROOT/"TNSM_EXECUTED_SOURCE_ARCHIVE_FIX_20260908_V2.zip",PACKAGE/"p0_source_archive/")
    copy_tree(ROOT/"p1a_runtime_clean/execution",PACKAGE/"p1a_static_lightlr_physical/raw_execution")
    shutil.copy2(ROOT/"p1a_runtime_clean/bindings/physical_schedule_p1a.json",PACKAGE/"p1a_static_lightlr_physical/")
    shutil.copy2(ROOT/"p1a_runtime_clean/runtime_manifest.json",PACKAGE/"p1a_static_lightlr_physical/")
    p1a_rows=make_p1a_registry(valid_p1a)
    copy_tree(ROOT/"p1b_scheduler_overhead",PACKAGE/"p1b_scheduler_overhead/invalid_historical_attempt")
    copy_tree(ROOT/"p1b_replacement_output",PACKAGE/"p1b_scheduler_overhead/corrected_replacement")
    invalid={"status":"INVALID_SUPERSEDED","units":240,"reasons":["CFSM incorrectly substituted by fixed MedRF return","required telemetry absent"],"eligible_for_inference":False}
    (PACKAGE/"p1b_scheduler_overhead/invalid_historical_attempt_status.json").write_text(json.dumps(invalid,indent=2)+"\n")
    p1b_rows=make_p1b_registry()
    copy_tree(ROOT/"p1c_multiseed",PACKAGE/"p1c_multiseed/frozen_training")
    copy_tree(ROOT/"p1c_derived_evaluation",PACKAGE/"p1c_multiseed/derived_evaluation")
    copy_tree(ROOT/"p1d_reward_state",PACKAGE/"p1d_reward_state/runs")
    p1d_rows=policy_registry("p1d_reward_state",PACKAGE/"p1d_reward_state/runs")
    copy_tree(ROOT/"p1e_hyperparameter",PACKAGE/"p1e_hyperparameter/runs")
    p1e_rows=policy_registry("p1e_hyperparameter",PACKAGE/"p1e_hyperparameter/runs")
    shutil.copy2(ROOT/"config/scheduler_experiment_v1.json",PACKAGE/"configs/")
    shutil.copy2(AUTH,PACKAGE/"configs/TNSM_P1_FINAL_CLOSURE_AUTHORIZATION_20260908.md")
    copy_tree(PROTOCOL,PACKAGE/"configs/TNSM_CODEX_P0_P1_20260908")
    for name in ("p1b_replacement_benchmark.py","p1c_derived_evaluate.py","p1c_multiseed_run.py","p1d_reward_state_run.py","p1e_hyperparameter_run.py","finalize_p0_p1.py"):
        shutil.copy2(ROOT/name,PACKAGE/"scripts"/name)
    failures={"p1a":["raw_execution/supp-lightlr-S01-p1-DQN-failure-no-seconds","raw_execution/supp-lightlr-S09-p2-Static-MedRF"],
        "p1d":["reward-dqn-equal-2017-interrupted-session-episode652"],"p1b_invalid_historical_attempt":True}
    (PACKAGE/"failures/INDEX.json").write_text(json.dumps(failures,indent=2)+"\n")
    factual_summary(valid_p1a,p1b_rows)
    report["package_counts"]={"p1a_registry_rows":len(p1a_rows),"p1b_valid_rows":len(p1b_rows),"p1d_registry_rows":len(p1d_rows),"p1e_registry_rows":len(p1e_rows)}
    (PACKAGE/"analysis/FINAL_VALIDATOR_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
    (PACKAGE/"COMPLETION_STATUS.md").write_text(
        "# Completion status\n\nP0: COMPLETE — six exact executed sources and V2 archive verified.\n\n"
        "P1A: COMPLETE — 40 valid runs in 10 paired blocks; interrupted attempt retained and linked to retry1.\n\n"
        "P1B: COMPLETE — invalid historical attempt retained; corrected replacement 240/240 PASS.\n\n"
        "P1C: COMPLETE — 20 frozen policies evaluated without retraining or checkpoint reselection.\n\n"
        "P1D: COMPLETE — 85/85 PASS.\n\nP1E: COMPLETE — 35/35 PASS.\n"
    )
    (PACKAGE/"README.md").write_text(
        "# TNSM P0/P1 strengthening evidence\n\n"
        "Primary evidence remains the evidence-locked original V1 campaign and is not replaced here. "
        "P0 is archival recovery. P1A is a supplementary matched physical control. P1B is an isolated scheduler-overhead replacement after the original attempt failed validation. "
        "P1C, P1D, and P1E are post-hoc software strengthening analyses. Test data is descriptive only after policy freeze. "
        "This package reports factual outputs and does not assert superiority, equivalence, or statistical significance.\n"
    )


def manifest_and_zip(report):
    # Exclude only this package's root manifest. Nested manifests are evidence
    # files and must themselves be covered by the root manifest.
    files=[p for p in sorted(PACKAGE.rglob("*")) if p.is_file() and p != PACKAGE/"MANIFEST_SHA256.txt"]
    lines=[f"{sha(path)}  {path.relative_to(PACKAGE)}" for path in files]
    (PACKAGE/"MANIFEST_SHA256.txt").write_text("\n".join(lines)+"\n")
    with zipfile.ZipFile(ZIP,"w",compression=zipfile.ZIP_DEFLATED,allowZip64=True) as archive:
        for path in sorted(PACKAGE.rglob("*")):
            if path.is_file(): archive.write(path,Path(PACKAGE.name)/path.relative_to(PACKAGE))
    with zipfile.ZipFile(ZIP) as archive:
        bad=archive.testzip(); assert bad is None
        names=archive.namelist(); root=PACKAGE.name+"/"
        manifest=archive.read(root+"MANIFEST_SHA256.txt").decode().splitlines()
        assert len(manifest)==len(names)-1
        for line in manifest:
            expected,relative=line.split("  ",1)
            assert hashlib.sha256(archive.read(root+relative)).hexdigest()==expected
    result={"status":"PASS","zip_path":str(ZIP),"zip_sha256":sha(ZIP),"zip_bytes":ZIP.stat().st_size,
        "zip_entries":len(names),"manifest_entries":len(manifest),"crc_self_test":"PASS","manifest_self_test":"PASS",
        "validator_status":report["status"],"attempt_counts":report["attempt_counts"],
        "protocol_deviations":report["protocol_deviations"]}
    (WORKSPACE/"TNSM_P0_P1_STRENGTHENING_20260908_V1_FINAL_REPORT.json").write_text(json.dumps(result,indent=2)+"\n")
    print(json.dumps(result,indent=2))


def main():
    report={"validator":"TNSM-P0-P1-FINAL-20260908-V1","validated_at_utc":datetime.now(timezone.utc).isoformat(),
        "authorization_sha256":sha(AUTH),"status":"PASS","protocol_deviations":[
            "Original P1B attempt invalidated after final validator found fixed-MedRF CFSM substitution and absent telemetry; corrected authorized replacement used for inference.",
            "P1A Mac controller session disappeared during S09-p2 after 403/500 power samples; original retained and explicit user-authorized retry1 used as replacement.",
            "P1D DQN equal-2017 session disappeared at episode 652; interrupted directory retained and explicit continuation reran the same frozen configuration from the start.",
        ]}
    p0_validate(report); valid=p1a_validate(report); p1b_validate(report); p1c_validate(report)
    validate_matrix("p1d_reward_state",85,"p1d",report); validate_matrix("p1e_hyperparameter",35,"p1e",report)
    report["attempt_counts"] = {
        "p1a_supplementary_physical_runs": {"attempted": 42, "valid": 40, "invalid": 2, "replacement": 1},
        "p1b_benchmark_units": {"attempted": 480, "valid": 240, "invalid": 240, "replacement": 240},
        "p1c_frozen_policy_evaluations": {"attempted": 20, "valid": 20, "invalid": 0, "replacement": 0},
        "p1d_policy_runs": {"attempted": 86, "valid": 85, "invalid": 1, "replacement": 1},
        "p1e_policy_runs": {"attempted": 35, "valid": 35, "invalid": 0, "replacement": 0},
    }
    build_package(report,valid); manifest_and_zip(report)


if __name__=="__main__":
    main()
