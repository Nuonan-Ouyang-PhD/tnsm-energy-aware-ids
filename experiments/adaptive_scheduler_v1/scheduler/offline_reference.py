"""Explicitly nondeployable, label-informed, one-window utility reference."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from .isolation import DataUse
from .reward import RewardComponents, RewardFunction
from .state import ACTION_ORDER, Action, OnlineState
from .trace_io import NpzTraceEpisode


@dataclass(frozen=True)
class OfflineReferenceDecision:
    action: Action
    reward: RewardComponents
    all_action_scalar_rewards: Mapping[str, float]


class LabelInformedPerWindowUtilityReference:
    """Maximize fixed utility independently per completed labeled window.

    This object is intentionally not a scheduler policy and cannot be frozen or
    exported as a deployable artifact. It has no look-ahead or trajectory model.
    """

    algorithm_id = "LI-PerWindow-Utility-Reference"
    display_name = "Label-Informed Per-Window Utility Reference"
    deployable = False
    oracle = False
    globally_optimal = False

    def __init__(self, config: Mapping[str, Any]):
        reference = config["offline_label_reference"]
        if reference["deployable"] or reference["oracle"] or reference["globally_optimal"]:
            raise ValueError("invalid one-window reference configuration")
        self.config = config
        self.reward = RewardFunction(config)
        self.threshold = float(config["actions"]["prediction_threshold"])

    def choose(
        self,
        *,
        episode: NpzTraceEpisode,
        state: OnlineState,
        window_index: int,
        policy_frozen: bool,
    ) -> OfflineReferenceDecision:
        labels = episode.labels_for_reward(
            window_index,
            DataUse.OFFLINE_LABEL_REFERENCE,
            policy_frozen=policy_frozen,
        )
        scores: dict[str, RewardComponents] = {}
        for action in ACTION_ORDER:
            outcome = episode.outcome_for_action(window_index, action)
            scores[action.value] = self.reward.calculate(
                labels=labels.tolist(),
                attack_probabilities=outcome.attack_probabilities.tolist(),
                predecision_smoothed_temperature_c=state.smoothed_temperature_c,
                cost=outcome.cost,
                prediction_threshold=self.threshold,
            )
        # max preserves ACTION_ORDER because dict insertion order is fixed.
        selected = max(ACTION_ORDER, key=lambda action: scores[action.value].scalar_reward)
        return OfflineReferenceDecision(
            action=selected,
            reward=scores[selected.value],
            all_action_scalar_rewards={
                action.value: scores[action.value].scalar_reward for action in ACTION_ORDER
            },
        )
