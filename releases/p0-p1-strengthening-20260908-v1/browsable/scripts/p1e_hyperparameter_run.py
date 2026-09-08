"""Run the optional, predeclared P1E Tabular-Q sensitivity matrix."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np

import p1d_reward_state_run as core
from scheduler import evaluation, training
from scheduler.config import load_config
from scheduler.isolation import Partition
from scheduler.state import StateEncoder
from scheduler.tabular_q import TabularQPolicy


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "p1e_hyperparameter"
SEEDS = (2003, 2011, 2017, 2027, 2029)
VARIANTS = (
    ("gamma", "gamma_0.00", 0.10, 0.00),
    ("gamma", "gamma_0.50", 0.10, 0.50),
    ("gamma", "gamma_0.90", 0.10, 0.90),
    ("gamma", "gamma_0.99", 0.10, 0.99),
    ("alpha", "alpha_0.05", 0.05, 0.90),
    ("alpha", "alpha_0.10", 0.10, 0.90),
    ("alpha", "alpha_0.20", 0.20, 0.90),
)


def run_one(axis: str, variant: str, alpha: float, gamma: float, seed: int):
    run_id = f"{axis}-{variant}-{seed}"
    run_dir = OUT / run_id
    if (run_dir / "summary.json").exists():
        return json.loads((run_dir / "summary.json").read_text())
    run_dir.mkdir(parents=True, exist_ok=False)
    config = copy.deepcopy(load_config(ROOT / "config/scheduler_experiment_v1.json").data)
    config["tabular_q"]["alpha"] = alpha
    config["tabular_q"]["gamma"] = gamma
    config_hash = core.derived_hash(config)
    (run_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n")
    training.StateEncoder = StateEncoder
    evaluation.StateEncoder = StateEncoder
    train_eps = core.load_episodes(config, Partition.TRAIN)
    validation_eps = core.load_episodes(config, Partition.VALIDATION)
    test_eps = core.load_episodes(config, Partition.TEST)
    policy = TabularQPolicy(config, seed=seed)
    policy, selection = training.train_and_select(
        policy,
        train_episodes=train_eps,
        validation_episodes=validation_eps,
        config=config,
        progress_path=run_dir / "training.jsonl",
    )
    policy.freeze()
    weights = run_dir / "q_values.npy"
    np.save(weights, policy.q_values, allow_pickle=False)
    validation = core.evaluate(
        policy,
        validation_eps,
        config,
        config_hash,
        run_id,
        Partition.VALIDATION,
        run_dir / "validation_windows.jsonl",
    )
    test = core.evaluate(
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
        "analysis_family": "hyperparameter",
        "axis": axis,
        "variant": variant,
        "alpha": alpha,
        "gamma": gamma,
        "seed": seed,
        "training_episodes": 1000,
        "selection": selection,
        "validation": validation,
        "test_descriptive_only": test,
        "test_used_for_training_or_selection": False,
        "policy_hash": core.sha(weights),
        "config_hash": config_hash,
        "reward_state_threshold_split_unchanged": True,
        "not_a_primary_policy_search": True,
    }
    (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({"event": "p1e_run_complete", "run_id": run_id}), flush=True)
    return summary


def main():
    OUT.mkdir(exist_ok=True)
    for axis, variant, alpha, gamma in VARIANTS:
        for seed in SEEDS:
            run_one(axis, variant, alpha, gamma, seed)
    rows = [json.loads(path.read_text()) for path in sorted(OUT.glob("*/summary.json"))]
    (OUT / "registry.json").write_text(json.dumps(rows, indent=2) + "\n")
    print(json.dumps({"event": "p1e_complete", "runs": len(rows)}), flush=True)


if __name__ == "__main__":
    main()
