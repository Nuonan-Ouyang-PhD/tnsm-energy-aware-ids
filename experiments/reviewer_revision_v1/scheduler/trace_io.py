"""Strict adapter for compact train/validation/test policy-trace NPZ files."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path
import re
from typing import Any, Mapping, Sequence

import numpy as np

from .isolation import DataIsolationError, DataUse, Partition, require_partition
from .reward import CostObservation, CostOrigin
from .state import ACTION_ORDER, Action, PreDecisionObservation


class TraceFormatError(ValueError):
    """Raised when an input trace fails identity, shape, or isolation checks."""


TRACE_NAME = re.compile(r"^(train|calibration|validation|test)_drift_([0-9]+)\.npz$")


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ActionOutcome:
    action: Action
    attack_probabilities: np.ndarray
    cost: CostObservation
    probability_source: str
    online_observation_origin: str


class NpzTraceEpisode:
    """One immutable trace; test labels remain unopened until an explicit posthoc call."""

    def __init__(
        self,
        *,
        path: Path,
        partition: Partition,
        seed: int,
        digest: str,
        dataset: str,
        probabilities: np.ndarray,
        labels: np.ndarray | None,
        temperatures: np.ndarray,
        queue_depths: np.ndarray,
        queue_capacities: np.ndarray,
        arrivals: np.ndarray,
        samples_per_window: int,
        config: Mapping[str, Any],
        online_observation_origin: str,
    ):
        self.path = path
        self.partition = partition
        self.seed = seed
        self.sha256 = digest
        self.dataset = dataset
        self.trace_id = f"{dataset}-{partition.value}-drift-{seed}"
        self.probabilities = probabilities
        self._labels = labels
        self.temperatures = temperatures
        self.queue_depths = queue_depths
        self.queue_capacities = queue_capacities
        self.arrivals = arrivals
        self.samples_per_window = samples_per_window
        self.windows = len(temperatures)
        self.config = config
        self.online_observation_origin = online_observation_origin

    def _slice(self, window_index: int) -> slice:
        if not 0 <= window_index < self.windows:
            raise TraceFormatError(f"window out of range: {window_index}")
        start = window_index * self.samples_per_window
        return slice(start, start + self.samples_per_window)

    def pre_decision(self, window_index: int) -> PreDecisionObservation:
        self._slice(window_index)
        return PreDecisionObservation(
            window_index=window_index,
            raw_temperature_c=float(self.temperatures[window_index]),
            queue_depth_samples=int(self.queue_depths[window_index]),
            queue_capacity_samples=int(self.queue_capacities[window_index]),
        )

    def outcome_for_action(self, window_index: int, action: str | Action) -> ActionOutcome:
        """Reveal only the selected action's outcome after action commitment."""

        selected = Action.parse(action)
        column = ACTION_ORDER.index(selected)
        probabilities = self.probabilities[self._slice(window_index), column]
        registry = self.config["resource_cost_registry"]["models"][selected.value]
        cost = CostObservation(
            power_watts=float(registry["mean_watts"]),
            latency_batch_ms=float(registry["mean_batch_latency_ms_median"]),
            post_temperature_c=float(self.temperatures[window_index]),
            origin=CostOrigin.TON_STATIC_PROFILE_LOOKUP_PROXY,
            latency_origin="TON scheduled-static-profile mean of per-run medians",
            temperature_origin=self.online_observation_origin,
        )
        return ActionOutcome(
            action=selected,
            attack_probabilities=probabilities,
            cost=cost,
            probability_source=(
                f"{self.path}#model_probabilities[window={window_index},"
                f"model={selected.value}]"
            ),
            online_observation_origin=self.online_observation_origin,
        )

    def labels_for_reward(
        self,
        window_index: int,
        use: DataUse,
        *,
        policy_frozen: bool = False,
    ) -> np.ndarray:
        if self._labels is None:
            raise DataIsolationError("labels were not loaded into this online trace")
        require_partition(self.partition, use, policy_frozen=policy_frozen)
        return self._labels[self._slice(window_index)]

    def load_labels_posthoc(self, *, schedule_complete: bool, policy_frozen: bool) -> np.ndarray:
        """Open test labels only after a complete frozen schedule has been produced."""

        if not schedule_complete:
            raise DataIsolationError("cannot open test labels before schedule completion")
        require_partition(
            self.partition,
            DataUse.POSTHOC_METRICS,
            policy_frozen=policy_frozen,
        )
        with np.load(self.path, allow_pickle=False) as archive:
            if "labels" not in archive.files:
                raise TraceFormatError(f"test label member missing: {self.path}")
            labels = np.asarray(archive["labels"], dtype=np.int8)
        expected = self.windows * self.samples_per_window
        if labels.shape != (expected,) or not np.isin(labels, [0, 1]).all():
            raise TraceFormatError("posthoc labels are not aligned binary rows")
        return labels


def _window_array(
    archive: Any,
    member: str,
    *,
    windows: int,
    default: float | int,
    dtype: Any,
) -> tuple[np.ndarray, bool]:
    if member not in archive.files:
        return np.full(windows, default, dtype=dtype), False
    values = np.asarray(archive[member], dtype=dtype)
    if values.ndim == 0:
        values = np.full(windows, values.item(), dtype=dtype)
    if values.shape != (windows,):
        raise TraceFormatError(f"{member} must be scalar or have one value per window")
    return values, True


def load_npz_episode(
    path: str | Path,
    *,
    partition: str | Partition,
    config: Mapping[str, Any],
    expected_sha256: str | None,
    load_labels: bool,
    allow_posthoc_test_labels: bool = False,
) -> NpzTraceEpisode:
    trace_path = Path(path).resolve()
    part = Partition.parse(partition)
    match = TRACE_NAME.fullmatch(trace_path.name)
    if match is None:
        raise TraceFormatError(f"unexpected trace filename: {trace_path.name}")
    if match.group(1) != part.value:
        raise DataIsolationError(
            f"filename partition {match.group(1)!r} does not match {part.value!r}"
        )
    seed = int(match.group(2))
    digest = file_sha256(trace_path)
    if expected_sha256 is not None and digest != expected_sha256:
        raise TraceFormatError(
            f"trace hash mismatch for {trace_path.name}: expected {expected_sha256}, got {digest}"
        )
    if part is Partition.TEST and load_labels and not allow_posthoc_test_labels:
        raise DataIsolationError("online test trace loading cannot request labels")
    adapter = config["software_trace_adapter"]
    expected_models = tuple(adapter["model_probability_order"])
    with np.load(trace_path, allow_pickle=False) as archive:
        required = {"model_probabilities", "models", "windows", "samples_per_window"}
        missing = required - set(archive.files)
        if missing:
            raise TraceFormatError(f"missing NPZ members in {trace_path.name}: {sorted(missing)}")
        models = tuple(str(value) for value in archive["models"].tolist())
        if models != expected_models:
            raise TraceFormatError(f"model order mismatch: {models!r}")
        windows = int(np.asarray(archive["windows"]).item())
        samples = int(np.asarray(archive["samples_per_window"]).item())
        if windows != int(adapter["windows_per_trace"]):
            raise TraceFormatError(f"unexpected window count: {windows}")
        if samples != int(adapter["samples_per_window"]):
            raise TraceFormatError(f"unexpected samples_per_window: {samples}")
        probabilities = np.asarray(archive["model_probabilities"], dtype=np.float32)
        expected_rows = windows * samples
        if probabilities.shape != (expected_rows, len(ACTION_ORDER)):
            raise TraceFormatError(f"unexpected probability shape: {probabilities.shape}")
        if not np.isfinite(probabilities).all() or np.any(probabilities < 0) or np.any(probabilities > 1):
            raise TraceFormatError("model probabilities must be finite values in [0,1]")
        labels = None
        if load_labels:
            if "labels" not in archive.files:
                raise TraceFormatError(f"labels missing from {trace_path.name}")
            labels = np.asarray(archive["labels"], dtype=np.int8)
            if labels.shape != (expected_rows,) or not np.isin(labels, [0, 1]).all():
                raise TraceFormatError("labels must be an aligned binary vector")

        fallback = adapter["missing_online_member_behavior"]
        temperatures, has_temperature = _window_array(
            archive,
            "predecision_temperature_c",
            windows=windows,
            default=float(fallback["predecision_temperature_c"]),
            dtype=np.float64,
        )
        queue_depths, has_queue = _window_array(
            archive,
            "predecision_queue_depth_samples",
            windows=windows,
            default=int(fallback["predecision_queue_depth_samples"]),
            dtype=np.int64,
        )
        capacities, has_capacity = _window_array(
            archive,
            "queue_capacity_samples",
            windows=windows,
            default=int(fallback["queue_capacity_samples"]),
            dtype=np.int64,
        )
        arrivals, has_arrivals = _window_array(
            archive,
            "arrivals_in_window",
            windows=windows,
            default=int(fallback["arrivals_in_window"]),
            dtype=np.int64,
        )
        # Deliberately do not access analysis_only_phase_ids, source_ids, indices,
        # or feature_fingerprints. They are neither online state nor training reward.

    if not np.isfinite(temperatures).all():
        raise TraceFormatError("predecision temperatures must be finite")
    if np.any(queue_depths < 0) or np.any(capacities <= 0) or np.any(queue_depths > capacities):
        raise TraceFormatError("queue observations are invalid")
    if np.any(arrivals < 0):
        raise TraceFormatError("arrivals_in_window must be non-negative")
    all_live = has_temperature and has_queue and has_capacity and has_arrivals
    origin = (
        "trace_supplied_online_observations"
        if all_live
        else str(fallback["origin"])
    )
    return NpzTraceEpisode(
        path=trace_path,
        partition=part,
        seed=seed,
        digest=digest,
        dataset=str(adapter["current_supported_dataset"]),
        probabilities=probabilities,
        labels=labels,
        temperatures=temperatures,
        queue_depths=queue_depths,
        queue_capacities=capacities,
        arrivals=arrivals,
        samples_per_window=samples,
        config=config,
        online_observation_origin=origin,
    )


def load_partition_episodes(
    directory: str | Path,
    *,
    partition: str | Partition,
    config: Mapping[str, Any],
    manifest_path: str | Path,
    load_labels: bool,
    require_complete_seed_set: bool = True,
) -> list[NpzTraceEpisode]:
    part = Partition.parse(partition)
    input_dir = Path(directory).resolve()
    manifest_file = Path(manifest_path).resolve()
    manifest = json.loads(manifest_file.read_text(encoding="utf-8"))
    if manifest.get("status") != "PASS":
        raise TraceFormatError("policy-input manifest status is not PASS")
    configured_key = {
        Partition.TRAIN: "training_trace_seeds",
        Partition.VALIDATION: "validation_trace_seeds",
        Partition.TEST: None,
        Partition.CALIBRATION: None,
    }[part]
    if configured_key is not None:
        expected_seeds = list(config["training_and_selection"][configured_key])
        manifest_key = "train_trace_seeds" if part is Partition.TRAIN else "validation_trace_seeds"
        if list(manifest.get(manifest_key, [])) != expected_seeds:
            raise TraceFormatError(f"manifest {manifest_key} differs from the fixed config")
    else:
        expected_seeds = list(config["experiment_scope"]["formal_test_trace_seeds"])

    by_seed: dict[int, Path] = {}
    for path in input_dir.glob(f"{part.value}_drift_*.npz"):
        match = TRACE_NAME.fullmatch(path.name)
        if match:
            by_seed[int(match.group(2))] = path
    if require_complete_seed_set and set(by_seed) != set(expected_seeds):
        raise TraceFormatError(
            f"{part.value} seed set mismatch: expected {expected_seeds}, got {sorted(by_seed)}"
        )
    output_hashes = manifest.get("output_sha256", {})
    episodes = []
    for seed in expected_seeds:
        if seed not in by_seed:
            continue
        path = by_seed[seed]
        expected_hash = output_hashes.get(path.name)
        if expected_hash is None:
            raise TraceFormatError(f"manifest has no digest for {path.name}")
        episodes.append(
            load_npz_episode(
                path,
                partition=part,
                config=config,
                expected_sha256=expected_hash,
                load_labels=load_labels,
                allow_posthoc_test_labels=False,
            )
        )
    return episodes
