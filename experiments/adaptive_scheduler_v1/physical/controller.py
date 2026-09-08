"""Mac controller for one excluded pilot and the fail-closed 40-run campaign."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import math
from pathlib import Path
import select
import subprocess
import threading
import time

import hid
import numpy as np

from measurement import decode, integrate, request


ROOT = Path(__file__).resolve().parent
REMOTE = "/home/pi/tnsm-adaptive-v1r2"
PYTHON = "/home/pi/tnsm-campaign-v1/venv/bin/python"
SSH = [
    "ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8",
    "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=6",
    "pi@pi4b8g.local",
]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def save_new(path: Path, value) -> None:
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def append_event(name: str, **fields) -> None:
    item = {"utc_epoch": time.time(), "event": name, **fields}
    with (ROOT / "execution" / "events.jsonl").open("a") as handle:
        handle.write(json.dumps(item, allow_nan=False) + "\n")
    print(json.dumps(item, allow_nan=False), flush=True)


def clock_check() -> list[dict]:
    checks = []
    command = "python3 -u -c 'import sys,time;print(\"ready\",flush=True);[(print(time.time(),flush=True)) for line in sys.stdin]'"
    process = subprocess.Popen(SSH + [command], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    try:
        if not select.select([process.stdout], [], [], 15)[0] or process.stdout.readline().strip() != "ready":
            raise RuntimeError("clock handshake timeout")
        for _ in range(5):
            before = time.time()
            process.stdin.write("ping\n")
            process.stdin.flush()
            if not select.select([process.stdout], [], [], 3)[0]:
                raise RuntimeError("clock response timeout")
            remote = float(process.stdout.readline())
            after = time.time()
            checks.append({
                "host_send": before,
                "host_receive": after,
                "remote_epoch": remote,
                "offset_interval": [remote - after, remote - before],
                "roundtrip_seconds": after - before,
            })
    finally:
        try:
            process.stdin.close()
        except Exception:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
    best = min(checks, key=lambda item: item["roundtrip_seconds"])
    if max(map(abs, best["offset_interval"])) > 0.25:
        raise RuntimeError("clock uncertainty too large")
    return checks


def binary_metrics(labels: np.ndarray, probabilities: np.ndarray) -> dict:
    prediction = probabilities >= 0.5
    truth = labels.astype(bool)
    tn = int(np.count_nonzero(~truth & ~prediction))
    fp = int(np.count_nonzero(~truth & prediction))
    fn = int(np.count_nonzero(truth & ~prediction))
    tp = int(np.count_nonzero(truth & prediction))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {
        "rows": int(len(labels)), "tn": tn, "fp": fp, "fn": fn, "tp": tp,
        "fpr": fp / (fp + tn) if fp + tn else 0.0,
        "precision": precision, "recall": recall, "f1": f1,
        "accuracy": (tn + tp) / len(labels),
    }


def run_one(spec: dict, device, baseline_volts: float) -> dict:
    run_dir = ROOT / "execution" / spec["run_id"]
    run_dir.mkdir(exist_ok=False)
    samples = []
    start_sent = False
    remote_log = None
    stderr = None
    process = None
    thread = None
    try:
        save_new(run_dir / "run_spec.json", spec)
        save_new(run_dir / "clock_check.json", clock_check())
        command = SSH + [
            f"cd {REMOTE} && {PYTHON} -B -u worker.py --method {spec['method']} --trace {spec['trace']} --seconds {spec['seconds']}"
        ]
        save_new(run_dir / "command.json", {"argv": command})
        remote_log = (run_dir / "pi_events.jsonl").open("x")
        stderr = (run_dir / "pi_stderr.log").open("x")
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
    except BaseException as error:
        if process is not None:
            process.terminate()
            process.wait(timeout=5)
        if remote_log is not None:
            remote_log.close()
        if stderr is not None:
            stderr.close()
        save_new(run_dir / "failure.json", {
            "status": "INVALID", "reason": repr(error), "phase": "preparation",
            "samples_retained": 0, "start_sent": False, "automatic_retry": False,
        })
        append_event("campaign_stopped", run_id=spec["run_id"], reason=repr(error), phase="preparation")
        raise
    state = {"ready": None, "failed": None, "complete": None, "decisions": [], "outcomes": [], "events": []}
    done = threading.Event()

    def reader() -> None:
        try:
            for line in process.stdout:
                remote_log.write(line)
                remote_log.flush()
                item = json.loads(line)
                state["events"].append(item)
                kind = item.get("event")
                if kind == "ready": state["ready"] = item
                elif kind == "failed": state["failed"] = item
                elif kind == "complete": state["complete"] = item
                elif kind == "decision": state["decisions"].append(item)
                elif kind == "outcome": state["outcomes"].append(item)
        except BaseException as error:
            state["failed"] = {"reader_error": repr(error)}
        finally:
            done.set()

    thread = threading.Thread(target=reader, daemon=True)
    thread.start()
    heartbeat_stop = threading.Event()
    try:
        ready_deadline = time.monotonic() + 1900
        while state["ready"] is None:
            if state["failed"] or done.is_set():
                raise RuntimeError(f"remote preparation failed: {state['failed']}")
            if time.monotonic() > ready_deadline:
                raise RuntimeError("remote ready timeout")
            time.sleep(0.2)
        device.write(request(250))
        pre_raw = bytes(device.read(64, 1000))
        decode(pre_raw, 250, baseline_volts)
        start_utc = time.time() + 5
        start_mono = time.monotonic() + start_utc - time.time()
        save_new(run_dir / "start.json", {"start_utc_epoch": start_utc, "prestart_adc_hex": pre_raw.hex(), "baseline_volts": baseline_volts})
        process.stdin.write(json.dumps({"start_utc": start_utc}) + "\n")
        process.stdin.flush()
        start_sent = True

        def heartbeat() -> None:
            while not heartbeat_stop.is_set():
                try:
                    process.stdin.write("heartbeat\n")
                    process.stdin.flush()
                except (BrokenPipeError, ValueError):
                    return
                heartbeat_stop.wait(1)

        threading.Thread(target=heartbeat, daemon=True).start()
        append_event("run_started", **spec, start_utc_epoch=start_utc, pid=process.pid)
        with (run_dir / "power.jsonl").open("x") as power_log:
            for index in range(spec["seconds"] + 1):
                target = start_mono + index
                delay = target - time.monotonic()
                if delay > 0:
                    time.sleep(delay)
                if time.monotonic() - target > 0.25:
                    raise RuntimeError("meter sampling deadline missed")
                if state["failed"]:
                    raise RuntimeError(f"Pi failed: {state['failed']}")
                if index > 30 and (not state["outcomes"] or state["outcomes"][-1]["window_index"] < index - 30):
                    raise RuntimeError("Pi event transport stale for 30 seconds")
                begin = time.monotonic()
                utc = time.time()
                device.write(request(index))
                raw = bytes(device.read(64, 1000))
                end = time.monotonic()
                if end - begin > 0.25:
                    raise RuntimeError("meter roundtrip too slow")
                values = decode(raw, index, baseline_volts)
                sample = {
                    "index": index, "utc_epoch_request": utc,
                    "request_monotonic": begin, "receive_monotonic": end,
                    "sample_monotonic": (begin + end) / 2,
                    "roundtrip_seconds": end - begin, "raw_hex": raw.hex(), **values,
                }
                samples.append(sample)
                power_log.write(json.dumps(sample, allow_nan=False) + "\n")
                power_log.flush()
                if index % 60 == 0:
                    append_event("run_progress", run_id=spec["run_id"], seconds=index, watts=values["watts"], volts=values["volts"])
        exit_code = process.wait(timeout=15)
        thread.join(timeout=5)
        if exit_code != 0 or state["failed"] or not state["complete"]:
            raise RuntimeError(f"remote completion invalid: exit={exit_code}, failed={state['failed']}")
        decisions = state["decisions"]
        outcomes = state["outcomes"]
        seconds = spec["seconds"]
        if len(decisions) != seconds or len(outcomes) != seconds:
            raise RuntimeError("wrong decision/outcome count")
        if [x["window_index"] for x in decisions] != list(range(seconds)) or [x["window_index"] for x in outcomes] != list(range(seconds)):
            raise RuntimeError("nonsequential window indices")
        ordered = [x["event"] for x in state["events"] if x["event"] in ("decision", "outcome")]
        if ordered != [name for _ in range(seconds) for name in ("decision", "outcome")]:
            raise RuntimeError("decision/outcome causal log order invalid")
        if any(x["rows"] != 100 or len(x["probabilities"]) != 100 for x in outcomes):
            raise RuntimeError("prediction row count mismatch")
        if any(x["throttled"] != "throttled=0x0" for x in outcomes):
            raise RuntimeError("throttle flag observed")
        if any(not 0 < b["utc_epoch"] - a["utc_epoch"] <= 1.5 for a, b in zip(outcomes, outcomes[1:])):
            raise RuntimeError("Pi window timestamp gap invalid")
        energy, duration = integrate(samples)
        probabilities = np.concatenate([np.asarray(x["probabilities"], dtype=np.float32) for x in outcomes])
        labels = np.load(ROOT / "traces" / f"{spec['trace']}.labels.npy", allow_pickle=False)[:seconds * 100]
        metrics = binary_metrics(labels, probabilities)
        actions = [x["selected_action"] for x in outcomes]
        action_counts = {name: actions.count(name) for name in ("TinyDT", "LightLR", "MedRF", "HeavyMLP")}
        switched = [bool(x["switched"]) for x in decisions]
        inference_ms = [x["inference_ns"] / 1e6 for x in outcomes]
        switch_latency = [value for value, flag in zip(inference_ms, switched) if flag]
        hold_latency = [value for value, flag in zip(inference_ms, switched) if not flag]
        posthoc = {
            "labels_loaded_only_after_complete_frozen_schedule": True,
            "metrics": metrics,
            "action_counts": action_counts,
            "switches": int(sum(switched)),
            "inference_batch_ms_mean": float(np.mean(inference_ms)),
            "inference_batch_ms_p95": float(np.quantile(inference_ms, 0.95)),
            "first_batch_after_switch_ms_mean": float(np.mean(switch_latency)) if switch_latency else None,
            "non_switch_batch_ms_mean": float(np.mean(hold_latency)) if hold_latency else None,
            "selected_probabilities_float32_sha256": hashlib.sha256(probabilities.astype("<f4").tobytes()).hexdigest(),
        }
        save_new(run_dir / "posthoc.json", posthoc)
        summary = {
            **spec, "status": "PASS", "power_samples": len(samples),
            "telemetry_windows": len(outcomes), "decision_windows": len(decisions),
            "observed_duration_seconds": duration, "energy_joules": energy,
            "mean_watts": energy / duration,
            "voltage_min": min(x["volts"] for x in samples),
            "voltage_max": max(x["volts"] for x in samples),
            "maximum_temperature_c": max(x["post_temperature_c"] for x in outcomes),
            "missing_power_samples": 0, "missing_telemetry_windows": 0,
            "throttle_events": 0, "posthoc": posthoc,
            "measurement_scope": "uncalibrated KM003C USB load-side whole-Pi input; user-accepted above-label supply; not AC-wall power",
        }
        save_new(run_dir / "summary.json", summary)
        append_event("run_complete", run_id=spec["run_id"], method=spec["method"], energy_joules=energy, mean_watts=energy / duration, f1=metrics["f1"])
        return summary
    except BaseException as error:
        save_new(run_dir / "failure.json", {"status": "INVALID", "reason": repr(error), "samples_retained": len(samples), "start_sent": start_sent, "automatic_retry": False})
        append_event("campaign_stopped", run_id=spec["run_id"], reason=repr(error))
        raise
    finally:
        heartbeat_stop.set()
        try:
            process.stdin.close()
        except Exception:
            pass
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.terminate()
            process.wait(timeout=5)
        thread.join(timeout=3)
        remote_log.close()
        stderr.close()


def validate_runtime() -> dict:
    manifest = json.loads((ROOT / "runtime_manifest.json").read_text())
    for relative, expected in manifest["files"].items():
        if digest(ROOT / relative) != expected:
            raise RuntimeError(f"local runtime hash mismatch: {relative}")
    output = subprocess.check_output(SSH + [f"cd {REMOTE} && shasum -a 256 -c inputs_manifest.sha256"], text=True)
    if "FAILED" in output:
        raise RuntimeError("remote manifest failed")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["pilot", "formal"], required=True)
    args = parser.parse_args()
    lock = (ROOT / "controller.lock").open("a")
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    (ROOT / "execution").mkdir(exist_ok=True)
    manifest = validate_runtime()
    device = hid.device()
    device.open(0x5FC9, 0x0063, "075356")
    try:
        device.write(request(249))
        raw = bytes(device.read(64, 1000))
        baseline = decode(raw, 249)["volts"]
        if not (ROOT / "execution" / "meter_start.json").exists():
            save_new(ROOT / "execution" / "meter_start.json", {"baseline_volts": baseline, "raw_hex": raw.hex(), "meter_serial": "075356"})
        if args.mode == "pilot":
            spec = {"run_id": "pilot-001-round-robin", "method": "Pilot-RoundRobin", "trace": "pilot_validation_401", "seconds": 120, "formal_statistics": False}
            result = run_one(spec, device, baseline)
            gate = {
                "status": "PASS",
                "pilot_excluded_from_formal_statistics": True,
                "pilot_summary_sha256": digest(ROOT / "execution" / spec["run_id"] / "summary.json"),
                "config_sha256": manifest["config_sha256"],
                "authorization_sha256": manifest["authorization_sha256"],
                "schedule_sha256": manifest["schedule_sha256"],
                "frozen_policy_identities": manifest["frozen_policy_identities"],
                "formal_execution_may_start_without_new_approval": True,
            }
            save_new(ROOT / "pilot_gate.json", gate)
            append_event("pilot_pass", **gate)
            print(json.dumps(result, indent=2), flush=True)
        else:
            gate = json.loads((ROOT / "pilot_gate.json").read_text())
            if gate.get("status") != "PASS" or digest(ROOT / "execution" / "pilot-001-round-robin" / "summary.json") != gate["pilot_summary_sha256"]:
                raise RuntimeError("pilot gate missing or invalid")
            for field in ("config_sha256", "authorization_sha256", "schedule_sha256", "frozen_policy_identities"):
                if gate.get(field) != manifest.get(field):
                    raise RuntimeError(f"pilot/runtime binding mismatch: {field}")
            schedule = json.loads((ROOT / "bindings" / "physical_schedule_v1.json").read_text())
            completed = []
            for item in schedule["runs"]:
                spec = {**item, "trace": f"formal_test_{item['trace_seed']}", "formal_statistics": True}
                completed.append(run_one(spec, device, baseline))
            summary = {
                "status": "PASS", "formal_runs": len(completed), "paired_blocks": 10,
                "runs": [{"run_id": x["run_id"], "method": x["method"], "trace_seed": x["trace_seed"], "energy_joules": x["energy_joules"], "mean_watts": x["mean_watts"], "f1": x["posthoc"]["metrics"]["f1"]} for x in completed],
            }
            save_new(ROOT / "execution" / "formal_summary.json", summary)
            append_event("formal_campaign_complete", formal_runs=40, paired_blocks=10)
    finally:
        device.close()


if __name__ == "__main__":
    main()
