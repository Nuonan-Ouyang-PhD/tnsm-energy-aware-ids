"""Derived validation/test evaluation of the 20 existing frozen P1C policies."""
from __future__ import annotations

import csv
import json
from pathlib import Path

import numpy as np
import torch

import p1d_reward_state_run as core
from scheduler.config import load_config
from scheduler.dqn import DQNPolicy
from scheduler.isolation import Partition
from scheduler.state import ACTION_ORDER, EncodedState
from scheduler.tabular_q import TabularQPolicy


ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / "p1c_multiseed"
OUT = ROOT / "p1c_derived_evaluation"


def load_frozen(source: Path, algorithm: str, seed: int, config):
    if algorithm == "Tabular-Q":
        policy = TabularQPolicy(config, seed=seed)
        policy.q_values[:] = np.load(source / "q_values.npy", allow_pickle=False)
        weights = source / "q_values.npy"
    else:
        policy = DQNPolicy(config, seed=seed)
        state = torch.load(source / "dqn_online_state.pt", map_location="cpu", weights_only=True)
        policy.load_online_state(state)
        weights = source / "dqn_online_state.pt"
    policy.freeze()
    return policy, weights


def main():
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    OUT.mkdir()
    loaded = load_config(ROOT / "config" / "scheduler_experiment_v1.json")
    config = loaded.data
    validation_eps = core.load_episodes(config, Partition.VALIDATION)
    test_eps = core.load_episodes(config, Partition.TEST)
    validation_manifest = json.loads((ROOT / "policy_inputs/manifest.json").read_text())
    test_manifest = json.loads((ROOT / "test_policy_inputs/manifest.json").read_text())
    rows = []
    summaries = []
    for source in sorted(path.parent for path in SOURCE.glob("*/metadata.json")):
        metadata = json.loads((source / "metadata.json").read_text())
        algorithm = metadata["algorithm"]
        seed = int(metadata["seed"])
        policy, weights = load_frozen(source, algorithm, seed, config)
        policy_hash = core.sha(weights)
        run_id = f"p1c-derived-{algorithm.lower().replace('-', '')}-{seed}"
        run_dir = OUT / run_id
        run_dir.mkdir()
        action_map = []
        for state_index in range(324):
            encoded = EncodedState(state_index, 0, 0, 0, 0, 0)
            action_map.append(policy.select_action(encoded, training=False).value)
        (run_dir / "action_map.json").write_text(json.dumps(action_map) + "\n")
        validation = core.evaluate(
            policy, validation_eps, config, loaded.sha256, run_id,
            Partition.VALIDATION, run_dir / "validation_windows.jsonl",
        )
        test = core.evaluate(
            policy, test_eps, config, loaded.sha256, run_id,
            Partition.TEST, run_dir / "test_windows.jsonl",
        )
        summary = {
            "status": "PASS",
            "analysis_family": "multiseed-derived-evaluation",
            "algorithm": algorithm,
            "seed": seed,
            "source_frozen_policy_directory": str(source),
            "source_metadata_sha256": core.sha(source / "metadata.json"),
            "policy_hash": policy_hash,
            "config_hash": loaded.sha256,
            "selected_checkpoint": metadata["selection"]["selection"]["training_episode"],
            "existing_validation_selection": metadata["selection"]["selection"],
            "validation_trace_hashes": validation_manifest["output_sha256"],
            "test_trace_hashes": test_manifest["output_sha256"],
            "validation": validation,
            "test_descriptive_only": test,
            "test_used_for_action_selection_training_or_checkpoint_selection": False,
            "retrained": False,
            "checkpoint_reselected": False,
        }
        (run_dir / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
        summaries.append(summary)
        vm = validation["metrics"]
        tm = test["metrics"]
        occ = test["action_occupancy"]
        rows.append({
            "analysis_family": "multiseed-derived-evaluation",
            "algorithm": algorithm,
            "variant": "default",
            "seed": seed,
            "training_episodes": 1000,
            "selected_checkpoint": summary["selected_checkpoint"],
            "validation_return": metadata["selection"]["selection"]["mean_validation_episode_return"],
            "validation_f1": vm["f1"],
            "validation_recall": vm["recall"],
            "validation_fpr": vm["false_positive_rate"],
            "validation_ba": vm["balanced_accuracy"],
            "test_f1": tm["f1"],
            "test_recall": tm["recall"],
            "test_fpr": tm["false_positive_rate"],
            "test_ba": tm["balanced_accuracy"],
            "test_switches": test["switches"],
            "test_occupancy_tinydt": occ["TinyDT"],
            "test_occupancy_lightlr": occ["LightLR"],
            "test_occupancy_medrf": occ["MedRF"],
            "test_occupancy_heavymlp": occ["HeavyMLP"],
            "unique_validation_states": validation["unique_states"],
            "unique_test_states": test["unique_states"],
            "policy_hash": policy_hash,
            "config_hash": loaded.sha256,
            "training_curve_path": str(source / "training.jsonl"),
            "validation_curve_path": str(source / "training.jsonl"),
            "action_map_path": str(run_dir / "action_map.json"),
            "notes": "existing frozen checkpoint; no retraining or reselection; test descriptive only",
        })
        print(json.dumps({"event": "p1c_derived_complete", "run_id": run_id}), flush=True)
    fields = list(rows[0])
    with (OUT / "policy_registry.csv").open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    (OUT / "registry.json").write_text(json.dumps(summaries, indent=2) + "\n")
    print(json.dumps({"status": "PASS", "policies": len(rows)}), flush=True)


if __name__ == "__main__":
    main()
