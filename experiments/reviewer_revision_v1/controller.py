"""Mac coordinator and KM003C recorder for frozen reviewer-revision runs."""
from __future__ import annotations

import argparse
import csv
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
REMOTE = "/home/pi/tnsm-reviewer-revision-v1"
PYTHON = "/home/pi/tnsm-campaign-v1/venv/bin/python"
SSH = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "-o", "ServerAliveInterval=5", "-o", "ServerAliveCountMax=6", "pi@pi4b8g.local"]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def save_new(path: Path, value) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        handle.write("\n")


def append_event(event: str, **fields) -> None:
    item = {"utc_epoch": time.time(), "event": event, **fields}
    with (ROOT / "execution_events.jsonl").open("a") as handle:
        handle.write(json.dumps(item, allow_nan=False) + "\n")
    print(json.dumps(item, allow_nan=False), flush=True)


def clock_check() -> list[dict]:
    command = "python3 -u -c 'import time;print(\"ready\",flush=True);[(print(time.time(),flush=True)) for line in __import__(\"sys\").stdin]'"
    process = subprocess.Popen(SSH + [command], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
    checks = []
    try:
        if not select.select([process.stdout], [], [], 15)[0] or process.stdout.readline().strip() != "ready":
            raise RuntimeError("clock handshake timeout")
        for _ in range(5):
            before = time.time()
            process.stdin.write("ping\n"); process.stdin.flush()
            if not select.select([process.stdout], [], [], 3)[0]:
                raise RuntimeError("clock response timeout")
            remote = float(process.stdout.readline())
            after = time.time()
            checks.append({"host_send": before, "host_receive": after, "remote_epoch": remote, "offset_interval": [remote-after, remote-before], "roundtrip_seconds": after-before})
    finally:
        try: process.stdin.close()
        except Exception: pass
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.terminate(); process.wait(timeout=5)
    best = min(checks, key=lambda x: x["roundtrip_seconds"])
    if max(map(abs, best["offset_interval"])) > 0.25:
        raise RuntimeError("clock uncertainty too large")
    return checks


def binary_metrics(labels: np.ndarray, probabilities: np.ndarray) -> dict:
    pred, truth = probabilities >= 0.5, labels.astype(bool)
    tn = int(np.count_nonzero(~truth & ~pred)); fp = int(np.count_nonzero(~truth & pred))
    fn = int(np.count_nonzero(truth & ~pred)); tp = int(np.count_nonzero(truth & pred))
    recall = tp/(tp+fn) if tp+fn else 0.0
    specificity = tn/(tn+fp) if tn+fp else 0.0
    precision = tp/(tp+fp) if tp+fp else 0.0
    return {
        "rows": int(len(labels)), "tn": tn, "fp": fp, "fn": fn, "tp": tp,
        "fpr": fp/(fp+tn) if fp+tn else 0.0, "recall": recall,
        "precision": precision, "f1": 2*precision*recall/(precision+recall) if precision+recall else 0.0,
        "balanced_accuracy": (recall+specificity)/2,
    }


def run_segment(spec: dict, device, baseline: float) -> dict:
    out_root = ROOT / ("r1_cascade_physical" if spec["campaign"] == "R1" else "r2_variable_load")
    run_dir = out_root / spec["run_id"]
    run_dir.mkdir(parents=True, exist_ok=False)
    save_new(run_dir / "run_spec.json", spec)
    save_new(run_dir / "clock_check.json", clock_check())
    command = SSH + [f"cd {REMOTE} && {PYTHON} -B -u worker.py --stage {spec['stage']} --method {spec['method']} --block {spec['block']} --seconds {spec['seconds']}"]
    save_new(run_dir / "command.json", {"argv": command})
    remote_log = (run_dir / "pi_events.jsonl").open("x")
    stderr = (run_dir / "pi_stderr.log").open("x")
    process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr, text=True, bufsize=1)
    state = {"ready": None, "failed": None, "complete": None, "events": [], "outcomes": [], "idle": [], "backlog": None}
    done = threading.Event()

    def reader() -> None:
        try:
            for line in process.stdout:
                remote_log.write(line); remote_log.flush()
                item = json.loads(line); state["events"].append(item)
                kind = item.get("event")
                if kind == "ready": state["ready"] = item
                elif kind == "failed": state["failed"] = item
                elif kind == "complete": state["complete"] = item
                elif kind == "outcome": state["outcomes"].append(item)
                elif kind == "idle_sample": state["idle"].append(item)
                elif kind == "r2_final_backlog": state["backlog"] = item
        except BaseException as error:
            state["failed"] = {"reader_error": repr(error)}
        finally:
            done.set()

    thread = threading.Thread(target=reader, daemon=True); thread.start()
    heartbeat_stop = threading.Event(); samples = []; start_sent = False
    try:
        deadline = time.monotonic() + 1900
        while state["ready"] is None:
            if state["failed"] or done.is_set(): raise RuntimeError(f"remote preparation failed: {state['failed']}")
            if time.monotonic() > deadline: raise RuntimeError("remote ready timeout")
            time.sleep(0.2)
        device.write(request(250)); raw = bytes(device.read(64, 1000)); decode(raw, 250, baseline)
        start_utc = time.time() + 5
        start_mono = time.monotonic() + start_utc - time.time()
        save_new(run_dir / "start.json", {"start_utc_epoch": start_utc, "prestart_adc_hex": raw.hex(), "baseline_volts": baseline})
        process.stdin.write(json.dumps({"start_utc": start_utc}) + "\n"); process.stdin.flush(); start_sent = True

        def heartbeat() -> None:
            while not heartbeat_stop.is_set():
                try: process.stdin.write("heartbeat\n"); process.stdin.flush()
                except (BrokenPipeError, ValueError): return
                heartbeat_stop.wait(1)

        threading.Thread(target=heartbeat, daemon=True).start()
        append_event("segment_started", **spec, start_utc_epoch=start_utc)
        with (run_dir / "power.jsonl").open("x") as power_log:
            for index in range(spec["seconds"] + 1):
                target = start_mono + index
                if (delay := target - time.monotonic()) > 0: time.sleep(delay)
                if time.monotonic() - target > 0.25: raise RuntimeError("meter sampling deadline missed")
                if state["failed"]: raise RuntimeError(f"Pi failed: {state['failed']}")
                t0 = time.monotonic(); utc = time.time()
                device.write(request(index)); frame = bytes(device.read(64, 1000)); t1 = time.monotonic()
                if t1-t0 > 0.25: raise RuntimeError("meter roundtrip too slow")
                values = decode(frame, index, baseline)
                sample = {"index": index, "utc_epoch_request": utc, "request_monotonic": t0, "receive_monotonic": t1, "sample_monotonic": (t0+t1)/2, "roundtrip_seconds": t1-t0, "raw_hex": frame.hex(), **values}
                samples.append(sample); power_log.write(json.dumps(sample, allow_nan=False)+"\n"); power_log.flush()
                if index % 60 == 0: append_event("segment_progress", run_id=spec["run_id"], seconds=index, watts=values["watts"])
        code = process.wait(timeout=30); thread.join(timeout=10)
        if code != 0 or state["failed"] or not state["complete"]: raise RuntimeError(f"remote completion invalid: code={code}, failure={state['failed']}")
        expected_events = state["idle"] if spec["stage"] == "idle" else state["outcomes"]
        if len(expected_events) != spec["seconds"]: raise RuntimeError("wrong telemetry event count")
        energy, duration = integrate(samples)
        summary = {
            **spec, "status": "PASS", "power_samples": len(samples), "observed_duration_seconds": duration,
            "energy_joules": energy, "mean_watts": energy/duration,
            "voltage_min": min(x["volts"] for x in samples), "voltage_max": max(x["volts"] for x in samples),
            "measurement_scope": "uncalibrated KM003C USB load-side whole-Pi input; not AC-wall power",
        }
        if spec["stage"] != "idle":
            test_y = np.load(ROOT / "inputs" / "test_y.npy", allow_pickle=False)
            if spec["campaign"] == "R1":
                indices = np.concatenate([np.asarray(x["source_indices"], dtype=np.int64) for x in state["outcomes"]])
                probs = np.concatenate([np.asarray(x["final_probabilities"], dtype=np.float32) for x in state["outcomes"]])
                summary["posthoc"] = {"labels_loaded_only_after_run": True, "metrics": binary_metrics(test_y[indices], probs)}
                if spec["method"] == "ConfidenceCascade_0p3_0p7":
                    deferred = sum(sum(map(bool, x["deferred_mask"])) for x in state["outcomes"])
                    summary["posthoc"]["cascade_deferred_rows"] = deferred
                    summary["posthoc"]["cascade_escalation_fraction"] = deferred/len(indices)
            else:
                indices = np.concatenate([np.asarray(x["completed_source_indices"], dtype=np.int64) for x in state["outcomes"]])
                probs = np.concatenate([np.asarray(x["final_probabilities"], dtype=np.float32) for x in state["outcomes"]])
                backlog = np.asarray(state["backlog"]["source_indices"], dtype=np.int64)
                summary["posthoc"] = {
                    "labels_loaded_only_after_run": True, "completed_metrics": binary_metrics(test_y[indices], probs),
                    "scheduled_rows": int(len(indices)+len(backlog)), "completed_rows": int(len(indices)), "final_backlog_rows": int(len(backlog)),
                    "missed_positive_presentations": int(np.count_nonzero(test_y[backlog])) if len(backlog) else 0,
                    "deadline_miss_windows": int(sum(x["queue_after"] > 0 or x["deadline_overrun_seconds"] > 0 for x in state["outcomes"])),
                    "unique_encoded_states": sorted(set(int(x["encoded_state"]["index"]) for x in state["outcomes"])),
                }
        save_new(run_dir / "summary.json", summary)
        append_event("segment_complete", run_id=spec["run_id"], energy_joules=energy, mean_watts=energy/duration)
        return summary
    except BaseException as error:
        save_new(run_dir / "failure.json", {"status": "INVALID", "reason": repr(error), "stage": spec["stage"], "samples_retained": len(samples), "start_sent": start_sent, "automatic_retry": False})
        append_event("campaign_stopped", run_id=spec["run_id"], reason=repr(error))
        raise
    finally:
        heartbeat_stop.set()
        try: process.stdin.close()
        except Exception: pass
        try: process.wait(timeout=8)
        except subprocess.TimeoutExpired: process.terminate(); process.wait(timeout=5)
        thread.join(timeout=3); remote_log.close(); stderr.close()


def specs(campaign: str) -> list[dict]:
    rows = list(csv.DictReader((ROOT / "protocol" / "PREDECLARED_METHOD_ORDERS.csv").open()))
    output = []
    for row in rows:
        if row["campaign"] != campaign: continue
        block = int(row["block"])
        methods = [row[f"position{i}"] for i in range(1, 7) if row[f"position{i}"]]
        for position, method in enumerate(methods, 1):
            stem = f"{campaign.lower()}v2-b{block:02d}-p{position}-{method}"
            output.append({"campaign": campaign, "run_id": stem+"-idle", "stage": "idle", "method": method, "block": block, "position": position, "seconds": 60, "formal_statistics": False})
            formal = {"campaign": campaign, "run_id": stem, "stage": campaign.lower(), "method": method, "block": block, "position": position, "seconds": 500, "formal_statistics": True, "preceding_idle_run_id": stem+"-idle"}
            if campaign == "R1" and block == 1 and position == 1:
                formal["replacement_for"] = "r1-b01-p1-Static-MedRF"
                formal["replacement_reason"] = "pre-validation harness telemetry omission; no scientific outcome used"
            output.append(formal)
    return output


def validate_runtime() -> None:
    manifest = json.loads((ROOT / "runtime_manifest.json").read_text())
    for relative, expected in manifest["files"].items():
        if digest(ROOT / relative) != expected: raise RuntimeError(f"local runtime hash mismatch: {relative}")
    output = subprocess.check_output(SSH + [f"cd {REMOTE} && shasum -a 256 -c inputs_manifest.sha256"], text=True)
    if "FAILED" in output: raise RuntimeError("remote input manifest failed")


def main() -> None:
    parser = argparse.ArgumentParser(); parser.add_argument("--campaign", choices=["R1", "R2"], required=True); args = parser.parse_args()
    lock = (ROOT / "controller.lock").open("a"); fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    validate_runtime()
    device = hid.device(); device.open(0x5FC9, 0x0063, "075356")
    try:
        device.write(request(249)); raw = bytes(device.read(64, 1000)); baseline = decode(raw, 249)["volts"]
        meter_file = ROOT / "meter_start.json"
        if not meter_file.exists(): save_new(meter_file, {"baseline_volts": baseline, "raw_hex": raw.hex(), "meter_serial": "075356"})
        summaries = []
        for spec in specs(args.campaign):
            summaries.append(run_segment(spec, device, baseline))
            if spec["stage"] != "idle":
                idle = summaries[-2]
                summaries[-1]["preceding_idle_mean_watts"] = idle["mean_watts"]
                summaries[-1]["idle_adjusted_mean_watts"] = summaries[-1]["mean_watts"] - idle["mean_watts"]
                path = ROOT / ("r1_cascade_physical" if args.campaign == "R1" else "r2_variable_load") / spec["run_id"] / "paired_summary.json"
                save_new(path, summaries[-1])
        save_new(ROOT / ("r1_cascade_physical" if args.campaign == "R1" else "r2_variable_load") / "campaign_summary.json", {"status": "PASS", "campaign": args.campaign, "segments": len(summaries), "formal_runs": len(summaries)//2})
        append_event("campaign_complete", campaign=args.campaign, segments=len(summaries), formal_runs=len(summaries)//2)
    finally:
        device.close()


if __name__ == "__main__":
    main()
