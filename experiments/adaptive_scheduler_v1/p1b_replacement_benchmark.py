"""Corrected P1B replacement: isolated production selector timing on the Pi."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import platform
import resource
import time

import numpy as np

from scheduler.artifacts import load_policy
from scheduler.cfsm import CFSMScheduler
from scheduler.config import load_config
from scheduler.state import ACTION_ORDER, Action, EncodedState, OnlineState, StateEncoder


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "p1b_replacement_output"
CAMPAIGN_ID = "TNSM-P1B-OVERHEAD-CORRECTED-20260908-R1"
ORDER_SEED = 20260908
N_BLOCKS = 30
N_WARMUP = 1000
N_TIMED = 10000
METHODS = ("Static-LightLR", "CFSM", "Tabular-Q", "DQN")


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def file_text(path: Path, default="unavailable"):
    try:
        return path.read_text().strip()
    except OSError:
        return default


def command_text(command, default="unavailable"):
    import subprocess

    try:
        return subprocess.check_output(command, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return default


def telemetry():
    page = os.sysconf("SC_PAGE_SIZE")
    statm = file_text(Path("/proc/self/statm"), "0 0").split()
    rss = int(statm[1]) * page if len(statm) > 1 else None
    frequencies = []
    max_frequencies = []
    governors = []
    for cpu in sorted(Path("/sys/devices/system/cpu").glob("cpu[0-9]*")):
        frequencies.append(file_text(cpu / "cpufreq/scaling_cur_freq"))
        max_frequencies.append(file_text(cpu / "cpufreq/scaling_max_freq"))
        governors.append(file_text(cpu / "cpufreq/scaling_governor"))
    temp_raw = file_text(Path("/sys/class/thermal/thermal_zone0/temp"))
    try:
        temperature = int(temp_raw) / 1000.0
    except ValueError:
        temperature = None
    return {
        "utc_epoch": time.time(),
        "rss_bytes": rss,
        "peak_rss_bytes": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
        "temperature_c": temperature,
        "throttle": command_text(["vcgencmd", "get_throttled"]),
        "cpu_freq_current_hz": [int(x) * 1000 for x in frequencies if x.isdigit()],
        "cpu_freq_max_hz": [int(x) * 1000 for x in max_frequencies if x.isdigit()],
        "governors": sorted(set(governors)),
    }


def online_state(data):
    return OnlineState(
        window_index=int(data["window_index"]),
        raw_temperature_c=float(data["raw_temperature_c"]),
        smoothed_temperature_c=float(data["smoothed_temperature_c"]),
        lagged_selected_model_threat=float(data["lagged_selected_model_threat"]),
        predecision_queue_utilization=float(data["predecision_queue_utilization"]),
        lagged_arrival_rate_ratio=float(data["lagged_arrival_rate_ratio"]),
        previous_action=Action(data["previous_action"]),
        temperature_source_window=int(data["temperature_source_window"]),
        threat_source_window=data["threat_source_window"],
        queue_source_window=int(data["queue_source_window"]),
        load_source_window=data["load_source_window"],
        previous_action_source_window=data["previous_action_source_window"],
    )


def load_observed():
    records = json.loads((ROOT / "p1b_observed_states.json").read_text())
    return [
        {
            **record,
            "state": online_state(record["state"]),
            "encoded": EncodedState(**record["encoded"]),
        }
        for record in records
    ]


def exhaustive(config):
    encoder = StateEncoder(config)
    values = (
        (35.0, 50.0, 75.0),
        (0.1, 0.5, 0.9),
        (0.1, 0.5, 0.9),
        (0.5, 1.0, 1.5),
        ACTION_ORDER,
    )
    output = []
    for temperature in values[0]:
        for threat in values[1]:
            for queue in values[2]:
                for load in values[3]:
                    for previous in values[4]:
                        state = OnlineState(
                            0, temperature, temperature, threat, queue, load, previous,
                            0, None, 0, None, None,
                        )
                        output.append(
                            {"state": state, "encoded": encoder.encode(state), "cooldown_before": 0}
                        )
    assert [item["encoded"].index for item in output] == list(range(324))
    return output


def semantic_validation(config, observed):
    policy = CFSMScheduler(config)
    failures = []
    for index, record in enumerate(observed):
        policy.current_action = record["state"].previous_action
        policy.cooldown_remaining = int(record["cooldown_before"])
        got = policy.select_action(record["state"])
        if (
            got.selected_action.value != record["expected_action"]
            or got.reason != record["expected_reason"]
            or got.cooldown_after != int(record["expected_cooldown_after"])
        ):
            failures.append(index)
    return {"states": len(observed), "mismatches": failures, "status": "PASS" if not failures else "FAIL"}


def main():
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    OUT.mkdir()
    (OUT / "raw").mkdir()
    config = load_config(ROOT / "config" / "scheduler_experiment_v1.json")
    tabular, tabular_meta = load_policy(ROOT / "policies/tabular-frozen", config=config, require_frozen=True)
    dqn, dqn_meta = load_policy(ROOT / "policies/dqn-frozen", config=config, require_frozen=True)
    observed = load_observed()
    streams = {"exhaustive_324": exhaustive(config.data), "observed_support": observed}
    validation = semantic_validation(config.data, observed)
    if validation["status"] != "PASS":
        raise RuntimeError("CFSM semantic replay failed")
    (OUT / "cfsm_semantic_validation.json").write_text(json.dumps(validation, indent=2) + "\n")
    rng = np.random.default_rng(ORDER_SEED)
    orders = []
    rows = []
    static = lambda _state: Action.LIGHT_LR
    cfsm = CFSMScheduler(config.data)
    selectors = {
        "Static-LightLR": lambda record: static(record["encoded"]),
        "CFSM": lambda record: cfsm.select_action(record["state"]).selected_action,
        "Tabular-Q": lambda record: tabular.select_action(record["encoded"], training=False),
        "DQN": lambda record: dqn.select_action(record["encoded"], training=False),
    }
    for block in range(1, N_BLOCKS + 1):
        order = list(METHODS)
        rng.shuffle(order)
        orders.append({"block": block, "method_order": order})
        for stream_name, source in streams.items():
            sequence = [source[index % len(source)] for index in range(N_TIMED)]
            for order_index, method in enumerate(order, 1):
                selector = selectors[method]
                for index in range(N_WARMUP):
                    record = source[index % len(source)]
                    if method == "CFSM":
                        cfsm.current_action = record["state"].previous_action
                        cfsm.cooldown_remaining = int(record.get("cooldown_before", 0))
                    selector(record)
                before = telemetry()
                samples = np.empty(N_TIMED, dtype=np.int64)
                for index, record in enumerate(sequence):
                    if method == "CFSM":
                        cfsm.current_action = record["state"].previous_action
                        cfsm.cooldown_remaining = int(record.get("cooldown_before", 0))
                    begin = time.perf_counter_ns()
                    selector(record)
                    samples[index] = time.perf_counter_ns() - begin
                after = telemetry()
                filename = f"block-{block:02d}-{stream_name}-{method}.npy"
                np.save(OUT / "raw" / filename, samples, allow_pickle=False)
                rows.append(
                    {
                        "campaign_id": CAMPAIGN_ID,
                        "stream": stream_name,
                        "benchmark_block": block,
                        "run_id": f"p1b-r1-{stream_name}-b{block:02d}-{method}",
                        "method": method,
                        "order": order_index,
                        "n_warmup": N_WARMUP,
                        "n_timed": N_TIMED,
                        "mean_ns": float(samples.mean()),
                        "median_ns": float(np.median(samples)),
                        "p95_ns": float(np.percentile(samples, 95)),
                        "p99_ns": float(np.percentile(samples, 99)),
                        "sd_ns": float(samples.std(ddof=1)),
                        "telemetry_before": before,
                        "telemetry_after": after,
                        "raw_array_path": "raw/" + filename,
                        "raw_array_sha256": digest(OUT / "raw" / filename),
                        "valid": True,
                    }
                )
    provenance = {
        "campaign_id": CAMPAIGN_ID,
        "status": "PASS",
        "replacement_for": "original P1B invalid historical attempt",
        "authorization_sha256": digest(ROOT / "P1_FINAL_CLOSURE_AUTHORIZATION.md"),
        "config_sha256": config.sha256,
        "tabular_policy_hash": tabular_meta["policy_identity_sha256"],
        "dqn_policy_hash": dqn_meta["policy_identity_sha256"],
        "source_hashes": {
            "benchmark": digest(Path(__file__)),
            "cfsm": digest(ROOT / "scheduler/cfsm.py"),
            "state": digest(ROOT / "scheduler/state.py"),
            "tabular_q": digest(ROOT / "scheduler/tabular_q.py"),
            "dqn": digest(ROOT / "scheduler/dqn.py"),
        },
        "host": {
            "platform": platform.platform(),
            "model": file_text(Path("/proc/device-tree/model")),
            "cpuinfo_sha256": digest(Path("/proc/cpuinfo")),
        },
        "order_seed": ORDER_SEED,
        "orders": orders,
        "rows": len(rows),
        "semantic_validation": validation,
        "timing_boundary": "production selector call only; CFSM hidden state prepared before timer",
        "joule_inference": False,
    }
    (OUT / "registry.json").write_text(json.dumps(rows, indent=2) + "\n")
    (OUT / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "rows": len(rows)}))


if __name__ == "__main__":
    main()
