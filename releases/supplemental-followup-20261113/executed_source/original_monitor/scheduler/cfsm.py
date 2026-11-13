"""Fixed conditional finite-state mechanism (CFSM) baseline."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from .state import ACTION_ORDER, ACTION_TO_INDEX, Action, OnlineState, StateError


@dataclass(frozen=True)
class CFSMDecision:
    selected_action: Action
    previous_action: Action
    reason: str
    switched: bool
    cooldown_before: int
    cooldown_after: int

    def as_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["selected_action"] = self.selected_action.value
        result["previous_action"] = self.previous_action.value
        return result


class CFSMScheduler:
    """Implement the complete fixed rule order and exact two-window cooldown."""

    algorithm_id = "CFSM"

    def __init__(self, config: Mapping[str, Any]):
        rules = config["cfsm"]
        if rules["learned"] is not False:
            raise ValueError("CFSM cannot be trained")
        self.temperature_warning_c = float(rules["temperature_warning_c"])
        self.threat_threshold = float(rules["threat_threshold"])
        self.cooldown_windows = int(rules["cooldown_full_windows_after_switch"])
        self.initial_action = Action.parse(rules["initial_action"])
        self.reset()

    def reset(self) -> None:
        self.current_action = self.initial_action
        self.cooldown_remaining = 0

    @staticmethod
    def _lighter(action: Action) -> Action:
        return ACTION_ORDER[max(0, ACTION_TO_INDEX[action] - 1)]

    @staticmethod
    def _heavier(action: Action) -> Action:
        return ACTION_ORDER[min(len(ACTION_ORDER) - 1, ACTION_TO_INDEX[action] + 1)]

    def select_action(self, state: OnlineState) -> CFSMDecision:
        if state.previous_action is not self.current_action:
            raise StateError(
                "CFSM internal action does not match the causal state's previous action"
            )
        before = self.cooldown_remaining
        previous = self.current_action

        if state.smoothed_temperature_c >= self.temperature_warning_c:
            selected = self._lighter(previous)
            reason = "thermal_safety_step_lighter" if selected is not previous else "thermal_at_lightest_hold"
            if selected is not previous:
                self.cooldown_remaining = self.cooldown_windows
            elif self.cooldown_remaining:
                self.cooldown_remaining -= 1
        elif self.cooldown_remaining > 0:
            selected = previous
            reason = "cooldown_hold"
            self.cooldown_remaining -= 1
        elif state.lagged_selected_model_threat < self.threat_threshold:
            selected = self._lighter(previous)
            reason = "low_threat_step_lighter" if selected is not previous else "low_threat_at_lightest_hold"
            if selected is not previous:
                self.cooldown_remaining = self.cooldown_windows
        else:
            selected = self._heavier(previous)
            reason = "high_threat_step_heavier" if selected is not previous else "high_threat_at_heaviest_hold"
            if selected is not previous:
                self.cooldown_remaining = self.cooldown_windows

        switched = selected is not previous
        self.current_action = selected
        return CFSMDecision(
            selected_action=selected,
            previous_action=previous,
            reason=reason,
            switched=switched,
            cooldown_before=before,
            cooldown_after=self.cooldown_remaining,
        )

