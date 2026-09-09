"""Append-only causal per-window event logging."""

from __future__ import annotations

from hashlib import sha256
import json
import math
import os
from pathlib import Path
from typing import Any, Mapping, Sequence

import numpy as np

from .reward import RewardComponents
from .state import Action, EncodedState, OnlineState
from .trace_io import ActionOutcome


class WindowLogError(ValueError):
    pass


def probability_digest(values: Sequence[float]) -> str:
    array = np.asarray(values, dtype="<f4")
    return sha256(np.ascontiguousarray(array).tobytes()).hexdigest()


def _reject_nonfinite(value: object) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise WindowLogError("JSONL event contains a non-finite float")
    if isinstance(value, dict):
        for child in value.values():
            _reject_nonfinite(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _reject_nonfinite(child)


class JsonlWindowLogger:
    """Write one complete JSON object per append, retaining partial logs on failure."""

    def __init__(self, path: str | Path, *, config_id: str, config_sha256: str):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.config_id = config_id
        self.config_sha256 = config_sha256

    def append(self, event: Mapping[str, Any]) -> None:
        record = {
            "schema_version": 1,
            "config_id": self.config_id,
            "config_sha256": self.config_sha256,
            **dict(event),
        }
        _reject_nonfinite(record)
        encoded = (
            json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
        ).encode("utf-8")
        descriptor = os.open(
            self.path,
            os.O_WRONLY | os.O_CREAT | os.O_APPEND,
            0o644,
        )
        try:
            os.write(descriptor, encoded)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)

    def decision(
        self,
        *,
        run_id: str,
        method: str,
        trace_id: str,
        dataset: str,
        partition: str,
        state: OnlineState,
        encoded_state: EncodedState,
        selected_action: Action,
        decision_detail: Mapping[str, Any],
        policy_artifact_sha256: str | None,
    ) -> None:
        self.append(
            {
                "event_type": "window_decision",
                "run_id": run_id,
                "method": method,
                "trace_id": trace_id,
                "dataset": dataset,
                "partition": partition,
                "window_index": state.window_index,
                "decision_available_state": state.as_log_dict(),
                "encoded_state": encoded_state.as_log_dict(),
                "selected_action": selected_action.value,
                "switched": selected_action is not state.previous_action,
                "decision_detail": dict(decision_detail),
                "policy_artifact_sha256": policy_artifact_sha256,
                "labels_accessed_before_action": False,
                "current_counterfactual_predictions_accessed_before_action": False,
            }
        )

    def outcome(
        self,
        *,
        run_id: str,
        method: str,
        trace_id: str,
        dataset: str,
        partition: str,
        window_index: int,
        outcome: ActionOutcome,
        reward: RewardComponents | None,
    ) -> None:
        probabilities = np.asarray(outcome.attack_probabilities, dtype=np.float32)
        thresholded = probabilities >= 0.5
        self.append(
            {
                "event_type": "window_outcome",
                "run_id": run_id,
                "method": method,
                "trace_id": trace_id,
                "dataset": dataset,
                "partition": partition,
                "window_index": window_index,
                "selected_action": outcome.action.value,
                "prediction_count": int(len(probabilities)),
                "predicted_attack_count": int(np.count_nonzero(thresholded)),
                "attack_probability_mean": float(np.mean(probabilities)),
                "attack_probability_float32_sha256": probability_digest(probabilities),
                "probability_source": outcome.probability_source,
                "power_watts": outcome.cost.power_watts,
                "power_origin": outcome.cost.origin.value,
                "latency_batch_ms": outcome.cost.latency_batch_ms,
                "latency_origin": outcome.cost.latency_origin,
                "post_temperature_c": outcome.cost.post_temperature_c,
                "temperature_origin": outcome.cost.temperature_origin,
                "online_observation_origin": outcome.online_observation_origin,
                "reward_components": reward.as_dict() if reward is not None else None,
                "test_labels_accessed_online": False,
            }
        )

    def posthoc(
        self,
        *,
        run_id: str,
        method: str,
        trace_id: str,
        dataset: str,
        partition: str,
        window_index: int,
        metrics: Mapping[str, Any],
    ) -> None:
        self.append(
            {
                "event_type": "window_posthoc",
                "run_id": run_id,
                "method": method,
                "trace_id": trace_id,
                "dataset": dataset,
                "partition": partition,
                "window_index": window_index,
                "policy_frozen_before_schedule": True,
                "labels_loaded_after_complete_schedule": True,
                "metrics": dict(metrics),
            }
        )

