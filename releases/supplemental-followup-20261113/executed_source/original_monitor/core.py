"""Shared causal observation and objective for the supplemental pilot.

No temperature feedback is fabricated. These functions do not touch hardware.
"""
from dataclasses import dataclass
import math


ACTIONS = ("TinyDT", "LightLR", "MedRF", "HeavyMLP")
STATE_COUNT = 3 * 3 * 3 * 4


@dataclass(frozen=True)
class Observation:
    arrivals_now: int
    carryover_before_arrivals: int
    previous_threat: float
    previous_action: int

    def __post_init__(self):
        if self.arrivals_now < 0 or self.carryover_before_arrivals < 0:
            raise ValueError("negative row count")
        if not 0 <= self.previous_threat <= 1 or not 0 <= self.previous_action < 4:
            raise ValueError("invalid causal context")

    @property
    def work_rows(self):
        return self.arrivals_now + self.carryover_before_arrivals

    @property
    def index(self):
        # Counts, not fictitious buffer utilization. Empty backlog stays bin 0
        # even when a new 100-row batch has just arrived.
        arrival = 0 if self.arrivals_now <= 50 else 1 if self.arrivals_now <= 100 else 2
        backlog = 0 if self.carryover_before_arrivals == 0 else 1 if self.carryover_before_arrivals <= 100 else 2
        threat = 0 if self.previous_threat < 1 / 3 else 1 if self.previous_threat < 0.7 else 2
        return ((arrival * 3 + backlog) * 3 + threat) * 4 + self.previous_action


def deadline_guard(observation, medrf_batch_p95_seconds):
    if not math.isfinite(medrf_batch_p95_seconds) or medrf_batch_p95_seconds <= 0:
        raise ValueError("invalid latency profile")
    demand = math.ceil(observation.work_rows / 100) * medrf_batch_p95_seconds
    return 2 if demand <= 1.0 else 1


def reward(*, balanced_accuracy, normalized_power, completion_seconds, backlog_rows, work_rows):
    """Pilot objective, frozen before its first training/validation execution.

    Retain the original nonthermal coefficients. Add an explicit deadline
    penalty and unfinished-row fraction. The base score is in [-.4,.5],
    so the unit deadline penalty exceeds its entire one-window range.
    This is not a claim of long-horizon constrained optimality.
    """
    if not 0 <= balanced_accuracy <= 1 or not 0 <= normalized_power <= 1:
        raise ValueError("invalid normalized score")
    if not math.isfinite(completion_seconds) or completion_seconds < 0:
        raise ValueError("invalid completion time")
    if not 0 <= backlog_rows <= work_rows:
        raise ValueError("invalid backlog")
    missed = completion_seconds > 1.0 or backlog_rows > 0
    pending_fraction = backlog_rows / work_rows if work_rows else 0.0
    components = {
        "detection": 0.5 * balanced_accuracy,
        "power": -0.2 * normalized_power,
        "completion": -0.2 * min(completion_seconds, 1.0),
        "deadline": -float(missed),
        "backlog": -pending_fraction,
    }
    return sum(components.values()), components


def external_busy_fraction(*, total_ticks, idle_ticks, allowed_process_ticks):
    """Unattributed busy CPU time; conservative, includes kernel/IRQ work.

    Inputs must be interval deltas, with allowed processes identified by PID
    AND starttime. A lifetime ps %CPU or load average is not accepted here.
    """
    if total_ticks <= 0 or not 0 <= idle_ticks <= total_ticks:
        raise ValueError("invalid CPU interval")
    if allowed_process_ticks < 0 or allowed_process_ticks > total_ticks:
        raise ValueError("invalid allowed-process CPU interval")
    return max(0, total_ticks - idle_ticks - allowed_process_ticks) / total_ticks
