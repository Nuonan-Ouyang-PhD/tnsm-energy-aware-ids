"""Load and strictly validate the single adaptive-scheduler configuration."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
from typing import Any, Mapping


DEFAULT_CONFIG_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "scheduler_experiment_v1.json"
)
EXPECTED_ACTIONS = ["TinyDT", "LightLR", "MedRF", "HeavyMLP"]


class ConfigError(ValueError):
    """Raised when a configuration could weaken a frozen experiment boundary."""


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ConfigError(f"duplicate JSON key: {key!r}")
        result[key] = value
    return result


def _reject_constant(value: str) -> None:
    raise ConfigError(f"non-finite JSON number is forbidden: {value}")


def sha256_file(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class LoadedConfig:
    path: Path
    sha256: str
    data: Mapping[str, Any]

    @property
    def config_id(self) -> str:
        return str(self.data["config_id"])


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ConfigError(message)


def _ascending_pair(value: Any, name: str) -> tuple[float, float]:
    _require(isinstance(value, list) and len(value) == 2, f"{name} must have two values")
    low, high = (float(value[0]), float(value[1]))
    _require(math.isfinite(low) and math.isfinite(high), f"{name} must be finite")
    _require(low < high, f"{name} must be strictly ascending")
    return low, high


def validate_config(data: Mapping[str, Any]) -> None:
    """Validate invariants that protect causality and evaluation isolation."""

    _require(data.get("schema_version") == 1, "unsupported config schema")
    _require(
        data.get("config_id") == "TNSM-ADAPTIVE-SCHEDULER-20260907-V1",
        "unexpected config_id",
    )
    actions = data.get("actions", {}).get("ordered_light_to_heavy")
    _require(actions == EXPECTED_ACTIONS, "action order or membership changed")

    state = data.get("online_state", {})
    _ascending_pair(
        state.get("temperature", {}).get("bins_c_low_medium_high"),
        "temperature bins",
    )
    _ascending_pair(
        state.get("threat", {}).get("bins_low_medium_high"), "threat bins"
    )
    _ascending_pair(
        state.get("queue", {}).get("bins_low_medium_high"), "queue bins"
    )
    _ascending_pair(
        state.get("network_load", {}).get("bins_ratio_low_medium_high"),
        "load bins",
    )
    _require(
        state.get("discrete_state_cardinality") == 3 * 3 * 3 * 3 * 4,
        "discrete state cardinality must remain 324",
    )
    forbidden = set(state.get("forbidden_before_action", []))
    for required in (
        "current_window_labels",
        "test_labels",
        "current_window_phase_id",
        "current_window_counterfactual_predictions",
        "cached_predictions_from_unselected_models",
    ):
        _require(required in forbidden, f"missing online forbidden field: {required}")

    cfsm = data.get("cfsm", {})
    _require(cfsm.get("learned") is False, "CFSM must remain a fixed rule baseline")
    _require(cfsm.get("temperature_warning_c") == 70.0, "CFSM temperature changed")
    _require(cfsm.get("threat_threshold") == 0.7, "CFSM threat threshold changed")
    _require(
        cfsm.get("cooldown_full_windows_after_switch") == 2,
        "CFSM cooldown must be two full windows",
    )

    reward = data.get("reward", {})
    weights = reward.get("weights", {})
    expected_weights = {
        "detection": 0.5,
        "power": 0.2,
        "latency": 0.2,
        "positive_thermal_increment": 0.1,
    }
    _require(weights == expected_weights, "reward weights changed")
    _require(
        math.isclose(sum(float(v) for v in weights.values()), 1.0),
        "reward weights do not sum to one",
    )

    tabular = data.get("tabular_q", {})
    _require(tabular.get("alpha") == 0.1, "Tabular-Q alpha changed")
    _require(tabular.get("gamma") == 0.9, "Tabular-Q gamma changed")
    _require(tabular.get("episodes") == 1000, "Tabular-Q episodes changed")
    _require(tabular.get("evaluation_updates") is False, "evaluation updates enabled")

    dqn = data.get("dqn", {})
    _require(dqn.get("episodes") == 1000, "DQN episodes changed")
    _require(dqn.get("batch_size") == 32, "DQN batch size changed")
    _require(dqn.get("output_actions") == 4, "DQN output size changed")
    _require(dqn.get("evaluation_updates") is False, "DQN evaluation updates enabled")

    roles = data.get("training_and_selection", {})
    _require(roles.get("q_or_network_updates_partition") == "train", "train role changed")
    _require(roles.get("checkpoint_selection_partition") == "validation", "validation role changed")
    _require(roles.get("formal_evaluation_partition") == "test", "test role changed")
    train_seeds = set(roles.get("training_trace_seeds", []))
    validation_seeds = set(roles.get("validation_trace_seeds", []))
    test_seeds = set(data.get("experiment_scope", {}).get("formal_test_trace_seeds", []))
    _require(not (train_seeds & validation_seeds), "train/validation seeds overlap")
    _require(not (train_seeds & test_seeds), "train/test seeds overlap")
    _require(not (validation_seeds & test_seeds), "validation/test seeds overlap")

    reference = data.get("offline_label_reference", {})
    _require(reference.get("deployable") is False, "offline reference marked deployable")
    _require(reference.get("oracle") is False, "one-step reference marked oracle")
    _require(reference.get("globally_optimal") is False, "one-step reference marked global")
    _require(
        reference.get("optimization_horizon") == "one window",
        "offline reference horizon changed",
    )


def load_config(path: str | Path | None = None) -> LoadedConfig:
    config_path = Path(path) if path is not None else DEFAULT_CONFIG_PATH
    config_path = config_path.resolve()
    try:
        text = config_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ConfigError(f"cannot read config {config_path}: {exc}") from exc
    try:
        data = json.loads(
            text,
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_constant,
        )
    except json.JSONDecodeError as exc:
        raise ConfigError(f"invalid JSON in {config_path}: {exc}") from exc
    _require(isinstance(data, dict), "config root must be an object")
    validate_config(data)
    return LoadedConfig(path=config_path, sha256=sha256_file(config_path), data=data)

