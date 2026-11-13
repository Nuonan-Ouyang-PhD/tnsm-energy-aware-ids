"""Causal online state tracking and the fixed 324-state encoding."""

from __future__ import annotations

from bisect import bisect_right
from dataclasses import asdict, dataclass
from enum import Enum
import math
from typing import Any, Iterable, Mapping


class StateError(ValueError):
    """Raised on non-causal, non-finite, or out-of-order state observations."""


class Action(str, Enum):
    TINY_DT = "TinyDT"
    LIGHT_LR = "LightLR"
    MED_RF = "MedRF"
    HEAVY_MLP = "HeavyMLP"

    @classmethod
    def parse(cls, value: str | "Action") -> "Action":
        if isinstance(value, cls):
            return value
        try:
            return cls(value)
        except ValueError as exc:
            raise StateError(f"unknown action: {value!r}") from exc


ACTION_ORDER = (
    Action.TINY_DT,
    Action.LIGHT_LR,
    Action.MED_RF,
    Action.HEAVY_MLP,
)
ACTION_TO_INDEX = {action: index for index, action in enumerate(ACTION_ORDER)}


def _finite(value: float, name: str) -> float:
    result = float(value)
    if not math.isfinite(result):
        raise StateError(f"{name} must be finite")
    return result


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class PreDecisionObservation:
    window_index: int
    raw_temperature_c: float
    queue_depth_samples: int
    queue_capacity_samples: int
    observed_at_utc: str | None = None
    observed_at_monotonic_ns: int | None = None

    def validate(self) -> None:
        if self.window_index < 0:
            raise StateError("window_index must be non-negative")
        _finite(self.raw_temperature_c, "raw_temperature_c")
        if self.queue_depth_samples < 0:
            raise StateError("queue_depth_samples must be non-negative")
        if self.queue_capacity_samples <= 0:
            raise StateError("queue_capacity_samples must be positive")


@dataclass(frozen=True)
class OnlineState:
    window_index: int
    raw_temperature_c: float
    smoothed_temperature_c: float
    lagged_selected_model_threat: float
    predecision_queue_utilization: float
    lagged_arrival_rate_ratio: float
    previous_action: Action
    temperature_source_window: int
    threat_source_window: int | None
    queue_source_window: int
    load_source_window: int | None
    previous_action_source_window: int | None

    def as_log_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["previous_action"] = self.previous_action.value
        return result


@dataclass(frozen=True)
class EncodedState:
    index: int
    temperature_bin: int
    threat_bin: int
    queue_bin: int
    load_bin: int
    previous_action_index: int

    def as_log_dict(self) -> dict[str, int]:
        return asdict(self)


class StateEncoder:
    cardinality = 324

    def __init__(self, config: Mapping[str, Any]):
        state = config["online_state"]
        self.temperature_bins = tuple(state["temperature"]["bins_c_low_medium_high"])
        self.threat_bins = tuple(state["threat"]["bins_low_medium_high"])
        self.queue_bins = tuple(state["queue"]["bins_low_medium_high"])
        self.load_bins = tuple(state["network_load"]["bins_ratio_low_medium_high"])

    @staticmethod
    def _bin(value: float, boundaries: tuple[float, float]) -> int:
        return bisect_right(boundaries, value)

    def encode(self, state: OnlineState) -> EncodedState:
        t = self._bin(state.smoothed_temperature_c, self.temperature_bins)
        p = self._bin(state.lagged_selected_model_threat, self.threat_bins)
        q = self._bin(state.predecision_queue_utilization, self.queue_bins)
        load = self._bin(state.lagged_arrival_rate_ratio, self.load_bins)
        previous = ACTION_TO_INDEX[state.previous_action]
        index = ((((t * 3) + p) * 3 + q) * 3 + load) * 4 + previous
        if not 0 <= index < self.cardinality:  # pragma: no cover - arithmetic guard
            raise StateError(f"encoded state out of range: {index}")
        return EncodedState(index, t, p, q, load, previous)


class OnlineStateTracker:
    """Expose a window's selected-model outcome only to the following decision."""

    def __init__(self, config: Mapping[str, Any]):
        state = config["online_state"]
        self.smoothing_lambda = float(state["temperature"]["smoothing_lambda"])
        self.nominal_arrivals = int(config["experiment_scope"]["samples_per_window"])
        self.initial_threat = float(state["threat"]["first_window_value"])
        self.initial_load = float(state["network_load"]["first_window_ratio"])
        self.initial_action = Action.parse(state["previous_action"]["first_window_value"])
        self.reset()

    def reset(self) -> None:
        self._next_window = 0
        self._smoothed_temperature: float | None = None
        self._lagged_threat = self.initial_threat
        self._lagged_load = self.initial_load
        self._previous_action = self.initial_action
        self._pending_state: OnlineState | None = None

    @property
    def next_window_index(self) -> int:
        return self._next_window

    @property
    def has_pending_action(self) -> bool:
        return self._pending_state is not None

    def begin_window(self, observation: PreDecisionObservation) -> OnlineState:
        observation.validate()
        if self._pending_state is not None:
            raise StateError("previous window has no committed outcome")
        if observation.window_index != self._next_window:
            raise StateError(
                f"out-of-order window: expected {self._next_window}, "
                f"got {observation.window_index}"
            )
        raw_temperature = _finite(observation.raw_temperature_c, "raw_temperature_c")
        if self._smoothed_temperature is None:
            smoothed = raw_temperature
        else:
            smoothed = (
                self.smoothing_lambda * self._smoothed_temperature
                + (1.0 - self.smoothing_lambda) * raw_temperature
            )
        queue = _clip(
            observation.queue_depth_samples / observation.queue_capacity_samples,
            0.0,
            1.0,
        )
        previous_index = observation.window_index - 1 if observation.window_index else None
        state = OnlineState(
            window_index=observation.window_index,
            raw_temperature_c=raw_temperature,
            smoothed_temperature_c=smoothed,
            lagged_selected_model_threat=self._lagged_threat,
            predecision_queue_utilization=queue,
            lagged_arrival_rate_ratio=self._lagged_load,
            previous_action=self._previous_action,
            temperature_source_window=observation.window_index,
            threat_source_window=previous_index,
            queue_source_window=observation.window_index,
            load_source_window=previous_index,
            previous_action_source_window=previous_index,
        )
        self._smoothed_temperature = smoothed
        self._pending_state = state
        return state

    def complete_window(
        self,
        *,
        window_index: int,
        selected_action: str | Action,
        selected_attack_probabilities: Iterable[float],
        arrivals_in_window: int,
    ) -> None:
        if self._pending_state is None:
            raise StateError("cannot complete a window before its decision state")
        if window_index != self._pending_state.window_index:
            raise StateError(
                f"outcome window {window_index} does not match pending "
                f"window {self._pending_state.window_index}"
            )
        probabilities = [
            _finite(value, "selected_attack_probability")
            for value in selected_attack_probabilities
        ]
        if not probabilities:
            raise StateError("selected model must produce at least one probability")
        if any(value < 0.0 or value > 1.0 for value in probabilities):
            raise StateError("selected attack probabilities must be in [0,1]")
        if arrivals_in_window < 0:
            raise StateError("arrivals_in_window must be non-negative")
        self._lagged_threat = sum(probabilities) / len(probabilities)
        self._lagged_load = _clip(arrivals_in_window / self.nominal_arrivals, 0.0, 2.0)
        self._previous_action = Action.parse(selected_action)
        self._pending_state = None
        self._next_window += 1

