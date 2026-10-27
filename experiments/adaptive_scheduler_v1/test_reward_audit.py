"""Regression tests for the validation-only reward audit."""

from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from reward_audit import build_audit


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

    def test_test_gap_is_descriptive_only(self):
        diagnostic = self.audit["static_classifier_aggregate_diagnostic"]
        self.assertAlmostEqual(
            diagnostic["test_balanced_accuracy_gap_medrf_minus_lightlr"],
            0.01401199554792143,
        )
        self.assertIn("not used", diagnostic["test_gap_role"])


if __name__ == "__main__":
    unittest.main()
