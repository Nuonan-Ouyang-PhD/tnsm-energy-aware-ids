"""Run the frozen P1D reward-weight and state-ablation matrix."""
from __future__ import annotations

import copy
import csv
import hashlib
import json
from pathlib import Path

import numpy as np

from scheduler import evaluation, training
from scheduler.config import load_config
from scheduler.dqn import DQNPolicy
from scheduler.isolation import Partition
from scheduler.metrics import binary_metrics
from scheduler.reward import RewardFunction
from scheduler.state import ACTION_ORDER, EncodedState, StateEncoder as BaseEncoder
from scheduler.tabular_q import TabularQPolicy
from scheduler.trace_io import load_npz_episode
from scheduler.window_log import JsonlWindowLogger


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "p1d_reward_state"
SEEDS = (2003, 2011, 2017, 2027, 2029)
WEIGHTS = {
    "default": (0.50, 0.20, 0.20, 0.10),
    "detection_heavy": (0.80, 0.10, 0.05, 0.05),
    "energy_heavy": (0.40, 0.40, 0.10, 0.10),
    "latency_heavy": (0.40, 0.10, 0.40, 0.10),
    "thermal_heavy": (0.40, 0.10, 0.10, 0.40),
    "equal": (0.25, 0.25, 0.25, 0.25),
    "detection_only": (1.00, 0.00, 0.00, 0.00),
}
DQN_VARIANTS = ("default", "detection_heavy", "energy_heavy", "equal")
STATE_VARIANTS = {
    "full": None,
    "minus_temperature": "smoothed_temperature_c",
    "minus_threat": "lagged_selected_model_threat",
    "minus_queue": "predecision_queue_utilization",
    "minus_arrival": "lagged_arrival_rate_ratio",
    "minus_previous_action": "previous_action",
}
FIELDS = (
    "smoothed_temperature_c",
    "lagged_selected_model_threat",
    "predecision_queue_utilization",
    "lagged_arrival_rate_ratio",
    "previous_action",
)
DIMS = (3, 3, 3, 3, 4)


def sha(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def derived_hash(config: dict) -> str:
    return hashlib.sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def encoder_for(removed: str | None):
    if removed is None:
        return BaseEncoder

    class AblationEncoder:
        def __init__(self, config):
            self.base = BaseEncoder(config)

        def encode(self, state):
            base = self.base.encode(state)
            values = (
                base.temperature_bin,
                base.threat_bin,
                base.queue_bin,
                base.load_bin,
                base.previous_action_index,
            )
            index = 0
            for field, dim, value in zip(FIELDS, DIMS, values):
                if field != removed:
                    index = index * dim + value
            return EncodedState(
                index=index,
                temperature_bin=base.temperature_bin if removed != FIELDS[0] else -1,
                threat_bin=base.threat_bin if removed != FIELDS[1] else -1,
                queue_bin=base.queue_bin if removed != FIELDS[2] else -1,
                load_bin=base.load_bin if removed != FIELDS[3] else -1,
                previous_action_index=(
                    base.previous_action_index if removed != FIELDS[4] else -1
                ),
            )

    return AblationEncoder


def load_episodes(config: dict, partition: Partition):
    if partition is Partition.TEST:
        directory = ROOT / "test_policy_inputs"
        manifest = json.loads((directory / "manifest.json").read_text())
        seeds = manifest["test_trace_seeds"]
        load_labels = False
    else:
        directory = ROOT / "policy_inputs"
        manifest = json.loads((directory / "manifest.json").read_text())
        key = "train_trace_seeds" if partition is Partition.TRAIN else "validation_trace_seeds"
        seeds = manifest[key]
        load_labels = True
    result = []
    for seed in seeds:
        name = f"{partition.value}_drift_{seed}.npz"
        result.append(
            load_npz_episode(
                directory / name,
                partition=partition,
                config=config,
                expected_sha256=manifest["output_sha256"][name],
                load_labels=load_labels,
            )
        )
    return result


def evaluate(policy, episodes, config, config_hash, run_id, partition, log_path):
    logger = JsonlWindowLogger(
        log_path, config_id="TNSM-P1D-20260908-V1", config_sha256=config_hash
    )
    labels_all = []
    predictions_all = []
    action_counts = {action.value: 0 for action in ACTION_ORDER}
    components = {"detection": [], "power": [], "latency": [], "thermal": [], "reward": []}
    switches = 0
    unique_states = set()
    reward = RewardFunction(config)
    for episode in episodes:
        scheduled = evaluation.evaluate_online_episode(
            policy,
            episode,
            config=config,
            config_id="TNSM-P1D-20260908-V1",
            config_sha256=config_hash,
            run_id=run_id,
            logger=logger,
            policy_artifact_sha256=None,
        )
        labels = (
            episode._labels
            if partition is Partition.VALIDATION
            else episode.load_labels_posthoc(schedule_complete=True, policy_frozen=True)
        )
        labels_all.extend(labels.astype(int).tolist())
        for window_index, (action, probabilities) in enumerate(
            zip(scheduled.actions, scheduled.selected_probabilities)
        ):
            row_slice = episode._slice(window_index)
            predictions_all.extend((probabilities >= 0.5).astype(int).tolist())
            action_counts[action.value] += 1
            state = None
            # Reward is descriptive here and cannot influence the frozen policy.
            outcome = episode.outcome_for_action(window_index, action)
            pre_temperature = float(episode.temperatures[window_index])
            c = reward.calculate(
                labels=labels[row_slice].tolist(),
                attack_probabilities=probabilities.tolist(),
                predecision_smoothed_temperature_c=pre_temperature,
                cost=outcome.cost,
                prediction_threshold=float(config["actions"]["prediction_threshold"]),
            )
            components["detection"].append(c.detection)
            components["power"].append(c.power)
            components["latency"].append(c.latency)
            components["thermal"].append(c.positive_thermal_increment)
            components["reward"].append(c.scalar_reward)
        switches += scheduled.switches
    for line in log_path.read_text().splitlines():
        item = json.loads(line)
        if item.get("event_type") == "window_decision":
            unique_states.add(item["encoded_state"]["index"])
    total = sum(action_counts.values())
    return {
        "metrics": binary_metrics(labels_all, predictions_all),
        "switches": switches,
        "action_counts": action_counts,
        "action_occupancy": {key: value / total for key, value in action_counts.items()},
        "unique_states": len(unique_states),
        "reward_components_mean": {key: float(np.mean(value)) for key, value in components.items()},
        "labels_used_only_after_frozen_schedule": partition is Partition.TEST,
    }


def run_one(family: str, algorithm: str, variant: str, seed: int, removed=None):
    run_id = f"{family}-{algorithm.lower().replace('-', '')}-{variant}-{seed}"
    run_dir = OUT / run_id
    if (run_dir / "summary.json").exists():
        return json.loads((run_dir / "summary.json").read_text())
    run_dir.mkdir(parents=True, exist_ok=True)
    base = load_config(ROOT / "config" / "scheduler_experiment_v1.json").data
    config = copy.deepcopy(base)
    if family == "reward":
        d, p, l, t = WEIGHTS[variant]
        config["reward"]["weights"] = {
            "detection": d,
            "power": p,
            "latency": l,
            "positive_thermal_increment": t,
        }
    if removed is not None:
        fields = list(config["online_state"]["ordered_fields"])
        fields.remove(removed)
        config["online_state"]["ordered_fields"] = fields
        cardinality = 1
        for field, dim in zip(FIELDS, DIMS):
            if field != removed:
                cardinality *= dim
        config["online_state"]["discrete_state_cardinality"] = cardinality
    config_hash = derived_hash(config)
    (run_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    encoder = encoder_for(removed)
    training.StateEncoder = encoder
    evaluation.StateEncoder = encoder
    train_eps = load_episodes(config, Partition.TRAIN)
    validation_eps = load_episodes(config, Partition.VALIDATION)
    test_eps = load_episodes(config, Partition.TEST)
    policy = TabularQPolicy(config, seed=seed) if algorithm == "Tabular-Q" else DQNPolicy(config, seed=seed)
    policy, selection = training.train_and_select(
        policy,
        train_episodes=train_eps,
        validation_episodes=validation_eps,
        config=config,
        progress_path=run_dir / "training.jsonl",
    )
    policy.freeze()
    if algorithm == "Tabular-Q":
        weights_path = run_dir / "q_values.npy"
        np.save(weights_path, policy.q_values, allow_pickle=False)
    else:
        import torch

        weights_path = run_dir / "dqn_online_state.pt"
        torch.save(policy.copy_online_state(), weights_path)
    validation = evaluate(
        policy,
        validation_eps,
        config,
        config_hash,
        run_id,
        Partition.VALIDATION,
        run_dir / "validation_windows.jsonl",
    )
    test = evaluate(
        policy,
        test_eps,
        config,
        config_hash,
        run_id,
        Partition.TEST,
        run_dir / "test_windows.jsonl",
    )
    summary = {
        "status": "PASS",
        "analysis_family": family,
        "algorithm": algorithm,
        "variant": variant,
        "removed_state_field": removed,
        "state_cardinality": config["online_state"]["discrete_state_cardinality"],
        "seed": seed,
        "training_episodes": 1000,
        "selection": selection,
        "validation": validation,
        "test_descriptive_only": test,
        "test_used_for_training_or_selection": False,
        "policy_hash": sha(weights_path),
        "config_hash": config_hash,
        "normalization_constants_unchanged": True,
        "threshold_and_split_unchanged": True,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"event": "p1d_run_complete", "run_id": run_id}), flush=True)
    return summary


def rebuild_registry():
    rows = []
    for path in sorted(OUT.glob("*/summary.json")):
        item = json.loads(path.read_text())
        rows.append(item)
    (OUT / "registry.json").write_text(json.dumps(rows, indent=2) + "\n")
    return rows


def main():
    OUT.mkdir(exist_ok=True)
    for variant in WEIGHTS:
        for seed in SEEDS:
            run_one("reward", "Tabular-Q", variant, seed)
    for variant in DQN_VARIANTS:
        for seed in SEEDS:
            run_one("reward", "DQN", variant, seed)
    for variant, removed in STATE_VARIANTS.items():
        for seed in SEEDS:
            run_one("state", "Tabular-Q", variant, seed, removed=removed)
    rows = rebuild_registry()
    print(json.dumps({"event": "p1d_complete", "runs": len(rows)}), flush=True)


if __name__ == "__main__":
    main()
