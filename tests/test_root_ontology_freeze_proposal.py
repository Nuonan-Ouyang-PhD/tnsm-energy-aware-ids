import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LABEL_ONTOLOGY_PATH = REPO_ROOT / "config" / "label_ontology.json"
FEATURE_POLICY_PATH = REPO_ROOT / "config" / "feature_policy.json"
DECISIONS_PATH = REPO_ROOT / "docs" / "DECISIONS.md"
LABEL_ONTOLOGY_MD_PATH = REPO_ROOT / "docs" / "LABEL_ONTOLOGY.md"

PROPOSED_ID = "LABEL-ONTOLOGY-ROOT-20260905-V1-PROPOSED"
FREEZE_V1R1_SHA = "1912365fe8a20f478a367dc844f3067c6d7fac176e71a5e9505a21c38fae3d3c"


def load_label_ontology():
    with LABEL_ONTOLOGY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


class RootFreezeProposalInputStateTests(unittest.TestCase):
    """Lock the CURRENT (proposal-time) state that #21 declares as its
    inputs. These tests assert proposed statuses NOW; a future #22
    freeze commit must REVERSE these assertions deliberately."""

    def setUp(self):
        self.ontology = load_label_ontology()

    def test_root_and_axes_all_proposed_at_proposal_time(self):
        self.assertEqual(self.ontology["status"], "proposed")
        self.assertEqual(
            self.ontology["canonical_family"]["decision_status"], "proposed"
        )
        for dataset in ("ton_iot", "ciciot2023", "n_baiot"):
            self.assertEqual(
                self.ontology["binary_label"]["derivation"][dataset]["decision_status"],
                "proposed",
                dataset,
            )

    def test_all_three_dataset_tables_frozen(self):
        cf = self.ontology["canonical_family"]
        for block, count, freeze_id in (
            ("ton_iot_type_mapping", 10, "TON-IOT-TYPE-MAPPING-20260904-V1-FROZEN"),
            ("ciciot2023_type_mapping", 34, "CICIOT2023-TYPE-MAPPING-20260904-V1-FROZEN"),
            ("n_baiot_type_mapping", 11, "N-BAIOT-TYPE-MAPPING-20260905-V1-FROZEN"),
        ):
            entries = cf[block]["entries"]
            self.assertEqual(len(entries), count, block)
            self.assertTrue(
                all(e["decision_status"] == "frozen" for e in entries), block
            )
            self.assertIn(freeze_id, cf[block]["description"], block)

    def test_fixed_decision_still_frozen(self):
        fixed = self.ontology["canonical_family"]["fixed_decisions"]
        self.assertEqual(len(fixed), 1)
        self.assertEqual(fixed[0]["decision_status"], "frozen")

    def test_feature_policy_still_proposed(self):
        with FEATURE_POLICY_PATH.open(encoding="utf-8") as handle:
            policy = json.load(handle)
        self.assertEqual(policy["status"], "proposed")

    def test_data_handling_ban_unchanged(self):
        with FEATURE_POLICY_PATH.open(encoding="utf-8") as handle:
            policy = json.load(handle)
        handling = policy["data_handling"]
        self.assertEqual(handling["materialization"], "forbidden before protocol freeze")
        self.assertEqual(handling["splitting"], "forbidden before protocol freeze")
        self.assertEqual(handling["training"], "forbidden before protocol freeze")


class RootFreezeProposalRecordTests(unittest.TestCase):
    """The #21 proposal must be recorded, scoped, and must itself change
    no status."""

    def test_decisions_md_records_decision_21(self):
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn("21. ROOT-LEVEL ONTOLOGY FREEZE PROPOSED as", md)
        self.assertIn(PROPOSED_ID, md)
        self.assertIn("This record is a proposal\n    for review only", md)
        self.assertIn(FREEZE_V1R1_SHA, md)
        # scope of a future #22 flip
        self.assertIn("ontology root `status` proposed -> frozen", md)
        self.assertIn("`canonical_family.decision_status` proposed -> frozen", md)
        self.assertIn("binary_label.derivation.*.decision_status` entries proposed", md)
        # out-of-scope and ban statement
        self.assertIn("config/feature_policy.json", md)
        self.assertIn("is NOT lifted by an\n    ontology root freeze alone", md)
        self.assertIn("Nothing is\n    frozen in this record", md)
        # #20 final evidence chain referenced
        self.assertIn("a2682f8", md)
        self.assertIn("b017f8f", md)

    def test_label_ontology_md_section6_staging_record(self):
        md = LABEL_ONTOLOGY_MD_PATH.read_text(encoding="utf-8")
        self.assertIn("## 6. Root-level ontology freeze proposal (staging record)", md)
        self.assertIn(PROPOSED_ID, md)
        self.assertIn("All\nstatuses are UNCHANGED at proposal time", md)
        self.assertIn("outside the freeze axis", md)
        self.assertIn("not this ontology root\nfreeze alone", md)

    def test_proposal_changes_no_status(self):
        """Machine assertion that the proposal itself flipped nothing:
        every status field still reads the pre-proposal values."""
        ontology = load_label_ontology()
        self.assertEqual(ontology["status"], "proposed")
        self.assertEqual(ontology["canonical_family"]["decision_status"], "proposed")
        for dataset in ("ton_iot", "ciciot2023", "n_baiot"):
            self.assertEqual(
                ontology["binary_label"]["derivation"][dataset]["decision_status"],
                "proposed",
            )


if __name__ == "__main__":
    unittest.main()
