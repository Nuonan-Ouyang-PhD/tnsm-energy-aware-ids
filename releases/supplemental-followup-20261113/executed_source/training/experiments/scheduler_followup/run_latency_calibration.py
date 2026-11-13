"""Deploy new, byte-bound calibration code without modifying old runtimes."""
import fcntl
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "supplemental_scheduler_20261112/latency_calibration_02"
REMOTE = "/home/pi/tnsm-followup-20261112-calibration-02"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "pi@10.10.10.31"]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def main():
    OUT.mkdir(parents=True, exist_ok=False)
    save(OUT / "authorization.json", {
        "user_direction": "可以，用新编号执行修正后的标定替代运行，保留旧记录，不放宽门槛，通过后继续补跑。",
        "replacement_for": "latency_calibration_01",
        "replacement_reason": "correct non-atomic CPU counter sampling; unchanged 5% limit",
        "prior_scope": "supplemental scheduler study, shared observations and one-second deadline, no thermal capability claim",
        "phase": "bounded prospective latency calibration; not the paired outcome campaign",
        "test_access": False, "retraining_classifiers": False, "old_runtime_changes": False})
    status = {"status": "FAIL_STOP", "remote_started": False}
    with (OUT.parent / "calibration.lock").open("a+") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            with (OUT / "synthetic_regression.log").open("x") as log:
                tests = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover",
                    "-s", str(HERE), "-p", "test_*.py", "-v"], stdout=log, stderr=subprocess.STDOUT)
            if tests.returncode:
                raise RuntimeError("synthetic regressions failed")
            source_dir = OUT / "executed_source"
            source_dir.mkdir()
            names = ("core.py", "cpu_guard.py", "calibrate_latency.py")
            for name in names:
                with (source_dir / name).open("xb") as handle:
                    handle.write((HERE / name).read_bytes())
            manifest = json.loads((ROOT / "revision_experiments_20260908/runtime_manifest.json").read_text())["files"]
            bindings = {"source_sha256": {n: digest(source_dir/n) for n in names},
                        "input_sha256": {n: manifest["inputs/"+n] for n in
                            ("TinyDT.joblib", "LightLR.joblib", "MedRF.joblib", "HeavyMLP.pt", "warm_X.npy")},
                        "test_files": "not deployed or opened",
                        "fixed_measurements": "20 warmups/model; 200 batch100 timings/model; three probes each of 50/100/4000 rows/model",
                        "external_cpu_limit_fraction": .05, "maximum_temperature_c_exclusive": 70,
                        "hard_timeout_seconds": 180, "no_automatic_retry": True}
            save(source_dir / "bindings.json", bindings)
            save(OUT / "deployment_lock.json", {"bindings_sha256": digest(source_dir/"bindings.json"),
                 "remote_directory": REMOTE, "target": "pi@10.10.10.31", "source_sha256": bindings["source_sha256"]})
            # mkdir is exclusive: a previous attempt must never be overwritten.
            created = subprocess.run(SSH + ["mkdir " + REMOTE], capture_output=True, text=True, timeout=15)
            save(OUT / "mkdir_result.json", {"returncode": created.returncode, "stdout": created.stdout, "stderr": created.stderr})
            if created.returncode:
                raise RuntimeError("exclusive remote deployment directory creation failed")
            copied = subprocess.run(["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
                *map(str, sorted(source_dir.iterdir())), "pi@10.10.10.31:"+REMOTE+"/"],
                capture_output=True, text=True, timeout=30)
            save(OUT / "copy_result.json", {"returncode": copied.returncode, "stdout": copied.stdout, "stderr": copied.stderr})
            if copied.returncode:
                raise RuntimeError("new calibration deployment failed")
            command = SSH + ["cd " + REMOTE + " && /home/pi/tnsm-campaign-v1/venv/bin/python -B -u calibrate_latency.py"]
            save(OUT / "command.json", {"argv": command})
            with (OUT / "events.jsonl").open("x") as log, (OUT / "stderr.log").open("x") as err:
                status["remote_started"] = True
                result = subprocess.run(command, stdout=log, stderr=err, timeout=200)
            events = [json.loads(line) for line in (OUT/"events.jsonl").read_text().splitlines()]
            complete = [e for e in events if e["event"] == "complete"]
            failures = [e for e in events if e["event"] in ("failed", "monitor_failed")]
            if result.returncode or failures or len(complete) != 1:
                raise RuntimeError("calibration failed; original attempt retained")
            batches = [e for e in events if e["event"] == "batch_latency"]
            probes = [e for e in events if e["event"] == "service_probe"]
            cpu = [e for e in events if e["event"].startswith("cpu_interval")]
            if len(batches) != 800 or len(probes) != 36 or not cpu or not all(e["pass"] for e in cpu):
                raise RuntimeError("calibration event count or CPU evidence incomplete")
            status.update(status="PASS", batch_timings=800, service_probes=36,
                          cpu_intervals=len(cpu), formal_paired_runs=0,
                          measured_energy_joules=None, test_inputs_opened=False,
                          latency_registry=complete[0]["latency_registry"])
        except Exception as error:
            status["error"] = repr(error)
        finally:
            save(OUT / "report.json", status)
            with (OUT/"MANIFEST_SHA256.txt").open("x") as handle:
                for path in sorted(p for p in OUT.rglob("*") if p.is_file() and p.name != "MANIFEST_SHA256.txt"):
                    handle.write(digest(path) + "  " + str(path.relative_to(OUT)) + "\n")
    print(json.dumps(status, indent=2))
    return 0 if status["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
