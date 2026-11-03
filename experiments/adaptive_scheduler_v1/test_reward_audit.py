"""Regression tests for the validation-only reward audit."""

from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reward_audit import build_audit
from scheduler.reward import CostObservation, CostOrigin, RewardFunction
from scheduler.config import load_config
from reward_audit import ROOT
from scheduler.trace_io import load_npz_episode
from scheduler.isolation import Partition
from scheduler.state import Action
import json


class RewardAuditTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.audit, cls.rows = build_audit()

    def test_hash_bound_validation_scope(self):
        self.assertEqual(self.audit["validation_traces"], 5)
        self.assertEqual(self.audit["validation_windows"], 2500)
        self.assertFalse(self.audit["test_used_for_reward_audit"])

    def test_medrf_lightlr_pair(self):
        pair = self.audit["medrf_minus_lightlr"]
        self.assertAlmostEqual(pair["tau_ab"], 0.7966756095509868)
        self.assertAlmostEqual(pair["validation_delta_ba_min"], -0.10526315789473684)
        self.assertAlmostEqual(pair["validation_delta_ba_max"], 0.10526315789473673)
        self.assertFalse(pair["strict_reversal_attainable"])

    def test_tinydt_exceptions_preclude_global_optimality(self):
        self.assertEqual(len(self.audit["tinydt_above_lightlr_windows"]), 7)
        self.assertFalse(self.audit["lightlr_globally_optimal_proven"])
        self.assertIn("retrospective", self.audit["audit_timing"])

    def test_no_test_or_aggregate_file_access(self):
        original = Path.open
        def guarded(path, *args, **kwargs):
            if path.name.startswith("test_drift_") or "reward_audit_inputs" in path.parts:
                raise AssertionError(f"forbidden audit input: {path}")
            return original(path, *args, **kwargs)
        with patch.object(Path, "open", guarded):
            audit, _ = build_audit()
        self.assertEqual(audit["validation_windows"], 2500)

    def test_missing_post_temperature_is_not_a_measurement(self):
        config = load_config(ROOT / "config/scheduler_experiment_v1.json").data
        cost = CostObservation(2.35, 2.0, None,
            CostOrigin.TON_STATIC_PROFILE_LOOKUP_PROXY, "profile", "unavailable")
        result = RewardFunction(config).calculate(labels=[0, 1],
            attack_probabilities=[0.1, 0.9],
            predecision_temperature_c=36.0, cost=cost)
        self.assertFalse(result.thermal_measurement_available)
        self.assertEqual(result.positive_thermal_increment, 0.0)

    def test_adapter_keeps_varying_pre_temperature_out_of_outcome(self):
        config = load_config(ROOT / "config/scheduler_experiment_v1.json").data
        manifest = json.loads((ROOT / "policy_inputs/manifest.json").read_text())
        name = "validation_drift_401.npz"
        episode = load_npz_episode(ROOT / "policy_inputs" / name,
            partition=Partition.VALIDATION, config=config,
            expected_sha256=manifest["output_sha256"][name], load_labels=True)
        episode.temperatures[0] = 42.0
        self.assertEqual(episode.pre_decision(0).raw_temperature_c, 42.0)
        self.assertIsNone(episode.outcome_for_action(0, Action.LIGHT_LR).cost.post_temperature_c)

    def test_measured_increment_uses_raw_pre_temperature(self):
        config = load_config(ROOT / "config/scheduler_experiment_v1.json").data
        cost = CostObservation(2.35, 2.0, 40.5,
            CostOrigin.TON_STATIC_PROFILE_LOOKUP_PROXY, "profile", "synthetic measurement")
        result = RewardFunction(config).calculate(labels=[0, 1],
            attack_probabilities=[0.1, 0.9], predecision_temperature_c=40.0, cost=cost)
        self.assertTrue(result.thermal_measurement_available)
        self.assertAlmostEqual(result.positive_thermal_increment, 0.5)


if __name__ == "__main__":
    unittest.main()
