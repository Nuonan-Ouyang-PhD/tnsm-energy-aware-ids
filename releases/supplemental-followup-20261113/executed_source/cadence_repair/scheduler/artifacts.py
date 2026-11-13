"""No-clobber policy artifact creation, verification, freezing, and loading."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
from typing import Any, Mapping

import numpy as np

from .config import LoadedConfig, sha256_file
from .dqn import DQNPolicy, torch
from .tabular_q import TabularQPolicy


class ArtifactError(ValueError):
    pass


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False)
        + "\n",
        encoding="utf-8",
    )


def _policy_identity(config_sha256: str, algorithm: str, weights_sha256: str) -> str:
    material = f"{config_sha256}\n{algorithm}\n{weights_sha256}\n".encode("utf-8")
    return sha256(material).hexdigest()


def save_trained_policy(
    output_dir: str | Path,
    *,
    config: LoadedConfig,
    policy: TabularQPolicy | DQNPolicy,
    training_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    if isinstance(policy, TabularQPolicy):
        algorithm = policy.algorithm_id
        weights_name = "q_values.npy"
        np.save(destination / weights_name, policy.q_values, allow_pickle=False)
    elif isinstance(policy, DQNPolicy):
        if torch is None:  # pragma: no cover
            raise ArtifactError("PyTorch unavailable")
        algorithm = policy.algorithm_id
        weights_name = "dqn_online_state.pt"
        torch.save(policy.copy_online_state(), destination / weights_name)
    else:
        raise ArtifactError(f"unsupported policy type: {type(policy)!r}")
    weights_hash = sha256_file(destination / weights_name)
    metadata = {
        "schema_version": 1,
        "artifact_type": "adaptive_scheduler_policy",
        "algorithm": algorithm,
        "status": "trained_validation_selected_not_frozen",
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "config_id": config.config_id,
        "config_sha256": config.sha256,
        "weights_file": weights_name,
        "weights_sha256": weights_hash,
        "policy_identity_sha256": _policy_identity(config.sha256, algorithm, weights_hash),
        "partitions_used_for_updates": ["train"],
        "partition_used_for_selection": "validation",
        "test_data_accessed": False,
        "frozen": False,
        "training": dict(training_metadata),
    }
    _write_json(destination / "metadata.json", metadata)
    return metadata


def load_metadata(directory: str | Path) -> tuple[Path, dict[str, Any]]:
    root = Path(directory).resolve()
    try:
        metadata = json.loads((root / "metadata.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ArtifactError(f"cannot load policy metadata from {root}: {exc}") from exc
    weights = root / str(metadata.get("weights_file", ""))
    if not weights.is_file():
        raise ArtifactError("policy weights file is missing")
    observed = sha256_file(weights)
    if observed != metadata.get("weights_sha256"):
        raise ArtifactError("policy weight digest mismatch")
    expected_identity = _policy_identity(
        str(metadata.get("config_sha256")),
        str(metadata.get("algorithm")),
        observed,
    )
    if metadata.get("policy_identity_sha256") != expected_identity:
        raise ArtifactError("policy identity digest mismatch")
    return root, metadata


def freeze_policy(
    input_dir: str | Path,
    output_dir: str | Path,
    *,
    config: LoadedConfig,
) -> dict[str, Any]:
    source, metadata = load_metadata(input_dir)
    if metadata.get("config_id") != config.config_id or metadata.get("config_sha256") != config.sha256:
        raise ArtifactError("training artifact is bound to a different config")
    if metadata.get("frozen") is not False or metadata.get("status") != "trained_validation_selected_not_frozen":
        raise ArtifactError("input artifact is not a train-selected unfrozen policy")
    if metadata.get("test_data_accessed") is not False:
        raise ArtifactError("training artifact reports test-data access")
    if metadata.get("partitions_used_for_updates") != ["train"]:
        raise ArtifactError("policy updates were not restricted to train")
    if metadata.get("partition_used_for_selection") != "validation":
        raise ArtifactError("policy selection was not restricted to validation")
    training = metadata.get("training")
    if not isinstance(training, dict) or training.get("test_data_accessed") is not False:
        raise ArtifactError("training metadata does not prove test isolation")
    if training.get("analysis_only_phase_ids_read") is not False:
        raise ArtifactError("training metadata reports phase-id access")
    settings = "tabular_q" if metadata["algorithm"] == "Tabular-Q" else "dqn"
    if training.get("episodes") != int(config.data[settings]["episodes"]):
        raise ArtifactError("training episode count differs from config")
    evidence = {
        "policy-input manifest": (
            training.get("policy_input_manifest"),
            training.get("policy_input_manifest_sha256"),
        ),
        "training log": (
            training.get("training_log"),
            training.get("training_log_sha256"),
        ),
    }
    for name, (path, expected) in evidence.items():
        if not path or not expected or sha256_file(Path(path)) != expected:
            raise ArtifactError(f"{name} evidence is missing or changed")
    manifest = json.loads(Path(training["policy_input_manifest"]).read_text(encoding="utf-8"))
    output_hashes = manifest.get("output_sha256", {})
    for partition in ("train", "validation"):
        recorded = training.get(f"{partition}_trace_sha256")
        if not isinstance(recorded, dict) or recorded != {
            name: output_hashes.get(name) for name in recorded
        }:
            raise ArtifactError(f"{partition} trace hashes do not match the input manifest")
    destination = Path(output_dir).resolve()
    destination.mkdir(parents=True, exist_ok=False)
    weights_name = str(metadata["weights_file"])
    shutil.copy2(source / weights_name, destination / weights_name)
    frozen = dict(metadata)
    frozen.update(
        {
            "status": "frozen_for_software_evaluation",
            "frozen": True,
            "frozen_at_utc": datetime.now(timezone.utc).isoformat(),
            "source_training_metadata_sha256": sha256_file(source / "metadata.json"),
            "evaluation_updates": False,
        }
    )
    _write_json(destination / "metadata.json", frozen)
    return frozen


def load_policy(
    directory: str | Path,
    *,
    config: LoadedConfig,
    require_frozen: bool,
) -> tuple[TabularQPolicy | DQNPolicy, dict[str, Any]]:
    root, metadata = load_metadata(directory)
    if metadata.get("config_id") != config.config_id or metadata.get("config_sha256") != config.sha256:
        raise ArtifactError("policy artifact/config binding mismatch")
    if require_frozen and metadata.get("frozen") is not True:
        raise ArtifactError("held-out evaluation requires a frozen policy artifact")
    algorithm = metadata.get("algorithm")
    weights = root / metadata["weights_file"]
    if algorithm == "Tabular-Q":
        policy = TabularQPolicy(config.data)
        values = np.load(weights, allow_pickle=False)
        if values.shape != policy.q_values.shape or not np.isfinite(values).all():
            raise ArtifactError("invalid Tabular-Q weights")
        policy.q_values[:] = values
    elif algorithm == "DQN":
        if torch is None:  # pragma: no cover
            raise ArtifactError("PyTorch unavailable")
        policy = DQNPolicy(config.data)
        state_dict = torch.load(weights, map_location="cpu", weights_only=True)
        policy.load_online_state(state_dict)
    else:
        raise ArtifactError(f"unsupported algorithm in artifact: {algorithm!r}")
    if metadata.get("frozen") is True:
        policy.freeze()
    return policy, metadata
