"""Training/validation-only software pilot. No test files or hardware access.

This checks the new causal loop with real cached classifier predictions and
explicitly approximate costs; it is not a formal experiment or a DQN run.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from core import ACTIONS, STATE_COUNT, Observation, deadline_guard, reward

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SEED = 2003
EPISODES = 10
ALPHA = .1
GAMMA = .9


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write("\n")


def read_pool(name, manifest):
    if name not in ("ton_iot_train_predictions.npz", "validation_drift_401.npz"):
        raise ValueError("only named training/validation inputs are permitted")
    path = ROOT / "experiments/adaptive_scheduler_v1/policy_inputs" / name
    if digest(path) != manifest["output_sha256"][name]:
        raise ValueError("input hash mismatch: " + name)
    with np.load(path, allow_pickle=False) as archive:
        if list(archive["models"]) != list(ACTIONS):
            raise ValueError("model order mismatch")
        key = "probabilities" if name.startswith("ton_iot_train") else "model_probabilities"
        return archive[key].copy(), archive["labels"].copy(), digest(path)


def make_workload(pool, seed):
    probabilities, labels, _ = pool
    rng = np.random.default_rng(seed)
    # Two repetitions of all nine cells; cell order is not an online feature.
    cells = [(n, p) for _ in range(2) for n in (50, 100, 4000) for p in (.1, .5, .9)]
    rng.shuffle(cells)
    classes = [np.flatnonzero(labels == k) for k in (0, 1)]
    windows = []
    for n, prevalence in cells:
        positive = int(round(n * prevalence))
        ids = np.concatenate([rng.choice(classes[0], n - positive, replace=True),
                              rng.choice(classes[1], positive, replace=True)])
        rng.shuffle(ids)
        windows.append((probabilities[ids], labels[ids], ids))
    return windows


def run(windows, method, table, costs, rng, epsilon, update, handle):
    queued_p = np.empty((0, 4), dtype=np.float32)
    queued_y = np.empty(0, dtype=np.int8)
    threat, previous = .5, 0
    totals, occupancy = Counter(), Counter()
    states, queue_bins, arrival_bins = set(), set(), set()
    total_reward = 0.
    for t, (arrived_p, arrived_y, source_ids) in enumerate(windows):
        view = Observation(len(arrived_y), len(queued_y), threat, previous)
        # State is shared by all methods and built before action commitment.
        queued_p = np.concatenate([queued_p, arrived_p])
        queued_y = np.concatenate([queued_y, arrived_y])
        state = view.index
        states.add(state)
        queue_bins.add((state // 12) % 3)
        arrival_bins.add(state // 36)
        if method == "Tabular-Q":
            action = int(rng.integers(4)) if update and rng.random() < epsilon else int(np.argmax(table[state]))
        elif method == "DeadlineGuard":
            # Pilot only: use mean static latency as a transparent stand-in.
            # Formal DeadlineGuard must use a separately measured p95.
            action = deadline_guard(view, costs[2][1])
        else:
            action = ACTIONS.index(method)
        occupancy[ACTIONS[action]] += 1
        power, latency = costs[action]
        batches = max(0, int(math.floor(1 / latency)))
        completed = min(len(queued_y), batches * 100)
        p = queued_p[:completed, action]
        y = queued_y[:completed]
        predicted = p >= .5
        for key, mask in (("tn", (y == 0) & ~predicted), ("fp", (y == 0) & predicted),
                          ("fn", (y == 1) & ~predicted), ("tp", (y == 1) & predicted)):
            totals[key] += int(np.count_nonzero(mask))
        # Unfinished rows count as incorrect for the current-window training
        # utility, not as fabricated classifier predictions in reported counts.
        work_y = queued_y
        recalls = [float(np.count_nonzero((y == k) & (predicted == k))) /
                   int(np.count_nonzero(work_y == k)) for k in (0, 1) if np.any(work_y == k)]
        ba = float(np.mean(recalls)) if recalls else 0.
        queued_p, queued_y = queued_p[completed:], queued_y[completed:]
        duration = math.ceil(completed / 100) * latency
        lo, hi = min(c[0] for c in costs), max(c[0] for c in costs)
        value, parts = reward(balanced_accuracy=ba, normalized_power=(power-lo)/(hi-lo),
                              completion_seconds=duration, backlog_rows=len(queued_y), work_rows=view.work_rows)
        next_threat = float(np.mean(p)) if completed else threat
        if update:
            if t + 1 == len(windows):
                future = 0.
            else:
                next_state = Observation(len(windows[t+1][1]), len(queued_y), next_threat, action).index
                future = float(np.max(table[next_state]))
            table[state, action] += ALPHA * (value + GAMMA * future - table[state, action])
        item = {"window": t, "method": method, "arrivals_now": view.arrivals_now,
                "carryover_before_arrivals": view.carryover_before_arrivals,
                "state": state, "action": ACTIONS[action], "completed_rows": completed,
                "backlog_after": len(queued_y), "reward": value, "components": parts,
                "cost_origin": "historical_TON_static_mean_proxy_no_physical_energy",
                "source_ids_sha256": hashlib.sha256(source_ids.tobytes()).hexdigest()}
        handle.write(json.dumps(item, allow_nan=False) + "\n")
        totals["deadline_miss_windows"] += int(bool(queued_y.size) or duration > 1)
        totals["completed_rows"] += completed
        total_reward += value
        threat, previous = next_threat, action
    tp, fp, fn = totals["tp"], totals["fp"], totals["fn"]
    return {"counts": dict(totals), "final_backlog_rows": len(queued_y),
            "completed_row_f1": 2*tp/(2*tp+fp+fn) if 2*tp+fp+fn else 0.,
            "occupancy": dict(occupancy), "unique_states": len(states),
            "queue_bins": sorted(queue_bins), "arrival_bins": sorted(arrival_bins),
            "reward_sum": total_reward}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source = ROOT / "experiments/adaptive_scheduler_v1"
    manifest = json.loads((source / "policy_inputs/manifest.json").read_text())
    config = json.loads((source / "config/scheduler_experiment_v1.json").read_text())
    train = read_pool("ton_iot_train_predictions.npz", manifest)
    validation = read_pool("validation_drift_401.npz", manifest)
    costs = [(config["resource_cost_registry"]["models"][m]["mean_watts"],
              config["resource_cost_registry"]["models"][m]["mean_batch_latency_ms_median"]/1000)
             for m in ACTIONS]
    save(args.output / "pilot_lock.json", {
        "scope": "EXPLORATORY_TRAIN_VALIDATION_SOFTWARE_PILOT_NOT_FORMAL",
        "created_utc": datetime.now(timezone.utc).isoformat(), "seed": SEED,
        "episodes": EPISODES, "alpha": ALPHA, "gamma": GAMMA,
        "epsilon": "linear 1.0 to 0.01 over ten pilot episodes",
        "workload": "two repetitions of nine cells: 50/100/4000 x .1/.5/.9; shuffle seed=2003+episode",
        "validation_workload_seed": 401, "sampling": "class-conditional with replacement",
        "train_input_sha256": train[2], "validation_input_sha256": validation[2],
        "old_cost_config_sha256": digest(source / "config/scheduler_experiment_v1.json"),
        "source_sha256": {f: digest(HERE/f) for f in ("core.py", "pilot.py")},
        "test_opened": False, "hardware_access": False,
        "latency_model": "static mean per100 rows, zero scheduler cost; NOT measured service/deadline prediction",
        "guard_latency": "same mean proxy, NOT formal p95",
        "thermal_capability_claim": False})
    q = np.zeros((STATE_COUNT, 4))
    rng = np.random.default_rng(SEED)
    training = []
    with (args.output / "training_windows.jsonl").open("x") as handle:
        for episode in range(EPISODES):
            result = run(make_workload(train, SEED+episode), "Tabular-Q", q, costs,
                         rng, 1.-.99*episode/(EPISODES-1), True, handle)
            training.append(result)
    with (args.output / "policy.npy").open("xb") as handle:
        np.save(handle, q, allow_pickle=False)
    policy_hash = digest(args.output / "policy.npy")
    save(args.output / "policy_freeze.json", {"policy_sha256": policy_hash,
         "checkpoint": "last episode; no validation checkpoint selection", "updates_allowed": False})
    results = {}
    for method in ("Tabular-Q", "DeadlineGuard", "LightLR", "MedRF"):
        with (args.output / (method + "_validation.jsonl")).open("x") as handle:
            results[method] = run(make_workload(validation, 401), method, q, costs,
                                  rng, 0., False, handle)
    if digest(args.output / "policy.npy") != policy_hash:
        raise RuntimeError("frozen policy changed")
    save(args.output / "summary.json", {"status": "PILOT_COMPLETE_NOT_FORMAL_RESULTS",
         "train": training, "validation": results, "policy_sha256": policy_hash,
         "test_opened": False, "dqn_executed": False, "physical_runs": 0,
         "no_thermal_claim": True})
    files = sorted(p for p in args.output.iterdir() if p.is_file())
    with (args.output / "MANIFEST_SHA256.txt").open("x") as handle:
        for path in files:
            handle.write(digest(path) + "  " + path.name + "\n")
    print(json.dumps({"output": str(args.output), "policy_sha256": policy_hash,
                      "validation": results, "physical_runs": 0}, indent=2))


if __name__ == "__main__":
    main()
