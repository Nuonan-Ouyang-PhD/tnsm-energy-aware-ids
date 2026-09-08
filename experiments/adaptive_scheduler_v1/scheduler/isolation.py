"""Partition and label-use guards for scheduler fitting and evaluation."""

from __future__ import annotations

from enum import Enum


class DataIsolationError(ValueError):
    """Raised when data are requested for a role they cannot legally serve."""


class Partition(str, Enum):
    TRAIN = "train"
    CALIBRATION = "calibration"
    VALIDATION = "validation"
    TEST = "test"

    @classmethod
    def parse(cls, value: str | "Partition") -> "Partition":
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:
            raise DataIsolationError(f"unknown partition: {value!r}") from exc


class DataUse(str, Enum):
    POLICY_UPDATE = "policy_update"
    EMPIRICAL_CALIBRATION = "empirical_calibration"
    CHECKPOINT_SELECTION = "checkpoint_selection"
    ONLINE_ACTION = "online_action"
    POSTHOC_METRICS = "posthoc_metrics"
    OFFLINE_LABEL_REFERENCE = "offline_label_reference"


def require_partition(
    partition: str | Partition,
    use: DataUse,
    *,
    policy_frozen: bool = False,
) -> Partition:
    """Authorize one narrowly defined use and return the normalized partition."""

    part = Partition.parse(partition)
    if use is DataUse.POLICY_UPDATE:
        allowed = {Partition.TRAIN}
    elif use is DataUse.EMPIRICAL_CALIBRATION:
        allowed = {Partition.CALIBRATION}
    elif use is DataUse.CHECKPOINT_SELECTION:
        allowed = {Partition.VALIDATION}
    elif use is DataUse.ONLINE_ACTION:
        allowed = set(Partition)
    elif use in {DataUse.POSTHOC_METRICS, DataUse.OFFLINE_LABEL_REFERENCE}:
        allowed = {Partition.VALIDATION, Partition.TEST}
    else:  # pragma: no cover - defensive for future enum changes
        raise DataIsolationError(f"unsupported data use: {use}")

    if part not in allowed:
        raise DataIsolationError(f"partition {part.value!r} cannot be used for {use.value!r}")
    if part is Partition.TEST and use in {
        DataUse.POSTHOC_METRICS,
        DataUse.OFFLINE_LABEL_REFERENCE,
    } and not policy_frozen:
        raise DataIsolationError("test labels require a completed frozen schedule")
    return part


FORBIDDEN_ONLINE_KEYS = frozenset(
    {
        "label",
        "labels",
        "y",
        "y_true",
        "ground_truth",
        "phase",
        "phase_id",
        "stage",
        "stage_id",
        "future_state",
        "future_temperature",
    }
)


def assert_no_forbidden_online_keys(value: object, *, path: str = "$") -> None:
    """Reject labels, phase identifiers, and future data in an online-state object."""

    if isinstance(value, dict):
        for key, child in value.items():
            normalized = str(key).strip().lower()
            if normalized in FORBIDDEN_ONLINE_KEYS:
                raise DataIsolationError(f"forbidden online key at {path}.{key}: {key!r}")
            assert_no_forbidden_online_keys(child, path=f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            assert_no_forbidden_online_keys(child, path=f"{path}[{index}]")

