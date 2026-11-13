"""Deterministic tabular Q-learning policy with partition-guarded updates."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

import numpy as np

from .isolation import DataUse, Partition, require_partition
from .state import ACTION_ORDER, Action, EncodedState


class PolicyStateError(RuntimeError):
    """Raised when a frozen policy is updated or an index is invalid."""


@dataclass(frozen=True)
class TabularUpdate:
    state_index: int
    action: Action
    reward: float
    next_state_index: int
    terminal: bool
    partition: Partition


class TabularQPolicy:
    algorithm_id = "Tabular-Q"

    def __init__(self, config: Mapping[str, Any], *, seed: int | None = None):
        settings = config["tabular_q"]
        training = config["training_and_selection"]
        self.alpha = float(settings["alpha"])
        self.gamma = float(settings["gamma"])
        self.episodes = int(settings["episodes"])
        self.epsilon_start = float(settings["epsilon_start"])
        self.epsilon_end = float(settings["epsilon_end"])
        self.state_count = int(config["online_state"]["discrete_state_cardinality"])
        self.action_count = len(ACTION_ORDER)
        self.q_values = np.full(
            (self.state_count, self.action_count),
            float(settings["q_initialization"]),
            dtype=np.float64,
        )
        self.seed = int(seed if seed is not None else training["policy_initialization_seed"])
        self.rng = np.random.default_rng(self.seed)
        self.frozen = False
        self.update_count = 0

    def epsilon_for_episode(self, episode: int) -> float:
        if not 0 <= episode < self.episodes:
            raise PolicyStateError(f"episode must be in [0,{self.episodes - 1}]")
        if self.episodes == 1:
            return self.epsilon_end
        fraction = episode / (self.episodes - 1)
        return self.epsilon_start + fraction * (self.epsilon_end - self.epsilon_start)

    def _state_index(self, state: int | EncodedState) -> int:
        index = state.index if isinstance(state, EncodedState) else int(state)
        if not 0 <= index < self.state_count:
            raise PolicyStateError(f"state index out of range: {index}")
        return index

    def select_action(
        self,
        state: int | EncodedState,
        *,
        training: bool = False,
        episode: int | None = None,
    ) -> Action:
        index = self._state_index(state)
        if training:
            if self.frozen:
                raise PolicyStateError("frozen Tabular-Q policy cannot explore")
            if episode is None:
                raise PolicyStateError("training selection requires an episode index")
            epsilon = self.epsilon_for_episode(episode)
            if self.rng.random() < epsilon:
                return ACTION_ORDER[int(self.rng.integers(self.action_count))]
        # np.argmax returns the first maximum, preserving the configured tie break.
        return ACTION_ORDER[int(np.argmax(self.q_values[index]))]

    def update(self, transition: TabularUpdate) -> float:
        if self.frozen:
            raise PolicyStateError("frozen Tabular-Q policy cannot be updated")
        require_partition(transition.partition, DataUse.POLICY_UPDATE)
        state = self._state_index(transition.state_index)
        next_state = self._state_index(transition.next_state_index)
        action_index = ACTION_ORDER.index(Action.parse(transition.action))
        current = self.q_values[state, action_index]
        bootstrap = 0.0 if transition.terminal else float(np.max(self.q_values[next_state]))
        target = float(transition.reward) + self.gamma * bootstrap
        updated = current + self.alpha * (target - current)
        self.q_values[state, action_index] = updated
        self.update_count += 1
        return float(updated - current)

    def freeze(self) -> None:
        self.frozen = True

    def copy(self) -> "TabularQPolicy":
        duplicate = object.__new__(TabularQPolicy)
        duplicate.alpha = self.alpha
        duplicate.gamma = self.gamma
        duplicate.episodes = self.episodes
        duplicate.epsilon_start = self.epsilon_start
        duplicate.epsilon_end = self.epsilon_end
        duplicate.state_count = self.state_count
        duplicate.action_count = self.action_count
        duplicate.q_values = self.q_values.copy()
        duplicate.seed = self.seed
        duplicate.rng = np.random.default_rng(self.seed)
        duplicate.frozen = self.frozen
        duplicate.update_count = self.update_count
        return duplicate

