"""Bounded same-runtime latency calibration; no training or test inputs.

All classifiers remain resident. This records timing, not measured energy.
Continuous interval CPU snapshots cover model loading, warmup and measurements.
"""
import os
os.environ["OMP_NUM_THREADS"] = "2"
os.environ["OPENBLAS_NUM_THREADS"] = "2"

import hashlib
import json
from pathlib import Path
import socket
import subprocess
import threading
import time

import joblib
import numpy as np
import torch

from core import ACTIONS
from cpu_guard import snapshot, interval

HERE = Path(__file__).resolve().parent
INPUTS = Path("/home/pi/tnsm-reviewer-revision-v1/inputs")
stop = threading.Event()
failed = []
output_lock = threading.Lock()
deadline = time.monotonic() + 180


def emit(event, **fields):
    with output_lock:
        print(json.dumps({"event": event, "utc_epoch": time.time(), **fields}, allow_nan=False), flush=True)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check():
    if failed:
        raise RuntimeError(failed[0])
    if time.monotonic() > deadline:
        raise RuntimeError("bounded calibration time exceeded")


def monitor():
    try:
        left = snapshot()
        while not stop.wait(1):
            right = snapshot()
            result = interval(left, right, {os.getpid()})
            temperature = int(Path("/sys/class/thermal/thermal_zone0/temp").read_text())/1000
            throttle = subprocess.check_output(["vcgencmd", "get_throttled"], text=True).strip()
            emit("cpu_interval", **result, left=left, right=right,
                 temperature_c=temperature, throttled=throttle)
            if not result["pass"] or temperature >= 70 or throttle != "throttled=0x0":
                raise RuntimeError("external load or thermal/throttle guard failed")
            left = right
        # Cover the final partial interval instead of silently discarding it.
        right = snapshot()
        if right["total"] > left["total"]:
            result = interval(left, right, {os.getpid()})
            emit("cpu_interval_final", **result, left=left, right=right)
            if not result["pass"]:
                raise RuntimeError("final external-load interval failed")
    except BaseException as error:
        failed.append(repr(error))
        emit("monitor_failed", error=repr(error))


def main():
    bindings = json.loads((HERE / "bindings.json").read_text())
    for name, expected in bindings["source_sha256"].items():
        if digest(HERE / name) != expected:
            raise RuntimeError("execution source drift: " + name)
    serial = next(x.split(":", 1)[1].strip() for x in Path("/proc/cpuinfo").read_text().splitlines() if x.startswith("Serial"))
    ntp = subprocess.check_output(["timedatectl", "show", "-p", "NTPSynchronized", "--value"], text=True).strip()
    if serial != "100000005368e39d" or socket.gethostname() != "pi4b8g" or ntp != "yes":
        raise RuntimeError("identity or NTP gate failed")
    torch.set_num_threads(2)
    emit("ready", cpu_serial=serial, hostname=socket.gethostname(), ntp_synchronized=ntp,
         boot_id=Path("/proc/sys/kernel/random/boot_id").read_text().strip(),
         source_sha256=bindings["source_sha256"], pid=os.getpid(),
         torch_version=torch.__version__, numpy_version=np.__version__,
         torch_threads=torch.get_num_threads(), scope="NEW_LATENCY_CALIBRATION_NOT_PHYSICAL_ENERGY")
    thread = threading.Thread(target=monitor, daemon=True)
    thread.start()
    try:
        for name, expected in bindings["input_sha256"].items():
            check()
            if digest(INPUTS / name) != expected:
                raise RuntimeError("calibration input drift: " + name)
        models = {m: joblib.load(INPUTS / (m + ".joblib")) for m in ACTIONS[:3]}
        saved = torch.load(INPUTS / "HeavyMLP.pt", map_location="cpu", weights_only=True)
        net = torch.nn.Sequential(torch.nn.Linear(saved["input_dim"], 64), torch.nn.ReLU(), torch.nn.Dropout(.2),
              torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Dropout(.2),
              torch.nn.Linear(32, 16), torch.nn.ReLU(), torch.nn.Dropout(.2), torch.nn.Linear(16, 1))
        net.load_state_dict(saved["state_dict"])
        net.eval()
        models["HeavyMLP"] = net
        warm = np.load(INPUTS / "warm_X.npy", allow_pickle=False)
        if warm.shape[0] < 100 or warm.dtype != np.float32:
            raise RuntimeError("unexpected warm-input shape/type")
        batch = np.array(warm[:100], copy=True)

        def predict(name, x):
            check()
            if name != "HeavyMLP":
                return models[name].predict_proba(x)[:, 1].astype(np.float32)
            with torch.no_grad():
                return torch.sigmoid(net(torch.from_numpy(x))).numpy().ravel().astype(np.float32)

        for name in ACTIONS:
            for _ in range(20):
                predict(name, batch)
        emit("warmup_complete", repeats_per_model=20, all_models_resident=True)
        summary = {}
        for name in ACTIONS:
            timings = []
            for i in range(200):
                start = time.perf_counter_ns()
                p = predict(name, batch)
                elapsed = time.perf_counter_ns() - start
                if p.shape != (100,) or not np.isfinite(p).all():
                    raise RuntimeError("invalid classifier output")
                timings.append(elapsed / 1e9)
                emit("batch_latency", model=name, repeat=i, rows=100, elapsed_ns=elapsed)
            summary[name] = {"batch_rows": 100, "repeats": 200,
                "mean_seconds": float(np.mean(timings)),
                "p95_seconds": float(np.quantile(timings, .95)),
                "p99_seconds": float(np.quantile(timings, .99))}
            for rows in (50, 100, 4000):
                for repeat in range(3):
                    check()
                    started = time.perf_counter_ns()
                    for first in range(0, rows, 100):
                        predict(name, batch[:min(100, rows-first)])
                    emit("service_probe", model=name, rows=rows, repeat=repeat,
                         elapsed_ns=time.perf_counter_ns()-started)
        stop.set()
        thread.join(timeout=5)
        if thread.is_alive():
            raise RuntimeError("CPU monitor did not finish")
        check()
        emit("complete", status="PASS", latency_registry=summary,
             inference_scope="resident classifiers, warm 100-row input; zero queue/transport/controller cost in batch timing",
             measured_energy_joules=None, test_inputs_opened=False,
             formal_paired_runs=0)
    finally:
        stop.set()
        thread.join(timeout=5)


if __name__ == "__main__":
    try:
        main()
    except BaseException as error:
        emit("failed", status="INVALID_RETAIN_NO_RETRY", error=repr(error))
        raise
