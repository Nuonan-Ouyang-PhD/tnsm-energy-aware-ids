"""CPU-deterministic DQN with a train-only replay buffer and frozen evaluation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import random
from typing import Any, Mapping

import numpy as np

from .isolation import DataUse, Partition, require_partition
from .state import ACTION_ORDER, Action, EncodedState
from .tabular_q import PolicyStateError

try:
    import torch
    from torch import nn
    from torch.nn import functional as F
except ImportError:  # pragma: no cover - exercised only on environments without torch
    torch = None
    nn = None
    F = None


class DQNUnavailable(RuntimeError):
    """Raised when DQN is requested without PyTorch."""


@dataclass(frozen=True)
class DQNTransition:
    state_index: int
    action: Action
    reward: float
    next_state_index: int
    terminal: bool
    partition: Partition


if nn is not None:

    class QNetwork(nn.Module):
        def __init__(self, state_count: int, hidden_layers: list[int], actions: int):
            super().__init__()
            widths = [state_count, *hidden_layers, actions]
            layers: list[nn.Module] = []
            for index, (left, right) in enumerate(zip(widths, widths[1:])):
                layers.append(nn.Linear(left, right))
                if index < len(widths) - 2:
                    layers.append(nn.ReLU())
            self.layers = nn.Sequential(*layers)

        def forward(self, inputs):
            return self.layers(inputs)


class DQNPolicy:
    algorithm_id = "DQN"

    def __init__(self, config: Mapping[str, Any], *, seed: int | None = None):
        if torch is None:
            raise DQNUnavailable("PyTorch is required for DQN")
        settings = config["dqn"]
        training = config["training_and_selection"]
        self.state_count = int(config["online_state"]["discrete_state_cardinality"])
        self.action_count = len(ACTION_ORDER)
        self.episodes = int(settings["episodes"])
        self.gamma = float(settings["gamma"])
        self.epsilon_start = float(settings["epsilon_start"])
        self.epsilon_end = float(settings["epsilon_end"])
        self.batch_size = int(settings["batch_size"])
        self.replay_capacity = int(settings["replay_capacity"])
        self.replay_warmup = int(settings["replay_warmup_transitions"])
        self.target_update_steps = int(settings["target_update_steps"])
        self.gradient_norm_clip = float(settings["gradient_norm_clip"])
        self.seed = int(seed if seed is not None else training["policy_initialization_seed"])
        self.device = torch.device(settings["device"])
        random.seed(self.seed)
        np.random.seed(self.seed)
        torch.manual_seed(self.seed)
        if settings["deterministic_algorithms"]:
            torch.use_deterministic_algorithms(True)
        hidden = [int(value) for value in settings["hidden_layers"]]
        self.online = QNetwork(self.state_count, hidden, self.action_count).to(self.device)
        self.target = QNetwork(self.state_count, hidden, self.action_count).to(self.device)
        self.target.load_state_dict(self.online.state_dict())
        self.target.eval()
        self.optimizer = torch.optim.Adam(
            self.online.parameters(), lr=float(settings["learning_rate"])
        )
        self.loss_function = nn.SmoothL1Loss()
        self.replay: deque[DQNTransition] = deque(maxlen=self.replay_capacity)
        self.rng = random.Random(self.seed)
        self.optimizer_steps = 0
        self.update_count = 0
        self.frozen = False

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

    def _one_hot(self, indices):
        return F.one_hot(indices, num_classes=self.state_count).to(torch.float32)

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
                raise PolicyStateError("frozen DQN cannot explore")
            if episode is None:
                raise PolicyStateError("training selection requires an episode index")
            if self.rng.random() < self.epsilon_for_episode(episode):
                return ACTION_ORDER[self.rng.randrange(self.action_count)]
        with torch.no_grad():
            encoded = self._one_hot(torch.tensor([index], device=self.device))
            # torch.argmax returns the first maximum, preserving the fixed tie break.
            action_index = int(torch.argmax(self.online(encoded), dim=1).item())
        return ACTION_ORDER[action_index]

    def observe(self, transition: DQNTransition) -> None:
        if self.frozen:
            raise PolicyStateError("frozen DQN cannot accept replay transitions")
        require_partition(transition.partition, DataUse.POLICY_UPDATE)
        self._state_index(transition.state_index)
        self._state_index(transition.next_state_index)
        Action.parse(transition.action)
        self.replay.append(transition)
        self.update_count += 1

    def optimize(self) -> float | None:
        if self.frozen:
            raise PolicyStateError("frozen DQN cannot optimize")
        required = max(self.batch_size, self.replay_warmup)
        if len(self.replay) < required:
            return None
        batch = self.rng.sample(list(self.replay), self.batch_size)
        states = torch.tensor([item.state_index for item in batch], device=self.device)
        actions = torch.tensor(
            [ACTION_ORDER.index(Action.parse(item.action)) for item in batch],
            dtype=torch.int64,
            device=self.device,
        )
        rewards = torch.tensor(
            [item.reward for item in batch], dtype=torch.float32, device=self.device
        )
        next_states = torch.tensor(
            [item.next_state_index for item in batch], device=self.device
        )
        nonterminal = torch.tensor(
            [not item.terminal for item in batch], dtype=torch.float32, device=self.device
        )
        predicted = self.online(self._one_hot(states)).gather(1, actions[:, None]).squeeze(1)
        with torch.no_grad():
            next_values = self.target(self._one_hot(next_states)).max(dim=1).values
            targets = rewards + self.gamma * nonterminal * next_values
        loss = self.loss_function(predicted, targets)
        self.optimizer.zero_grad(set_to_none=True)
        loss.backward()
        torch.nn.utils.clip_grad_norm_(self.online.parameters(), self.gradient_norm_clip)
        self.optimizer.step()
        self.optimizer_steps += 1
        if self.optimizer_steps % self.target_update_steps == 0:
            self.target.load_state_dict(self.online.state_dict())
        return float(loss.detach().cpu().item())

    def freeze(self) -> None:
        self.frozen = True
        self.online.eval()
        self.target.eval()
        self.replay.clear()

    def copy_online_state(self) -> dict[str, Any]:
        return {
            key: value.detach().cpu().clone()
            for key, value in self.online.state_dict().items()
        }

    def load_online_state(self, state_dict: Mapping[str, Any]) -> None:
        if self.frozen:
            raise PolicyStateError("cannot replace weights on a frozen DQN")
        self.online.load_state_dict(state_dict)
        self.target.load_state_dict(state_dict)

