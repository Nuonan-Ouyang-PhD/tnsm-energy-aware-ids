"""Frozen online evaluation followed by an optional separate test-label pass."""

from __future__ import annotations

from dataclasses import dataclass
from statistics import mean
from typing import Any, Mapping, Sequence

import numpy as np

from .cfsm import CFSMScheduler
from .dqn import DQNPolicy
from .isolation import DataUse, Partition, require_partition
from .metrics import binary_metrics
from .state import Action, OnlineStateTracker, StateEncoder
from .tabular_q import TabularQPolicy
from .trace_io import NpzTraceEpisode
from .window_log import JsonlWindowLogger


@dataclass
class ScheduledEpisode:
    episode: NpzTraceEpisode
    actions: list[Action]
    selected_probabilities: list[np.ndarray]
    switches: int


def evaluate_online_episode(
    policy: TabularQPolicy | DQNPolicy | CFSMScheduler,
    episode: NpzTraceEpisode,
    *,
    config: Mapping[str, Any],
    config_id: str,
    config_sha256: str,
    run_id: str,
    logger: JsonlWindowLogger,
    policy_artifact_sha256: str | None,
) -> ScheduledEpisode:
    require_partition(episode.partition, DataUse.ONLINE_ACTION)
    if isinstance(policy, (TabularQPolicy, DQNPolicy)) and not policy.frozen:
        raise ValueError("software evaluation requires a frozen RL policy")
    if episode.partition is Partition.TEST and episode._labels is not None:
        raise ValueError("online test episode unexpectedly has labels loaded")
    tracker = OnlineStateTracker(config)
    encoder = StateEncoder(config)
    if isinstance(policy, CFSMScheduler):
        policy.reset()
        method = policy.algorithm_id
    else:
        method = policy.algorithm_id
    actions: list[Action] = []
    selected_probabilities: list[np.ndarray] = []
    switches = 0
    for window_index in range(episode.windows):
        state = tracker.begin_window(episode.pre_decision(window_index))
        encoded = encoder.encode(state)
        if isinstance(policy, CFSMScheduler):
            cfsm_decision = policy.select_action(state)
            action = cfsm_decision.selected_action
            detail = cfsm_decision.as_dict()
        else:
            action = policy.select_action(encoded, training=False)
            detail = {"mode": "frozen_greedy", "evaluation_updates": False}
        logger.decision(
            run_id=run_id,
            method=method,
            trace_id=episode.trace_id,
            dataset=episode.dataset,
            partition=episode.partition.value,
            state=state,
            encoded_state=encoded,
            selected_action=action,
            decision_detail=detail,
            policy_artifact_sha256=policy_artifact_sha256,
        )
        # The selected action is committed before this provider call.
        outcome = episode.outcome_for_action(window_index, action)
        logger.outcome(
            run_id=run_id,
            method=method,
            trace_id=episode.trace_id,
            dataset=episode.dataset,
            partition=episode.partition.value,
            window_index=window_index,
            outcome=outcome,
            reward=None,
        )
        switches += int(action is not state.previous_action)
        tracker.complete_window(
            window_index=window_index,
            selected_action=action,
            selected_attack_probabilities=outcome.attack_probabilities,
            arrivals_in_window=int(episode.arrivals[window_index]),
        )
        actions.append(action)
        selected_probabilities.append(np.asarray(outcome.attack_probabilities).copy())
    return ScheduledEpisode(episode, actions, selected_probabilities, switches)


def add_posthoc_test_metrics(
    scheduled: ScheduledEpisode,
    *,
    logger: JsonlWindowLogger,
    run_id: str,
    method: str,
) -> dict[str, Any]:
    labels = scheduled.episode.load_labels_posthoc(
        schedule_complete=True,
        policy_frozen=True,
    )
    all_labels: list[int] = []
    all_predictions: list[int] = []
    window_metrics = []
    for window_index, probabilities in enumerate(scheduled.selected_probabilities):
        row_slice = scheduled.episode._slice(window_index)
        truth = labels[row_slice].astype(int).tolist()
        predictions = (probabilities >= 0.5).astype(int).tolist()
        metrics = binary_metrics(truth, predictions)
        logger.posthoc(
            run_id=run_id,
            method=method,
            trace_id=scheduled.episode.trace_id,
            dataset=scheduled.episode.dataset,
            partition=scheduled.episode.partition.value,
            window_index=window_index,
            metrics=metrics,
        )
        all_labels.extend(truth)
        all_predictions.extend(predictions)
        window_metrics.append(metrics)
    aggregate = binary_metrics(all_labels, all_predictions)
    aggregate.update(
        {
            "trace_id": scheduled.episode.trace_id,
            "windows": scheduled.episode.windows,
            "switches": scheduled.switches,
            "mean_window_f1": mean(float(item["f1"]) for item in window_metrics),
            "labels_loaded_after_complete_schedule": True,
        }
    )
    return aggregate

