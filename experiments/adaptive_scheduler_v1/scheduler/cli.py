"""Command-line lifecycle for training, freezing, and isolated software evaluation."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any, Sequence

import numpy as np

from .artifacts import (
    freeze_policy,
    load_metadata,
    load_policy,
    save_trained_policy,
)
from .cfsm import CFSMScheduler
from .config import DEFAULT_CONFIG_PATH, LoadedConfig, load_config, sha256_file
from .dqn import DQNPolicy
from .evaluation import StaticPolicy, add_posthoc_test_metrics, evaluate_online_episode
from .offline_reference import LabelInformedPerWindowUtilityReference
from .state import ACTION_ORDER, Action, OnlineStateTracker, StateEncoder
from .tabular_q import TabularQPolicy
from .trace_io import (
    TRACE_NAME,
    load_npz_episode,
    load_partition_episodes,
)
from .window_log import JsonlWindowLogger


def _json_print(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False))


def _default_policy_input_dir(config: LoadedConfig) -> Path:
    return config.path.parents[1] / "policy_inputs"


def _verify_stage_bindings(config: LoadedConfig) -> dict[str, str]:
    root = config.path.parents[2]
    bindings = config.data["authority_and_provenance"]["adaptive_stage_inputs"]
    checks = {
        "authorization": (
            root / bindings["authorization_path"],
            bindings["authorization_sha256"],
        ),
        "plan": (root / bindings["plan_path"], bindings["plan_sha256"]),
        "policy_input_builder": (
            root / bindings["policy_input_builder_path"],
            bindings["policy_input_builder_sha256"],
        ),
        "policy_input_manifest": (
            root / bindings["policy_input_manifest_path"],
            bindings["policy_input_manifest_sha256_at_configuration"],
        ),
        "cost_registry": (
            root / bindings["cost_registry_path"],
            bindings["cost_registry_sha256_at_configuration"],
        ),
    }
    observed: dict[str, str] = {}
    for name, (path, expected) in checks.items():
        actual = sha256_file(path)
        if actual != expected:
            raise ValueError(
                f"bound adaptive-stage input changed: {name}: expected {expected}, got {actual}"
            )
        observed[name] = actual
    return observed


def _require_new_directory(path: str | Path) -> Path:
    destination = Path(path).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    return destination


def _load_train_validation(args, config: LoadedConfig):
    _verify_stage_bindings(config)
    input_dir = Path(args.input_dir).resolve() if args.input_dir else _default_policy_input_dir(config)
    manifest = Path(args.input_manifest).resolve() if args.input_manifest else input_dir / "manifest.json"
    train = load_partition_episodes(
        input_dir,
        partition="train",
        config=config.data,
        manifest_path=manifest,
        load_labels=True,
    )
    validation = load_partition_episodes(
        input_dir,
        partition="validation",
        config=config.data,
        manifest_path=manifest,
        load_labels=True,
    )
    return train, validation, manifest


def command_validate_config(args, config: LoadedConfig) -> int:
    bindings = _verify_stage_bindings(config)
    _json_print(
        {
            "status": "PASS",
            "config_id": config.config_id,
            "config_path": str(config.path),
            "config_sha256": config.sha256,
            "formal_test_executed": False,
            "physical_experiment_executed": False,
            "adaptive_stage_bindings": bindings,
        }
    )
    return 0


def command_validate_inputs(args, config: LoadedConfig) -> int:
    train, validation, manifest = _load_train_validation(args, config)
    _json_print(
        {
            "status": "PASS",
            "manifest": str(manifest),
            "train": {item.path.name: item.sha256 for item in train},
            "validation": {item.path.name: item.sha256 for item in validation},
            "test_opened": False,
            "phase_ids_read": False,
        }
    )
    return 0


def _train(args, config: LoadedConfig, algorithm: str) -> int:
    from .training import train_and_select

    train, validation, manifest = _load_train_validation(args, config)
    output = Path(args.output_dir).resolve()
    progress = (
        Path(args.training_log).resolve()
        if args.training_log
        else output.parent / f"{output.name}.training.jsonl"
    )
    if output.exists():
        raise FileExistsError(f"refusing to overwrite {output}")
    policy = TabularQPolicy(config.data) if algorithm == "Tabular-Q" else DQNPolicy(config.data)
    selected, metadata = train_and_select(
        policy,
        train_episodes=train,
        validation_episodes=validation,
        config=config.data,
        progress_path=progress,
    )
    metadata.update(
        {
            "policy_input_manifest": str(manifest),
            "policy_input_manifest_sha256": sha256_file(manifest),
            "training_log": str(progress),
            "training_log_sha256": sha256_file(progress),
            "analysis_only_phase_ids_read": False,
            "online_observation_limit": config.data["software_trace_adapter"][
                "missing_online_member_behavior"
            ]["claim_boundary"],
        }
    )
    artifact = save_trained_policy(
        output,
        config=config,
        policy=selected,
        training_metadata=metadata,
    )
    _json_print(
        {
            "status": artifact["status"],
            "algorithm": algorithm,
            "artifact_dir": str(output),
            "policy_identity_sha256": artifact["policy_identity_sha256"],
            "test_data_accessed": False,
            "next_step": "freeze-policy",
        }
    )
    return 0


def command_train_tabular(args, config: LoadedConfig) -> int:
    return _train(args, config, "Tabular-Q")


def command_train_dqn(args, config: LoadedConfig) -> int:
    return _train(args, config, "DQN")


def command_freeze(args, config: LoadedConfig) -> int:
    metadata = freeze_policy(args.input_dir, args.output_dir, config=config)
    _json_print(
        {
            "status": metadata["status"],
            "algorithm": metadata["algorithm"],
            "output_dir": str(Path(args.output_dir).resolve()),
            "policy_identity_sha256": metadata["policy_identity_sha256"],
            "evaluation_updates": False,
        }
    )
    return 0


def command_inspect(args, config: LoadedConfig) -> int:
    _, metadata = load_metadata(args.policy_dir)
    if metadata.get("config_sha256") != config.sha256:
        raise ValueError("policy/config digest mismatch")
    _json_print(metadata)
    return 0


def _load_test_episodes(args, config: LoadedConfig):
    if not args.acknowledge_heldout_test:
        raise ValueError("held-out evaluation requires --acknowledge-heldout-test")
    input_dir = Path(args.input_dir).resolve()
    manifest = Path(args.input_manifest).resolve()
    return load_partition_episodes(
        input_dir,
        partition="test",
        config=config.data,
        manifest_path=manifest,
        load_labels=False,
    )


def _load_test_manifest(args, config: LoadedConfig) -> tuple[Path, dict[str, Any]]:
    if not args.acknowledge_heldout_test:
        raise ValueError("held-out evaluation requires --acknowledge-heldout-test")
    path = Path(args.input_manifest).resolve()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS":
        raise ValueError("test manifest status is not PASS")
    if manifest.get("config_sha256") != config.sha256:
        raise ValueError("test manifest/config binding mismatch")
    if manifest.get("test_trace_seeds") != config.data["experiment_scope"]["formal_test_trace_seeds"]:
        raise ValueError("test manifest seed set differs from config")
    if manifest.get("created_only_after_both_policies_frozen") is not True:
        raise ValueError("test manifest does not prove both policies were frozen first")
    if set(manifest.get("frozen_policies", {})) != {"Tabular-Q", "DQN"}:
        raise ValueError("test manifest frozen-policy set is incomplete")
    return path, manifest


def _verify_test_manifest_policy(
    manifest: dict[str, Any], policy_dir: str | Path, metadata: dict[str, Any]
) -> str:
    expected = manifest["frozen_policies"].get(metadata["algorithm"])
    if expected is None:
        raise ValueError("policy is not bound by the test manifest")
    metadata_sha256 = sha256_file(Path(policy_dir).resolve() / "metadata.json")
    observed = {
        "policy_identity_sha256": metadata.get("policy_identity_sha256"),
        "metadata_sha256": metadata_sha256,
        "weights_sha256": metadata.get("weights_sha256"),
    }
    if observed != expected:
        raise ValueError("policy/test-manifest binding mismatch")
    return metadata_sha256


def _save_selected_predictions(destination: Path, schedules) -> dict[str, str]:
    identities: dict[str, str] = {}
    for schedule in schedules:
        probabilities = np.concatenate(schedule.selected_probabilities).astype(np.float32)
        actions = np.asarray([action.value for action in schedule.actions])
        path = destination / f"{schedule.episode.trace_id}.selected.npz"
        np.savez_compressed(
            path,
            selected_attack_probabilities=probabilities,
            selected_actions=actions,
            trace_sha256=np.asarray(schedule.episode.sha256),
            labels_included=np.asarray(False),
        )
        identities[path.name] = sha256_file(path)
    return identities


def _evaluate(args, config: LoadedConfig, *, cfsm: bool, static_action: str | None = None) -> int:
    manifest_path, manifest = _load_test_manifest(args, config)
    policy_metadata_sha256 = None
    if static_action is not None:
        policy = StaticPolicy(Action.parse(static_action))
        metadata = {
            "algorithm": policy.algorithm_id,
            "policy_identity_sha256": None,
            "frozen": True,
        }
    elif cfsm:
        policy = CFSMScheduler(config.data)
        metadata = {
            "algorithm": "CFSM",
            "policy_identity_sha256": None,
            "frozen": True,
        }
    else:
        policy, metadata = load_policy(args.policy_dir, config=config, require_frozen=True)
        policy_metadata_sha256 = _verify_test_manifest_policy(
            manifest, args.policy_dir, metadata
        )
    episodes = _load_test_episodes(args, config)
    output = _require_new_directory(args.output_dir)
    method = metadata["algorithm"]
    logger = JsonlWindowLogger(
        output / "windows.jsonl",
        config_id=config.config_id,
        config_sha256=config.sha256,
    )
    schedules = []
    for episode in episodes:
        schedules.append(
            evaluate_online_episode(
                policy,
                episode,
                config=config.data,
                config_id=config.config_id,
                config_sha256=config.sha256,
                run_id=f"{method}-{episode.trace_id}",
                logger=logger,
                policy_artifact_sha256=metadata.get("policy_identity_sha256"),
            )
        )
    prediction_hashes = _save_selected_predictions(output, schedules)
    posthoc = []
    # This branch is reached only after every online schedule and prediction
    # artifact has been completed. The online loader never accessed labels.
    if args.posthoc_labels_from_same_npz:
        for schedule in schedules:
            posthoc.append(
                add_posthoc_test_metrics(
                    schedule,
                    logger=logger,
                    run_id=f"{method}-{schedule.episode.trace_id}",
                    method=method,
                )
            )
    summary = {
        "schema_version": 1,
        "status": "software_test_schedule_complete",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "method": method,
        "config_id": config.config_id,
        "config_sha256": config.sha256,
        "policy_identity_sha256": metadata.get("policy_identity_sha256"),
        "policy_metadata_sha256": policy_metadata_sha256,
        "policy_frozen": True,
        "test_input_manifest": str(manifest_path),
        "test_input_manifest_sha256": sha256_file(manifest_path),
        "online_test_labels_accessed": False,
        "posthoc_test_labels_accessed": bool(args.posthoc_labels_from_same_npz),
        "test_trace_sha256": {item.path.name: item.sha256 for item in episodes},
        "selected_prediction_artifacts": prediction_hashes,
        "posthoc_metrics": posthoc,
        "physical_measurement_performed": False,
        "cost_interpretation": "TON static-profile lookup proxy, not measured current-window energy",
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _json_print(summary)
    return 0


def command_evaluate_test(args, config: LoadedConfig) -> int:
    return _evaluate(args, config, cfsm=False)


def command_evaluate_cfsm(args, config: LoadedConfig) -> int:
    return _evaluate(args, config, cfsm=True)


def command_evaluate_static(args, config: LoadedConfig) -> int:
    return _evaluate(args, config, cfsm=False, static_action=args.action)


def command_offline_reference(args, config: LoadedConfig) -> int:
    if not args.acknowledge_heldout_test:
        raise ValueError("offline test reference requires --acknowledge-heldout-test")
    if not args.acknowledge_nondeployable_label_reference:
        raise ValueError(
            "offline reference requires --acknowledge-nondeployable-label-reference"
        )
    # Verify every evaluated RL policy is already frozen before opening labels.
    fixed_policy_identities = []
    policy_metadata = []
    for directory in args.frozen_policy_dir:
        _, metadata = load_policy(directory, config=config, require_frozen=True)
        fixed_policy_identities.append(metadata["policy_identity_sha256"])
        policy_metadata.append((directory, metadata))
    input_dir = Path(args.input_dir).resolve()
    manifest_path, manifest = _load_test_manifest(args, config)
    manifest_policy_metadata_sha256 = {
        metadata["algorithm"]: _verify_test_manifest_policy(manifest, directory, metadata)
        for directory, metadata in policy_metadata
    }
    if set(manifest_policy_metadata_sha256) != {"Tabular-Q", "DQN"}:
        raise ValueError("offline reference requires the two manifest-bound policies")
    output_hashes = manifest.get("output_sha256", {})
    expected_seeds = config.data["experiment_scope"]["formal_test_trace_seeds"]
    paths = {int(TRACE_NAME.fullmatch(path.name).group(2)): path for path in input_dir.glob("test_drift_*.npz") if TRACE_NAME.fullmatch(path.name)}
    if set(paths) != set(expected_seeds):
        raise ValueError("offline reference test seed set mismatch")
    episodes = []
    for seed in expected_seeds:
        path = paths[seed]
        expected_hash = output_hashes.get(path.name)
        if expected_hash is None:
            raise ValueError(f"test manifest has no digest for {path.name}")
        episodes.append(
            load_npz_episode(
                path,
                partition="test",
                config=config.data,
                expected_sha256=expected_hash,
                load_labels=True,
                allow_posthoc_test_labels=True,
            )
        )
    output = _require_new_directory(args.output_dir)
    logger = JsonlWindowLogger(
        output / "offline_reference.jsonl",
        config_id=config.config_id,
        config_sha256=config.sha256,
    )
    reference = LabelInformedPerWindowUtilityReference(config.data)
    summaries = []
    for episode in episodes:
        tracker = OnlineStateTracker(config.data)
        encoder = StateEncoder(config.data)
        episode_return = 0.0
        action_counts = {action: 0 for action in config.data["actions"]["ordered_light_to_heavy"]}
        for window_index in range(episode.windows):
            state = tracker.begin_window(episode.pre_decision(window_index))
            encoded = encoder.encode(state)
            decision = reference.choose(
                episode=episode,
                state=state,
                window_index=window_index,
                policy_frozen=True,
            )
            outcome = episode.outcome_for_action(window_index, decision.action)
            logger.append(
                {
                    "event_type": "offline_reference_window",
                    "algorithm_id": reference.algorithm_id,
                    "display_name": reference.display_name,
                    "deployable": False,
                    "oracle": False,
                    "globally_optimal": False,
                    "optimization_horizon": "one window",
                    "trace_id": episode.trace_id,
                    "window_index": window_index,
                    "state_index": encoded.index,
                    "selected_action": decision.action.value,
                    "all_action_scalar_rewards": dict(decision.all_action_scalar_rewards),
                    "selected_reward": decision.reward.as_dict(),
                    "labels_used_posthoc": True,
                }
            )
            tracker.complete_window(
                window_index=window_index,
                selected_action=decision.action,
                selected_attack_probabilities=outcome.attack_probabilities,
                arrivals_in_window=int(episode.arrivals[window_index]),
            )
            episode_return += decision.reward.scalar_reward
            action_counts[decision.action.value] += 1
        summaries.append(
            {
                "trace_id": episode.trace_id,
                "episode_return": episode_return,
                "action_counts": action_counts,
            }
        )
    summary = {
        "status": "posthoc_label_informed_reference_complete",
        "algorithm_id": reference.algorithm_id,
        "display_name": reference.display_name,
        "deployable": False,
        "oracle": False,
        "globally_optimal": False,
        "optimization_horizon": "one window",
        "fixed_policy_identities_verified_before_label_access": fixed_policy_identities,
        "fixed_policy_metadata_sha256": manifest_policy_metadata_sha256,
        "test_input_manifest": str(manifest_path),
        "test_input_manifest_sha256": sha256_file(manifest_path),
        "test_labels_used_posthoc": True,
        "episodes": summaries,
    }
    (output / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    _json_print(summary)
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-config")
    validate.set_defaults(handler=command_validate_config)

    validate_inputs = subparsers.add_parser("validate-inputs")
    validate_inputs.add_argument("--input-dir")
    validate_inputs.add_argument("--input-manifest")
    validate_inputs.set_defaults(handler=command_validate_inputs)

    for name, handler in (
        ("train-tabular", command_train_tabular),
        ("train-dqn", command_train_dqn),
    ):
        train = subparsers.add_parser(name)
        train.add_argument("--input-dir")
        train.add_argument("--input-manifest")
        train.add_argument("--output-dir", required=True)
        train.add_argument("--training-log")
        train.set_defaults(handler=handler)

    freeze = subparsers.add_parser("freeze-policy")
    freeze.add_argument("--input-dir", required=True)
    freeze.add_argument("--output-dir", required=True)
    freeze.set_defaults(handler=command_freeze)

    inspect = subparsers.add_parser("inspect-policy")
    inspect.add_argument("--policy-dir", required=True)
    inspect.set_defaults(handler=command_inspect)

    for name, handler, needs_policy in (
        ("evaluate-test", command_evaluate_test, True),
        ("evaluate-cfsm-test", command_evaluate_cfsm, False),
        ("evaluate-static-test", command_evaluate_static, False),
    ):
        evaluate = subparsers.add_parser(name)
        if needs_policy:
            evaluate.add_argument("--policy-dir", required=True)
        if name == "evaluate-static-test":
            evaluate.add_argument("--action", choices=[item.value for item in ACTION_ORDER], required=True)
        evaluate.add_argument("--input-dir", required=True)
        evaluate.add_argument("--input-manifest", required=True)
        evaluate.add_argument("--output-dir", required=True)
        evaluate.add_argument("--acknowledge-heldout-test", action="store_true")
        evaluate.add_argument("--posthoc-labels-from-same-npz", action="store_true")
        evaluate.set_defaults(handler=handler)

    reference = subparsers.add_parser("offline-reference-test")
    reference.add_argument("--input-dir", required=True)
    reference.add_argument("--input-manifest", required=True)
    reference.add_argument("--output-dir", required=True)
    reference.add_argument("--frozen-policy-dir", action="append", required=True)
    reference.add_argument("--acknowledge-heldout-test", action="store_true")
    reference.add_argument(
        "--acknowledge-nondeployable-label-reference", action="store_true"
    )
    reference.set_defaults(handler=command_offline_reference)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        return int(args.handler(args, config))
    except Exception as exc:
        print(
            json.dumps(
                {
                    "status": "ERROR",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
