from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from .artifacts import freeze_policy, load_policy, save_trained_policy
from .cfsm import CFSMScheduler
from .cli import main as cli_main
from .config import load_config
from .dqn import DQNPolicy, DQNTransition
from .isolation import DataIsolationError, DataUse, Partition, require_partition
from .offline_reference import LabelInformedPerWindowUtilityReference
from .reward import CostObservation, CostOrigin, RewardFunction
from .state import (
    ACTION_ORDER,
    Action,
    OnlineState,
    OnlineStateTracker,
    PreDecisionObservation,
    StateEncoder,
    StateError,
)
from .tabular_q import PolicyStateError, TabularQPolicy, TabularUpdate
from .trace_io import TraceFormatError, file_sha256, load_npz_episode
from .window_log import JsonlWindowLogger


class SchedulerInfrastructureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.loaded = load_config()
        cls.config = cls.loaded.data

    @staticmethod
    def state(
        *,
        window: int,
        temperature: float,
        threat: float,
        queue: float = 0.0,
        load: float = 1.0,
        previous: Action = Action.TINY_DT,
    ) -> OnlineState:
        prior = window - 1 if window else None
        return OnlineState(
            window_index=window,
            raw_temperature_c=temperature,
            smoothed_temperature_c=temperature,
            lagged_selected_model_threat=threat,
            predecision_queue_utilization=queue,
            lagged_arrival_rate_ratio=load,
            previous_action=previous,
            temperature_source_window=window,
            threat_source_window=prior,
            queue_source_window=window,
            load_source_window=prior,
            previous_action_source_window=prior,
        )

    def test_unique_config_and_seed_isolation(self) -> None:
        self.assertEqual(self.loaded.config_id, "TNSM-ADAPTIVE-SCHEDULER-20260907-V1")
        train = set(self.config["training_and_selection"]["training_trace_seeds"])
        validation = set(self.config["training_and_selection"]["validation_trace_seeds"])
        test = set(self.config["experiment_scope"]["formal_test_trace_seeds"])
        self.assertEqual(train, {211, 223, 227, 229, 233, 239, 241, 251, 257, 263})
        self.assertFalse(train & validation or train & test or validation & test)

    def test_online_state_is_one_window_lagged(self) -> None:
        tracker = OnlineStateTracker(self.config)
        first = tracker.begin_window(PreDecisionObservation(0, 40.0, 10, 100))
        self.assertEqual(first.lagged_selected_model_threat, 0.5)
        self.assertIsNone(first.threat_source_window)
        with self.assertRaises(StateError):
            tracker.begin_window(PreDecisionObservation(1, 41.0, 0, 100))
        tracker.complete_window(
            window_index=0,
            selected_action=Action.LIGHT_LR,
            selected_attack_probabilities=[0.8, 0.6],
            arrivals_in_window=130,
        )
        second = tracker.begin_window(PreDecisionObservation(1, 50.0, 50, 100))
        self.assertAlmostEqual(second.smoothed_temperature_c, 41.0)
        self.assertAlmostEqual(second.lagged_selected_model_threat, 0.7)
        self.assertAlmostEqual(second.lagged_arrival_rate_ratio, 1.3)
        self.assertEqual(second.previous_action, Action.LIGHT_LR)
        self.assertEqual(second.threat_source_window, 0)

    def test_state_encoder_has_324_unique_states(self) -> None:
        encoder = StateEncoder(self.config)
        temperatures = (40.0, 50.0, 75.0)
        threats = (0.1, 0.5, 0.9)
        queues = (0.1, 0.5, 0.9)
        loads = (0.5, 1.0, 1.5)
        indices = {
            encoder.encode(
                self.state(
                    window=1,
                    temperature=t,
                    threat=p,
                    queue=q,
                    load=load,
                    previous=action,
                )
            ).index
            for t in temperatures
            for p in threats
            for q in queues
            for load in loads
            for action in ACTION_ORDER
        }
        self.assertEqual(indices, set(range(324)))

    def test_cfsm_two_full_window_cooldown_and_thermal_override(self) -> None:
        cfsm = CFSMScheduler(self.config)
        first = cfsm.select_action(self.state(window=0, temperature=40, threat=0.8))
        self.assertEqual(first.selected_action, Action.LIGHT_LR)
        self.assertEqual(first.cooldown_after, 2)
        second = cfsm.select_action(
            self.state(window=1, temperature=40, threat=0.8, previous=Action.LIGHT_LR)
        )
        third = cfsm.select_action(
            self.state(window=2, temperature=40, threat=0.8, previous=Action.LIGHT_LR)
        )
        fourth = cfsm.select_action(
            self.state(window=3, temperature=40, threat=0.8, previous=Action.LIGHT_LR)
        )
        self.assertEqual([second.reason, third.reason], ["cooldown_hold", "cooldown_hold"])
        self.assertEqual(fourth.selected_action, Action.MED_RF)
        thermal = cfsm.select_action(
            self.state(window=4, temperature=70, threat=0.8, previous=Action.MED_RF)
        )
        self.assertEqual(thermal.selected_action, Action.LIGHT_LR)
        self.assertEqual(thermal.reason, "thermal_safety_step_lighter")

    def test_partition_guards(self) -> None:
        self.assertEqual(
            require_partition("train", DataUse.POLICY_UPDATE), Partition.TRAIN
        )
        with self.assertRaises(DataIsolationError):
            require_partition("test", DataUse.POLICY_UPDATE)
        with self.assertRaises(DataIsolationError):
            require_partition("test", DataUse.POSTHOC_METRICS, policy_frozen=False)
        self.assertEqual(
            require_partition("test", DataUse.POSTHOC_METRICS, policy_frozen=True),
            Partition.TEST,
        )

    def test_reward_and_cost_origin(self) -> None:
        reward = RewardFunction(self.config)
        cost = CostObservation(
            power_watts=2.347219335926574,
            latency_batch_ms=1.2979595,
            post_temperature_c=40.0,
            origin=CostOrigin.SYNTHETIC_UNIT_TEST,
            latency_origin="synthetic_unit_test",
            temperature_origin="synthetic_unit_test",
        )
        perfect = reward.calculate(
            labels=[0, 1],
            attack_probabilities=[0.1, 0.9],
            predecision_smoothed_temperature_c=40.0,
            cost=cost,
        )
        wrong = reward.calculate(
            labels=[0, 1],
            attack_probabilities=[0.9, 0.1],
            predecision_smoothed_temperature_c=40.0,
            cost=cost,
        )
        self.assertAlmostEqual(perfect.scalar_reward, 0.5)
        self.assertGreater(perfect.scalar_reward, wrong.scalar_reward)

    def test_tabular_update_is_train_only_and_freezes(self) -> None:
        policy = TabularQPolicy(self.config, seed=7)
        policy.update(TabularUpdate(0, Action.TINY_DT, 1.0, 1, True, Partition.TRAIN))
        self.assertAlmostEqual(policy.q_values[0, 0], 0.1)
        with self.assertRaises(DataIsolationError):
            policy.update(TabularUpdate(0, Action.TINY_DT, 1.0, 1, True, Partition.TEST))
        policy.freeze()
        with self.assertRaises(PolicyStateError):
            policy.update(TabularUpdate(0, Action.TINY_DT, 1.0, 1, True, Partition.TRAIN))

    def test_dqn_replay_is_train_only_and_freezes(self) -> None:
        config = deepcopy(self.config)
        config["dqn"].update(
            {
                "episodes": 3,
                "hidden_layers": [8, 8],
                "batch_size": 2,
                "replay_warmup_transitions": 2,
                "target_update_steps": 1,
            }
        )
        policy = DQNPolicy(config, seed=3)
        transition = DQNTransition(0, Action.TINY_DT, 1.0, 1, False, Partition.TRAIN)
        policy.observe(transition)
        policy.observe(transition)
        self.assertIsInstance(policy.optimize(), float)
        with self.assertRaises(DataIsolationError):
            policy.observe(DQNTransition(0, Action.TINY_DT, 0.0, 1, True, Partition.TEST))
        policy.freeze()
        with self.assertRaises(PolicyStateError):
            policy.optimize()

    def _write_trace(self, directory: Path, name: str) -> Path:
        windows = 500
        samples = 100
        rows = windows * samples
        probabilities = np.tile(
            np.asarray([[0.1, 0.2, 0.8, 0.9]], dtype=np.float32), (rows, 1)
        )
        labels = np.tile(np.asarray([0, 1], dtype=np.int8), rows // 2)
        path = directory / name
        np.savez_compressed(
            path,
            model_probabilities=probabilities,
            models=np.asarray([action.value for action in ACTION_ORDER]),
            labels=labels,
            analysis_only_phase_ids=np.full(windows, 99, dtype=np.int8),
            windows=np.int64(windows),
            samples_per_window=np.int64(samples),
        )
        return path

    def test_npz_adapter_never_exposes_test_labels_online(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = self._write_trace(root, "test_drift_11.npz")
            with self.assertRaises(DataIsolationError):
                load_npz_episode(
                    path,
                    partition="test",
                    config=self.config,
                    expected_sha256=file_sha256(path),
                    load_labels=True,
                )
            episode = load_npz_episode(
                path,
                partition="test",
                config=self.config,
                expected_sha256=file_sha256(path),
                load_labels=False,
            )
            self.assertIsNone(episode._labels)
            self.assertEqual(episode.pre_decision(0).raw_temperature_c, 35.0)
            with self.assertRaises(DataIsolationError):
                episode.load_labels_posthoc(schedule_complete=False, policy_frozen=True)
            labels = episode.load_labels_posthoc(schedule_complete=True, policy_frozen=True)
            self.assertEqual(labels.shape, (50000,))
            path.write_bytes(path.read_bytes() + b"changed")
            with self.assertRaises(TraceFormatError):
                episode.load_labels_posthoc(schedule_complete=True, policy_frozen=True)

    def test_offline_reference_is_explicitly_non_oracle(self) -> None:
        reference = LabelInformedPerWindowUtilityReference(self.config)
        self.assertFalse(reference.deployable)
        self.assertFalse(reference.oracle)
        self.assertFalse(reference.globally_optimal)
        self.assertEqual(reference.display_name, "Label-Informed Per-Window Utility Reference")

    def test_policy_artifact_requires_separate_freeze(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            policy = TabularQPolicy(self.config)
            trained_dir = root / "trained"
            frozen_dir = root / "frozen"
            manifest = root / "manifest.json"
            manifest.write_text(
                json.dumps(
                    {
                        "output_sha256": {
                            "train_drift_211.npz": "a" * 64,
                            "validation_drift_401.npz": "b" * 64,
                        }
                    }
                )
            )
            training_log = root / "training.jsonl"
            training_log.write_text("{}\n")
            metadata = save_trained_policy(
                trained_dir,
                config=self.loaded,
                policy=policy,
                training_metadata={
                    "test_data_accessed": False,
                    "analysis_only_phase_ids_read": False,
                    "episodes": 1000,
                    "policy_input_manifest": str(manifest),
                    "policy_input_manifest_sha256": file_sha256(manifest),
                    "training_log": str(training_log),
                    "training_log_sha256": file_sha256(training_log),
                    "train_trace_sha256": {"train_drift_211.npz": "a" * 64},
                    "validation_trace_sha256": {
                        "validation_drift_401.npz": "b" * 64
                    },
                },
            )
            self.assertFalse(metadata["frozen"])
            with self.assertRaises(Exception):
                load_policy(trained_dir, config=self.loaded, require_frozen=True)
            frozen = freeze_policy(trained_dir, frozen_dir, config=self.loaded)
            self.assertTrue(frozen["frozen"])
            loaded, _ = load_policy(frozen_dir, config=self.loaded, require_frozen=True)
            self.assertTrue(loaded.frozen)

    def test_window_logger_separates_decision_outcome_and_posthoc(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "windows.jsonl"
            logger = JsonlWindowLogger(
                path,
                config_id=self.loaded.config_id,
                config_sha256=self.loaded.sha256,
            )
            state = self.state(window=0, temperature=40, threat=0.5)
            encoded = StateEncoder(self.config).encode(state)
            logger.decision(
                run_id="synthetic",
                method="Tabular-Q",
                trace_id="synthetic-trace",
                dataset="ton_iot",
                partition="test",
                state=state,
                encoded_state=encoded,
                selected_action=Action.TINY_DT,
                decision_detail={"mode": "frozen_greedy"},
                policy_artifact_sha256="0" * 64,
            )
            event = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(event["event_type"], "window_decision")
            self.assertFalse(event["labels_accessed_before_action"])
            self.assertNotIn("labels", event)

    def test_cli_validate_config_smoke(self) -> None:
        self.assertEqual(cli_main(["validate-config"]), 0)


if __name__ == "__main__":
    unittest.main()
