"""Guards for the user-authorized #24 feature-policy freeze."""

import hashlib
import json
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_POLICY = REPO_ROOT / "config" / "feature_policy.json"
ONTOLOGY = REPO_ROOT / "config" / "label_ontology.json"
TARGET = (
    REPO_ROOT
    / "artifacts"
    / "proposals"
    / "feature_policy_freeze_target_v1r2.json"
)
BASELINE = (
    REPO_ROOT
    / "artifacts"
    / "freezes"
    / "feature_policy_pre_freeze_baseline.json"
)
PREINSTALL = (
    REPO_ROOT
    / "artifacts"
    / "freezes"
    / "feature_policy_freeze_preinstall_v1.json"
)
POSTINSTALL = (
    REPO_ROOT
    / "artifacts"
    / "freezes"
    / "feature_policy_freeze_postinstall_v1.json"
)
EXECUTION = (
    REPO_ROOT
    / "artifacts"
    / "freezes"
    / "feature_policy_freeze_execution_v1.json"
)
DECISIONS = REPO_ROOT / "docs" / "DECISIONS.md"
FMP = REPO_ROOT / "docs" / "FEATURE_MAPPING_PROTOCOL.md"

BASELINE_SHA = "2a903a4a0dd54e4307b7dce24599c39ce62b378b4cd8a95f8a633ffedb321b47"
TARGET_SHA = "e81a55c16f9439b0356295353e8b342de19d5c5606d868952592f913beda714b"
ONTOLOGY_SHA = "8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab"
FREEZE_ID = "FEATURE-POLICY-20260905-V1-FROZEN"
FLIP_PATHS = {
    "status",
    "semantic_core.candidate_examples[0].decision_status",
    "semantic_core.candidate_examples[1].decision_status",
    "semantic_core.review_outcome_2026_09_04.resolved_points[0]"
    ".decision_status",
}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def census(node, prefix=""):
    result = {}
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{prefix}.{key}" if prefix else key
            if key in ("status", "decision_status") and isinstance(value, str):
                result[child] = value
            result.update(census(value, child))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            result.update(census(value, f"{prefix}[{index}]"))
    return result


class FeaturePolicyFreezeExecutionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = json.loads(LIVE_POLICY.read_text(encoding="utf-8"))
        cls.baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
        cls.pre = json.loads(PREINSTALL.read_text(encoding="utf-8"))
        cls.post = json.loads(POSTINSTALL.read_text(encoding="utf-8"))
        cls.execution = json.loads(EXECUTION.read_text(encoding="utf-8"))

    def test_live_config_is_byte_identical_to_fixed_target(self):
        self.assertEqual(digest(LIVE_POLICY), TARGET_SHA)
        self.assertEqual(digest(TARGET), TARGET_SHA)
        self.assertEqual(LIVE_POLICY.read_bytes(), TARGET.read_bytes())

    def test_preserved_baseline_and_ontology_are_pinned(self):
        self.assertEqual(digest(BASELINE), BASELINE_SHA)
        self.assertEqual(digest(ONTOLOGY), ONTOLOGY_SHA)
        self.assertNotEqual(BASELINE.resolve(), LIVE_POLICY.resolve())
        self.assertNotEqual(BASELINE.resolve(), TARGET.resolve())

    def test_exactly_four_structured_statuses_flipped(self):
        self.assertEqual(census(self.baseline), dict.fromkeys(FLIP_PATHS, "proposed"))
        self.assertEqual(census(self.live), dict.fromkeys(FLIP_PATHS, "frozen"))

    def test_frozen_state_still_has_zero_admissions(self):
        admission = self.live["admission_set_this_version"]
        self.assertEqual(admission["admitted_mapping_count"], 0)
        self.assertEqual(admission["three_way_core"], "EMPTY")
        self.assertTrue(
            all(value.startswith("EMPTY") for value in admission["pairwise_cores"].values())
        )
        self.assertEqual(self.live["freeze_metadata"]["freeze_id"], FREEZE_ID)

    def test_preinstall_evidence_records_30_green_checks(self):
        self.assertEqual(self.pre["phase"], "pre_install")
        self.assertEqual(self.pre["verifier"]["exit_code"], 0)
        self.assertTrue(self.pre["verifier"]["all_pass"])
        self.assertEqual(self.pre["verifier"]["checks_total"], 30)
        self.assertEqual(self.pre["verifier"]["checks_failed"], [])
        self.assertFalse(self.pre["live_config_modified_by_verifier"])

    def test_postinstall_evidence_records_36_green_read_only_checks(self):
        self.assertTrue(self.post["all_pass"])
        self.assertEqual(self.post["checks_total"], 36)
        self.assertEqual(self.post["failures"], [])
        self.assertEqual(self.post["errors"], [])
        self.assertEqual(len(self.post["checks"]), 36)
        self.assertTrue(all(self.post["checks"].values()))
        self.assertFalse(self.post["authorization_granted"])
        self.assertFalse(self.post["data_gates_unlocked"])

    def test_each_data_gate_still_requires_separate_authorization(self):
        for gate in ("materialization", "splitting", "training"):
            state = self.live["data_handling"][gate]
            self.assertEqual(state["current"], "forbidden before protocol freeze")
            self.assertIn("individually authorized", state["authorization"])
            self.assertIn(
                "separate explicit user authorization", state["preconditions"][-1]
            )
        self.assertEqual(
            self.execution["operations_not_authorized_or_run"],
            ["materialization", "splitting", "training"],
        )

    def test_execution_record_contains_actual_commit_and_provenance(self):
        commit_id = self.execution["freeze_application_commit"]
        self.assertRegex(commit_id, re.compile(r"^[0-9a-f]{40}$"))
        self.assertEqual(
            self.execution["authorized_proposal_package"]["sha256"],
            "313e03a0fe702c11bc028adf16349d6aacfd211cf95b11aea5192b576e6a1d39",
        )
        self.assertEqual(
            self.execution["installation"]["installed_sha256"], TARGET_SHA
        )
        self.assertTrue(self.execution["installation"]["byte_equal"])

    def test_decision_and_protocol_docs_record_applied_freeze(self):
        decisions = DECISIONS.read_text(encoding="utf-8")
        protocol = FMP.read_text(encoding="utf-8")
        self.assertIn("24. FEATURE/LABEL PROTOCOL FROZEN as", decisions)
        self.assertIn(FREEZE_ID, decisions)
        self.assertIn("30/30", decisions)
        self.assertIn("36/36", decisions)
        self.assertIn("materialization, splitting, and training remain", decisions)
        self.assertIn("## 7. #24 applied feature/label protocol freeze", protocol)
        self.assertIn("36/36", protocol)


if __name__ == "__main__":
    unittest.main()
