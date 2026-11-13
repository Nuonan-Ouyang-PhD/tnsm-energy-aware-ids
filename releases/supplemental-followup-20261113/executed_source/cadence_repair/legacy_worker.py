"""Fail-closed Raspberry Pi worker for reviewer-requested R1/R2/R3 runs."""
from __future__ import annotations

import os
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"

import argparse
from collections import deque
import hashlib
import json
import math
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


def load_models() -> dict:
    models = {name: joblib.load(ROOT / "inputs" / f"{name}.joblib") for name in ("TinyDT", "LightLR", "MedRF")}
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


def predict(models: dict, action: Action, batch: np.ndarray) -> np.ndarray:
    if action is not Action.HEAVY_MLP:
        return models[action.value].predict_proba(batch)[:, 1].astype(np.float32)
    with torch.no_grad():
        return torch.sigmoid(models["HeavyMLP"](torch.from_numpy(batch))).numpy().ravel().astype(np.float32)


def cascade(models: dict, batch: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    light = predict(models, Action.LIGHT_LR, batch)
    deferred = (light >= 0.3) & (light <= 0.7)
    final = light.copy()
    med = np.full(len(light), np.nan, dtype=np.float32)
    if np.any(deferred):
        scores = predict(models, Action.MED_RF, batch[deferred])
        final[deferred] = scores
        med[deferred] = scores
    return final, light, med, deferred


def preflight() -> tuple[dict, dict, object, object]:
    if "Raspberry Pi 4 Model B" not in Path("/proc/device-tree/model").read_text():
        raise RuntimeError("unexpected hardware")
    hostname = socket.gethostname()
    memory_kb = int(next(line.split()[1] for line in Path("/proc/meminfo").read_text().splitlines() if line.startswith("MemTotal:")))
    cpu_serial = next(line.split(":", 1)[1].strip() for line in Path("/proc/cpuinfo").read_text().splitlines() if line.startswith("Serial"))
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
    return {"hostname": hostname, "memory_kb": memory_kb, "cpu_serial": cpu_serial}, manifest, config, telemetry()


def warm_models(models: dict) -> None:
    warm = np.load(ROOT / "inputs" / "warm_X.npy", mmap_mode="r")[:100]
    batch = np.array(warm, copy=True)
    for action in ACTION_ORDER:
        for _ in range(20):
            predict(models, action, batch)


def wait_cool() -> dict:
    deadline = time.monotonic() + 1800
    while True:
        value = telemetry()
        if value["temperature_c"] <= 45:
            return value
        if time.monotonic() > deadline:
            raise RuntimeError("cooldown timeout")
        emit("cooldown", **value)
        time.sleep(5)


def start_barrier(stage: str, method: str, seconds: int, identity: dict, initial: dict) -> float:
    governors = {p.read_text().strip() for p in Path("/sys/devices/system/cpu").glob("cpu[0-9]/cpufreq/scaling_governor")}
    if len(governors) != 1:
        raise RuntimeError("mixed CPU governors")
    emit("ready", stage=stage, method=method, seconds=seconds, governors=sorted(governors), **identity, **initial)
    command = json.loads(sys.stdin.readline())
    start_utc = float(command["start_utc"])
    if not 1 < start_utc - time.time() < 30:
        raise RuntimeError("invalid scheduled start")
    global last_heartbeat
    last_heartbeat = time.monotonic()
    threading.Thread(target=watch_control, daemon=True).start()
    return time.monotonic() + start_utc - time.time()


def choose_policy(method: str, config):
    if method == "CFSM":
        return CFSMScheduler(config.data)
    if method == "Tabular-Q":
        return load_policy(ROOT / "policies" / "tabular-frozen", config=config, require_frozen=True)[0]
    if method == "DQN":
        return load_policy(ROOT / "policies" / "dqn-frozen", config=config, require_frozen=True)[0]
    return None


def select(method: str, state, encoded, policy, arrivals: int, l95_medrf_s: float) -> tuple[Action | None, dict]:
    if method == "Static-LightLR":
        return Action.LIGHT_LR, {"mode": "static"}
    if method == "Static-MedRF":
        return Action.MED_RF, {"mode": "static"}
    if method == "ConfidenceCascade_0p3_0p7":
        return None, {"mode": "fixed_confidence_cascade", "inclusive_band": [0.3, 0.7]}
    if method == "DeadlineGuard":
        demand = math.ceil(arrivals / 100) * l95_medrf_s
        action = Action.MED_RF if demand <= 1.0 else Action.LIGHT_LR
        return action, {"mode": "deadline_guard", "arrivals": arrivals, "predicted_medrf_seconds": demand, "deadline_seconds": 1.0}
    if method == "CFSM":
        decision = policy.select_action(state)
        return decision.selected_action, decision.as_dict()
    action = policy.select_action(encoded, training=False)
    return action, {"mode": "frozen_greedy", "evaluation_updates": False}


def do_idle(seconds: int, start_mono: float) -> None:
    for index in range(seconds):
        watch_guard()
        target = start_mono + index
        if (delay := target - time.monotonic()) > 0:
            time.sleep(delay)
        value = telemetry()
        emit("idle_sample", window_index=index, detector_inference_executed=False, **value)


def do_r1(method: str, seconds: int, block: int, models: dict, config, manifest: dict, start_mono: float) -> None:
    trace = f"formal_test_{[11,23,37,53,71,89,107,131,157,191][block - 1]}"
    info = manifest["traces"][trace]
    x = np.load(ROOT / info["x_file"], mmap_mode="r")
    indices = np.load(ROOT / info["indices_file"], allow_pickle=False)
    if indices.shape != (50000,):
        raise RuntimeError("R1 trace shape mismatch")
    policy = choose_policy(method, config)
    tracker, encoder = OnlineStateTracker(config.data), StateEncoder(config.data)
    previous_finish = start_mono
    for window in range(seconds):
        watch_guard()
        target = start_mono + window
        if (delay := target - time.monotonic()) > 0:
            time.sleep(delay)
        lateness = time.monotonic() - target
        if lateness > 0.25:
            raise RuntimeError("R1 workload deadline missed")
        before = telemetry()
        queue_depth = max(0, round((previous_finish - target) * 100))
        state = tracker.begin_window(PreDecisionObservation(window, before["temperature_c"], queue_depth, 100))
        encoded = encoder.encode(state)
        decision_begin_ns = time.perf_counter_ns()
        action, detail = select(method, state, encoded, policy, 100, 0.0)
        scheduler_selection_ns = time.perf_counter_ns() - decision_begin_ns
        source = indices[window * 100:(window + 1) * 100]
        batch = np.array(x[source], copy=True)
        begin_ns = time.perf_counter_ns()
        if action is None:
            probs, light, med, deferred = cascade(models, batch)
        else:
            probs = predict(models, action, batch)
            light = med = deferred = None
        elapsed_ns = time.perf_counter_ns() - begin_ns
        previous_finish = time.monotonic()
        if elapsed_ns >= 250_000_000:
            raise RuntimeError("R1 inference batch over budget")
        tracker.complete_window(window_index=window, selected_action=action or Action.LIGHT_LR, selected_attack_probabilities=probs, arrivals_in_window=100)
        after = telemetry()
        payload = {
            "window_index": window, "method": method, "encoded_state": encoded.as_log_dict(),
            "state": state.as_log_dict(), "selected_action": action.value if action else "ConfidenceCascade_0p3_0p7",
            "decision_detail": detail, "source_indices": source.tolist(), "final_probabilities": probs.tolist(),
            "scheduler_selection_ns": scheduler_selection_ns, "inference_ns": elapsed_ns,
            "end_to_end_window_completion_seconds": previous_finish - target,
            "lateness_seconds": lateness, "queue_depth_samples": queue_depth,
            "labels_available": False, "pre_temperature_c": before["temperature_c"],
            "post_temperature_c": after["temperature_c"], "throttled": after["throttled"],
            "load_1m": after["load_1m"], "frequencies_khz": after["frequencies_khz"],
        }
        if deferred is not None:
            payload.update({
                "lightlr_probabilities": light.tolist(), "deferred_mask": deferred.tolist(),
                "deferred_source_indices": source[deferred].tolist(),
                "deferred_medrf_probabilities": med[deferred].tolist(),
            })
        emit("outcome", **payload)


def do_r2(method: str, seconds: int, block: int, models: dict, config, manifest: dict, start_mono: float) -> None:
    info = manifest["r2_blocks"][str(block)]
    x = np.load(ROOT / "inputs" / "test_X.npy", mmap_mode="r")
    indices = np.load(ROOT / info["indices_file"], allow_pickle=False)
    arrivals = np.load(ROOT / info["arrivals_file"], allow_pickle=False)
    offsets = np.load(ROOT / info["offsets_file"], allow_pickle=False)
    if arrivals.shape != (500,) or offsets.shape != (501,) or int(offsets[-1]) != len(indices):
        raise RuntimeError("R2 workload shape mismatch")
    policy = choose_policy(method, config)
    tracker, encoder = OnlineStateTracker(config.data), StateEncoder(config.data)
    queue: deque[tuple[int, int]] = deque()
    l95 = float(manifest["deadline_guard"]["medrf_p95_seconds_per_100_rows"])
    for window in range(seconds):
        watch_guard()
        target = start_mono + window
        if (delay := target - time.monotonic()) > 0:
            time.sleep(delay)
        window_end = start_mono + window + 1
        begin, end = int(offsets[window]), int(offsets[window + 1])
        for index in indices[begin:end]:
            queue.append((int(index), window))
        before = telemetry()
        queue_before = len(queue)
        state = tracker.begin_window(PreDecisionObservation(window, before["temperature_c"], queue_before, 100))
        encoded = encoder.encode(state)
        decision_begin_ns = time.perf_counter_ns()
        action, detail = select(method, state, encoded, policy, int(arrivals[window]), l95)
        scheduler_selection_ns = time.perf_counter_ns() - decision_begin_ns
        completed_indices: list[int] = []
        completed_arrival_windows: list[int] = []
        probabilities: list[float] = []
        light_scores: list[float] = []
        deferred_flags: list[bool] = []
        deferred_med_scores: list[float] = []
        batch_times: list[int] = []
        while queue and time.monotonic() < window_end:
            count = min(100, len(queue))
            pairs = [queue.popleft() for _ in range(count)]
            source = np.asarray([p[0] for p in pairs], dtype=np.int64)
            batch = np.array(x[source], copy=True)
            t0 = time.perf_counter_ns()
            if action is None:
                probs, light, med, deferred = cascade(models, batch)
                light_scores.extend(map(float, light))
                deferred_flags.extend(map(bool, deferred))
                deferred_med_scores.extend(map(float, med[deferred]))
            else:
                probs = predict(models, action, batch)
            batch_times.append(time.perf_counter_ns() - t0)
            completed_indices.extend(map(int, source))
            completed_arrival_windows.extend(p[1] for p in pairs)
            probabilities.extend(map(float, probs))
        finish = time.monotonic()
        if not probabilities:
            raise RuntimeError("R2 no service completion in window")
        tracker.complete_window(
            window_index=window, selected_action=action or Action.LIGHT_LR,
            selected_attack_probabilities=probabilities, arrivals_in_window=int(arrivals[window]),
        )
        after = telemetry()
        emit(
            "outcome", window_index=window, method=method, state=state.as_log_dict(), encoded_state=encoded.as_log_dict(),
            selected_action=action.value if action else "ConfidenceCascade_0p3_0p7", decision_detail=detail,
            switched=(action or Action.LIGHT_LR) is not state.previous_action,
            scheduler_selection_ns=scheduler_selection_ns,
            arrivals=int(arrivals[window]), queue_before=queue_before, rows_completed=len(completed_indices), queue_after=len(queue),
            completed_source_indices=completed_indices, completed_arrival_windows=completed_arrival_windows,
            final_probabilities=probabilities, lightlr_probabilities=light_scores,
            deferred_mask=deferred_flags, deferred_medrf_probabilities=deferred_med_scores,
            batch_inference_ns=batch_times, end_to_end_window_completion_seconds=finish-target,
            deadline_missed=finish > window_end or bool(queue), deadline_overrun_seconds=max(0.0, finish - window_end),
            detector_inference_executed=True,
            labels_available=False, pre_temperature_c=before["temperature_c"], post_temperature_c=after["temperature_c"],
            throttled=after["throttled"], load_1m=after["load_1m"], frequencies_khz=after["frequencies_khz"],
        )
    emit("r2_final_backlog", rows=len(queue), source_indices=[x[0] for x in queue], arrival_windows=[x[1] for x in queue])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=["idle", "r1", "r2"], required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--block", type=int, required=True)
    parser.add_argument("--seconds", type=int, required=True)
    args = parser.parse_args()
    expected = 60 if args.stage == "idle" else 500
    if args.seconds != expected:
        raise ValueError("unexpected segment duration")
    try:
        identity, manifest, config, initial = preflight()
        models = load_models()
        warm_models(models)
        initial = wait_cool()
        start_mono = start_barrier(args.stage, args.method, args.seconds, identity, initial)
        if args.stage == "idle":
            do_idle(args.seconds, start_mono)
        elif args.stage == "r1":
            do_r1(args.method, args.seconds, args.block, models, config, manifest, start_mono)
        else:
            do_r2(args.method, args.seconds, args.block, models, config, manifest, start_mono)
        delay = start_mono + args.seconds - time.monotonic()
        if delay > 0:
            time.sleep(delay)
        emit("complete", stage=args.stage, method=args.method, seconds=args.seconds)
    except BaseException as error:
        emit("failed", error=repr(error))
        raise


if __name__ == "__main__":
    main()
