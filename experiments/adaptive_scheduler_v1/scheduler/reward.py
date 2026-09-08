"""Fixed, label-aware training reward with explicit cost provenance."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import math
from typing import Any, Mapping, Sequence


class RewardError(ValueError):
    """Raised for malformed labels, predictions, or cost observations."""


class CostOrigin(str, Enum):
    MEASURED_CURRENT_WINDOW = "measured_current_window"
    TON_STATIC_PROFILE_LOOKUP_PROXY = "ton_static_profile_lookup_proxy"
    SYNTHETIC_UNIT_TEST = "synthetic_unit_test"

    @classmethod
    def parse(cls, value: str | "CostOrigin") -> "CostOrigin":
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:
            raise RewardError(f"unknown cost origin: {value!r}") from exc


def _finite(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise RewardError(f"{name} must be finite")
    return result


def _normalize(value: float, low: float, high: float) -> float:
    if not high > low:
        raise RewardError("normalization upper bound must exceed lower bound")
    return max(0.0, min(1.0, (value - low) / (high - low)))


def balanced_accuracy(labels: Sequence[int], predictions: Sequence[int]) -> float:
    """Mean recall over ground-truth classes present in this window."""

    if len(labels) != len(predictions) or not labels:
        raise RewardError("labels and predictions must have equal non-zero length")
    recalls: list[float] = []
    for target in sorted(set(int(value) for value in labels)):
        if target not in (0, 1):
            raise RewardError("binary labels must be 0 or 1")
        positions = [index for index, value in enumerate(labels) if int(value) == target]
        correct = sum(int(predictions[index]) == target for index in positions)
        recalls.append(correct / len(positions))
    if any(int(value) not in (0, 1) for value in predictions):
        raise RewardError("binary predictions must be 0 or 1")
    return sum(recalls) / len(recalls)


@dataclass(frozen=True)
class CostObservation:
    power_watts: float
    latency_batch_ms: float
    post_temperature_c: float
    origin: CostOrigin
    latency_origin: str
    temperature_origin: str

    def validate(self) -> None:
        power = _finite(self.power_watts, "power_watts")
        latency = _finite(self.latency_batch_ms, "latency_batch_ms")
        _finite(self.post_temperature_c, "post_temperature_c")
        if power <= 0.0:
            raise RewardError("power_watts must be positive")
        if latency < 0.0:
            raise RewardError("latency_batch_ms must be non-negative")
        CostOrigin.parse(self.origin)
        if not self.latency_origin:
            raise RewardError("latency_origin is required")
        if not self.temperature_origin:
            raise RewardError("temperature_origin is required")


@dataclass(frozen=True)
class RewardComponents:
    detection: float
    power: float
    latency: float
    positive_thermal_increment: float
    scalar_reward: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


class RewardFunction:
    def __init__(self, config: Mapping[str, Any]):
        reward = config["reward"]
        self.weights = {key: float(value) for key, value in reward["weights"].items()}
        power = reward["power_component"]
        latency = reward["latency_component"]
        thermal = reward["thermal_component"]
        self.power_bounds = (float(power["lower_watts"]), float(power["upper_watts"]))
        self.latency_bounds = (
            float(latency["lower_batch_ms"]),
            float(latency["upper_batch_ms"]),
        )
        self.thermal_scale_c = float(thermal["positive_increment_scale_c"])
        self.allowed_cost_origins = {
            CostOrigin.parse(value) for value in power["allowed_origins"]
        }

    def calculate(
        self,
        *,
        labels: Sequence[int],
        attack_probabilities: Sequence[float],
        predecision_smoothed_temperature_c: float,
        cost: CostObservation,
        prediction_threshold: float = 0.5,
    ) -> RewardComponents:
        cost.validate()
        if CostOrigin.parse(cost.origin) not in self.allowed_cost_origins:
            raise RewardError(f"cost origin is not enabled: {cost.origin.value}")
        if len(labels) != len(attack_probabilities) or not labels:
            raise RewardError("labels and attack probabilities must align and be non-empty")
        probabilities = [
            _finite(value, "attack_probability") for value in attack_probabilities
        ]
        if any(value < 0.0 or value > 1.0 for value in probabilities):
            raise RewardError("attack probabilities must be in [0,1]")
        threshold = _finite(prediction_threshold, "prediction_threshold")
        if not 0.0 <= threshold <= 1.0:
            raise RewardError("prediction_threshold must be in [0,1]")
        predictions = [int(value >= threshold) for value in probabilities]
        detection = balanced_accuracy(labels, predictions)
        power = _normalize(cost.power_watts, *self.power_bounds)
        latency = _normalize(cost.latency_batch_ms, *self.latency_bounds)
        pre_temperature = _finite(
            predecision_smoothed_temperature_c, "predecision_smoothed_temperature_c"
        )
        positive_increment = max(0.0, cost.post_temperature_c - pre_temperature)
        thermal = max(0.0, min(1.0, positive_increment / self.thermal_scale_c))
        scalar = (
            self.weights["detection"] * detection
            - self.weights["power"] * power
            - self.weights["latency"] * latency
            - self.weights["positive_thermal_increment"] * thermal
        )
        return RewardComponents(detection, power, latency, thermal, scalar)

