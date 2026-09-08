"""Train and validation-select Tabular-Q or DQN without test-data access."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from statistics import mean
from typing import Any, Mapping, Sequence

from .dqn import DQNPolicy, DQNTransition
from .isolation import DataUse, Partition
from .reward import RewardFunction
from .state import ACTION_ORDER, OnlineStateTracker, StateEncoder
from .tabular_q import TabularQPolicy, TabularUpdate
from .trace_io import NpzTraceEpisode


@dataclass(frozen=True)
class EpisodeMetrics:
    trace_id: str
    windows: int
    episode_return: float
    mean_detection: float
    mean_power_component: float
    mean_latency_component: float
    mean_thermal_component: float
    switches: int

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def run_labeled_episode(
    policy: TabularQPolicy | DQNPolicy,
    episode: NpzTraceEpisode,
    *,
    config: Mapping[str, Any],
    training_episode_index: int | None,
) -> EpisodeMetrics:
    is_training = training_episode_index is not None
    expected = Partition.TRAIN if is_training else Partition.VALIDATION
    if episode.partition is not expected:
        raise ValueError(f"expected {expected.value} episode, got {episode.partition.value}")
    label_use = DataUse.POLICY_UPDATE if is_training else DataUse.CHECKPOINT_SELECTION
    tracker = OnlineStateTracker(config)
    encoder = StateEncoder(config)
    reward_function = RewardFunction(config)
    rewards = []
    detections = []
    powers = []
    latencies = []
    thermals = []
    switches = 0
    state = tracker.begin_window(episode.pre_decision(0))
    encoded = encoder.encode(state)
    for window_index in range(episode.windows):
        action = policy.select_action(
            encoded,
            training=is_training,
            episode=training_episode_index,
        )
        outcome = episode.outcome_for_action(window_index, action)
        labels = episode.labels_for_reward(window_index, label_use)
        components = reward_function.calculate(
            labels=labels.tolist(),
            attack_probabilities=outcome.attack_probabilities.tolist(),
            predecision_smoothed_temperature_c=state.smoothed_temperature_c,
            cost=outcome.cost,
            prediction_threshold=float(config["actions"]["prediction_threshold"]),
        )
        switches += int(action is not state.previous_action)
        tracker.complete_window(
            window_index=window_index,
            selected_action=action,
            selected_attack_probabilities=outcome.attack_probabilities,
            arrivals_in_window=int(episode.arrivals[window_index]),
        )
        terminal = window_index == episode.windows - 1
        if terminal:
            next_encoded = encoded
        else:
            next_state = tracker.begin_window(episode.pre_decision(window_index + 1))
            next_encoded = encoder.encode(next_state)
        if is_training:
            if isinstance(policy, TabularQPolicy):
                policy.update(
                    TabularUpdate(
                        state_index=encoded.index,
                        action=action,
                        reward=components.scalar_reward,
                        next_state_index=next_encoded.index,
                        terminal=terminal,
                        partition=Partition.TRAIN,
                    )
                )
            else:
                policy.observe(
                    DQNTransition(
                        state_index=encoded.index,
                        action=action,
                        reward=components.scalar_reward,
                        next_state_index=next_encoded.index,
                        terminal=terminal,
                        partition=Partition.TRAIN,
                    )
                )
                policy.optimize()
        rewards.append(components.scalar_reward)
        detections.append(components.detection)
        powers.append(components.power)
        latencies.append(components.latency)
        thermals.append(components.positive_thermal_increment)
        if not terminal:
            state = next_state
            encoded = next_encoded
    return EpisodeMetrics(
        trace_id=episode.trace_id,
        windows=episode.windows,
        episode_return=sum(rewards),
        mean_detection=mean(detections),
        mean_power_component=mean(powers),
        mean_latency_component=mean(latencies),
        mean_thermal_component=mean(thermals),
        switches=switches,
    )


def aggregate_validation(metrics: Sequence[EpisodeMetrics], episode_index: int) -> dict[str, Any]:
    return {
        "training_episode": episode_index,
        "validation_traces": len(metrics),
        "mean_validation_episode_return": mean(item.episode_return for item in metrics),
        "mean_validation_balanced_accuracy": mean(item.mean_detection for item in metrics),
        "mean_validation_power_component": mean(item.mean_power_component for item in metrics),
        "mean_validation_latency_component": mean(item.mean_latency_component for item in metrics),
        "mean_validation_thermal_component": mean(item.mean_thermal_component for item in metrics),
        "total_validation_switches": sum(item.switches for item in metrics),
    }


def _selection_rank(summary: Mapping[str, Any]) -> tuple[float, float, float, float, float, float]:
    return (
        float(summary["mean_validation_episode_return"]),
        float(summary["mean_validation_balanced_accuracy"]),
        -float(summary["mean_validation_power_component"]),
        -float(summary["mean_validation_latency_component"]),
        -float(summary["total_validation_switches"]),
        -float(summary["training_episode"]),
    )


def train_and_select(
    policy: TabularQPolicy | DQNPolicy,
    *,
    train_episodes: Sequence[NpzTraceEpisode],
    validation_episodes: Sequence[NpzTraceEpisode],
    config: Mapping[str, Any],
    progress_path: str | Path,
) -> tuple[TabularQPolicy | DQNPolicy, dict[str, Any]]:
    if not train_episodes or not validation_episodes:
        raise ValueError("both train and validation traces are required")
    total_episodes = int(
        config["tabular_q" if isinstance(policy, TabularQPolicy) else "dqn"]["episodes"]
    )
    checkpoint_interval = int(config["training_and_selection"]["checkpoint_interval_episodes"])
    progress = Path(progress_path)
    progress.parent.mkdir(parents=True, exist_ok=True)
    if progress.exists():
        raise FileExistsError(f"refusing to overwrite training log {progress}")
    best_rank = None
    best_payload = None
    best_summary = None
    with progress.open("x", encoding="utf-8") as handle:
        for episode_index in range(total_episodes):
            source_episode = train_episodes[episode_index % len(train_episodes)]
            training_metrics = run_labeled_episode(
                policy,
                source_episode,
                config=config,
                training_episode_index=episode_index,
            )
            event: dict[str, Any] = {
                "event": "training_episode",
                "episode": episode_index,
                "source_trace": source_episode.trace_id,
                "epsilon": policy.epsilon_for_episode(episode_index),
                "metrics": training_metrics.as_dict(),
            }
            should_validate = (
                (episode_index + 1) % checkpoint_interval == 0
                or episode_index == total_episodes - 1
            )
            if should_validate:
                validation_metrics = [
                    run_labeled_episode(
                        policy,
                        validation_episode,
                        config=config,
                        training_episode_index=None,
                    )
                    for validation_episode in validation_episodes
                ]
                summary = aggregate_validation(validation_metrics, episode_index)
                event["validation"] = summary
                rank = _selection_rank(summary)
                if best_rank is None or rank > best_rank:
                    best_rank = rank
                    best_summary = summary
                    best_payload = (
                        policy.q_values.copy()
                        if isinstance(policy, TabularQPolicy)
                        else policy.copy_online_state()
                    )
            handle.write(json.dumps(event, sort_keys=True, allow_nan=False) + "\n")
            handle.flush()
    if best_payload is None or best_summary is None:  # pragma: no cover
        raise RuntimeError("no validation checkpoint was selected")
    if isinstance(policy, TabularQPolicy):
        policy.q_values[:] = best_payload
    else:
        policy.load_online_state(best_payload)
    metadata = {
        "episodes": total_episodes,
        "train_trace_sha256": {item.path.name: item.sha256 for item in train_episodes},
        "validation_trace_sha256": {
            item.path.name: item.sha256 for item in validation_episodes
        },
        "selection": best_summary,
        "selection_criterion": config["training_and_selection"]["selection_primary"],
        "test_data_accessed": False,
    }
    return policy, metadata

