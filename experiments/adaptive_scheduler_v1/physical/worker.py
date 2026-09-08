"""Fail-closed Pi worker for pilot and frozen paired scheduling runs."""
from __future__ import annotations

import os
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import threading
import time

import joblib
import numpy as np
import torch

from scheduler.artifacts import load_policy
from scheduler.cfsm import CFSMScheduler
from scheduler.config import load_config
from scheduler.state import ACTION_ORDER, Action, OnlineStateTracker, PreDecisionObservation, StateEncoder


ROOT = Path(__file__).resolve().parent
EXPECTED_HOSTNAME = "pi4b8g"
EXPECTED_CPU_SERIAL = "100000005368e39d"
MIN_MEMORY_KB = 7_500_000
last_heartbeat = time.monotonic()
control_closed = threading.Event()


def emit(event: str, **fields) -> None:
    print(json.dumps({"event": event, "utc_epoch": time.time(), **fields}, allow_nan=False), flush=True)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def watch_control() -> None:
    global last_heartbeat
    for line in sys.stdin:
        if line.strip() == "heartbeat":
            last_heartbeat = time.monotonic()
        else:
            break
    control_closed.set()


def watch_guard() -> None:
    if control_closed.is_set() or time.monotonic() - last_heartbeat > 30:
        raise RuntimeError("coordinator heartbeat lost")


def telemetry() -> dict:
    temperature = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text()) / 1000
    throttled = subprocess.check_output(["vcgencmd", "get_throttled"], text=True).strip()
    if temperature >= 70 or throttled != "throttled=0x0":
        raise RuntimeError(f"thermal/throttle guard: {temperature}, {throttled}")
    return {
        "temperature_c": temperature,
        "throttled": throttled,
        "load_1m": os.getloadavg()[0],
        "frequencies_khz": [
            int(path.read_text())
            for path in sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]/cpufreq/scaling_cur_freq"))
        ],
    }


def load_models():
    models = {
        name: joblib.load(ROOT / "inputs" / f"{name}.joblib")
        for name in ("TinyDT", "LightLR", "MedRF")
    }
    saved = torch.load(ROOT / "inputs" / "HeavyMLP.pt", map_location="cpu", weights_only=True)
    net = torch.nn.Sequential(
        torch.nn.Linear(saved["input_dim"], 64), torch.nn.ReLU(), torch.nn.Dropout(0.2),
        torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Dropout(0.2),
        torch.nn.Linear(32, 16), torch.nn.ReLU(), torch.nn.Dropout(0.2),
        torch.nn.Linear(16, 1),
    )
    net.load_state_dict(saved["state_dict"])
    net.eval()
    models["HeavyMLP"] = net
    return models


def predict(models, action: Action, batch: np.ndarray) -> np.ndarray:
    if action is not Action.HEAVY_MLP:
        return models[action.value].predict_proba(batch)[:, 1].astype(np.float32)
    with torch.no_grad():
        return torch.sigmoid(models["HeavyMLP"](torch.from_numpy(batch))).numpy().ravel().astype(np.float32)


def main() -> None:
    global last_heartbeat
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", choices=["Pilot-RoundRobin", "Static-MedRF", "CFSM", "Tabular-Q", "DQN"], required=True)
    parser.add_argument("--trace", required=True)
    parser.add_argument("--seconds", type=int, required=True)
    args = parser.parse_args()
    if args.method == "Pilot-RoundRobin" and not 60 <= args.seconds <= 180:
        raise ValueError("pilot duration outside 60..180 seconds")
    if args.method != "Pilot-RoundRobin" and args.seconds != 500:
        raise ValueError("formal method duration must be 500 seconds")
    if "Raspberry Pi 4 Model B" not in Path("/proc/device-tree/model").read_text():
        raise RuntimeError("unexpected hardware")
    hostname = socket.gethostname()
    memory_kb = int(next(
        line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines()
        if line.startswith("MemTotal:")
    ))
    cpu_serial = next(
        line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines()
        if line.startswith("Serial")
    )
    if hostname != EXPECTED_HOSTNAME or memory_kb < MIN_MEMORY_KB or cpu_serial != EXPECTED_CPU_SERIAL:
        raise RuntimeError("unexpected Pi identity")
    if shutil.disk_usage(ROOT).free < 1 << 30:
        raise RuntimeError("insufficient Pi disk")
    if subprocess.check_output(["timedatectl", "show", "-p", "NTPSynchronized", "--value"], text=True).strip() != "yes":
        raise RuntimeError("Pi clock is not synchronized")
    manifest = json.loads((ROOT / "inputs_manifest.json").read_text())
    for relative, expected in manifest["files"].items():
        if digest(ROOT / relative) != expected:
            raise RuntimeError(f"input hash mismatch: {relative}")
    config = load_config(ROOT / "config" / "scheduler_experiment_v1.json")
    if config.sha256 != manifest["config_sha256"]:
        raise RuntimeError("config binding mismatch")
    trace_info = manifest["traces"].get(args.trace)
    if trace_info is None:
        raise RuntimeError("trace is not registered")
    x = np.load(ROOT / trace_info["x_file"], mmap_mode="r")
    indices = np.load(ROOT / trace_info["indices_file"], allow_pickle=False)
    needed = args.seconds * 100
    if indices.shape != (50000,) or needed > len(indices):
        raise RuntimeError("trace index shape mismatch")
    if np.any(indices < 0) or np.any(indices >= len(x)):
        raise RuntimeError("trace index out of bounds")
    models = load_models()
    # Warm every resident model on training-only calibration rows.
    warm = np.load(ROOT / "inputs" / "warm_X.npy", mmap_mode="r")[:100]
    for action in ACTION_ORDER:
        for _ in range(20):
            predict(models, action, np.array(warm, copy=True))
    if args.method == "CFSM":
        policy = CFSMScheduler(config.data)
    elif args.method == "Tabular-Q":
        policy, _ = load_policy(ROOT / "policies" / "tabular-frozen", config=config, require_frozen=True)
    elif args.method == "DQN":
        policy, _ = load_policy(ROOT / "policies" / "dqn-frozen", config=config, require_frozen=True)
    else:
        policy = None
    tracker = OnlineStateTracker(config.data)
    encoder = StateEncoder(config.data)
    deadline = time.monotonic() + 1800
    while True:
        pre = telemetry()
        if pre["temperature_c"] <= 45:
            break
        if time.monotonic() > deadline:
            raise RuntimeError("cooldown timeout")
        emit("cooldown", **pre)
        time.sleep(5)
    governors = {p.read_text().strip() for p in Path("/sys/devices/system/cpu").glob("cpu[0-9]/cpufreq/scaling_governor")}
    if len(governors) != 1:
        raise RuntimeError("mixed CPU governors")
    emit(
        "ready", method=args.method, trace=args.trace, seconds=args.seconds,
        hostname=hostname, memory_kb=memory_kb, cpu_serial=cpu_serial,
        governors=sorted(governors), **pre,
    )
    command = json.loads(sys.stdin.readline())
    start_utc = float(command["start_utc"])
    if not 1 < start_utc - time.time() < 30:
        raise RuntimeError("invalid scheduled start")
    start_mono = time.monotonic() + start_utc - time.time()
    last_heartbeat = time.monotonic()
    threading.Thread(target=watch_control, daemon=True).start()
    previous_finish = start_mono
    for window_index in range(args.seconds):
        watch_guard()
        target = start_mono + window_index
        delay = target - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        watch_guard()
        lateness = time.monotonic() - target
        if lateness > 0.25:
            raise RuntimeError("Pi workload deadline missed")
        before = telemetry()
        queue_depth = max(0, round((previous_finish - target) * 100))
        state = tracker.begin_window(PreDecisionObservation(
            window_index=window_index,
            raw_temperature_c=before["temperature_c"],
            queue_depth_samples=queue_depth,
            queue_capacity_samples=100,
        ))
        encoded = encoder.encode(state)
        if args.method == "Static-MedRF":
            action = Action.MED_RF
            detail = {"mode": "static"}
        elif args.method == "Pilot-RoundRobin":
            # Hold each resident model for five windows so the excluded pilot
            # contains both first-batch-after-switch and steady hold batches.
            action = ACTION_ORDER[(window_index // 5) % 4]
            detail = {
                "mode": "pilot_blocked_round_robin",
                "hold_windows": 5,
                "excluded_from_formal_statistics": True,
            }
        elif args.method == "CFSM":
            decision = policy.select_action(state)
            action = decision.selected_action
            detail = decision.as_dict()
        else:
            action = policy.select_action(encoded, training=False)
            detail = {"mode": "frozen_greedy", "evaluation_updates": False}
        emit(
            "decision", window_index=window_index, method=args.method,
            state=state.as_log_dict(), encoded_state=encoded.as_log_dict(),
            selected_action=action.value, switched=action is not state.previous_action,
            decision_detail=detail, labels_available=False,
            current_counterfactual_predictions_available=False,
        )
        source = indices[window_index * 100:(window_index + 1) * 100]
        batch = np.array(x[source], copy=True)
        begin_ns = time.perf_counter_ns()
        probabilities = predict(models, action, batch)
        end_ns = time.perf_counter_ns()
        previous_finish = time.monotonic()
        elapsed_ns = end_ns - begin_ns
        if elapsed_ns >= 250_000_000:
            raise RuntimeError("inference batch over budget")
        after = telemetry()
        tracker.complete_window(
            window_index=window_index,
            selected_action=action,
            selected_attack_probabilities=probabilities,
            arrivals_in_window=100,
        )
        emit(
            "outcome", window_index=window_index, method=args.method,
            selected_action=action.value, source_offset=window_index * 100,
            rows=100, probabilities=probabilities.tolist(), inference_ns=elapsed_ns,
            lateness_seconds=lateness, queue_depth_samples=queue_depth,
            pre_temperature_c=before["temperature_c"], post_temperature_c=after["temperature_c"],
            throttled=after["throttled"], load_1m=after["load_1m"], frequencies_khz=after["frequencies_khz"],
        )
    final_delay = start_mono + args.seconds - time.monotonic()
    if final_delay > 0:
        time.sleep(final_delay)
    watch_guard()
    emit("complete", method=args.method, trace=args.trace, windows=args.seconds, **telemetry())


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        emit("failed", reason=repr(error))
        raise
