import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LABEL_ONTOLOGY_PATH = REPO_ROOT / "config" / "label_ontology.json"
FEATURE_POLICY_PATH = REPO_ROOT / "config" / "feature_policy.json"
DECISIONS_PATH = REPO_ROOT / "docs" / "DECISIONS.md"
LABEL_ONTOLOGY_MD_PATH = REPO_ROOT / "docs" / "LABEL_ONTOLOGY.md"

PROPOSED_ID = "LABEL-ONTOLOGY-ROOT-20260905-V1-PROPOSED"
PREDICTED_FREEZE_ID = "LABEL-ONTOLOGY-ROOT-20260905-V1-FROZEN"
FREEZE_V1R1_SHA = "1912365fe8a20f478a367dc844f3067c6d7fac176e71a5e9505a21c38fae3d3c"
PROPOSAL_V1_SHA = "3da7642fb1a08d7aee987298af01e6bd7eb5b2dbf3b727d05c68c994b14c284a"
NOTE_CURRENT = (
    "Final family assignments are NOT frozen until the TON-IoT type "
    "inventory is complete and official documents are reviewed."
)
NOTE_FROZEN = (
    "Final family assignments are frozen under "
    "LABEL-ONTOLOGY-ROOT-20260905-V1-FROZEN after completion of the "
    "required inventory and official-document reviews."
)


def recursive_status_census(node, path=""):
    """Recursively collect every (path, value) pair whose dict key is
    `status` or `decision_status` with a string value."""
    hits = []
    if isinstance(node, dict):
        for key, value in node.items():
            child = f"{path}.{key}" if path else key
            if key in ("status", "decision_status") and isinstance(value, str):
                hits.append((child, value))
            hits.extend(recursive_status_census(value, child))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            hits.extend(recursive_status_census(value, f"{path}[{index}]"))
    return hits


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


class RootFreezeProposalRev1Tests(unittest.TestCase):
    """#21 Rev 1 (proposal-consistency lock): the future #22 freeze is
    EXACTLY 5 status flips, the canonical_family.note frozen-state
    wording is pre-authorized, and the predetermined freeze id and
    provenance minimums are recorded. Nothing is frozen yet."""

    def test_recursive_census_proposed_set_is_exactly_five(self):
        """Recursive enumeration over the WHOLE label_ontology.json:
        61 status/decision_status fields = 56 frozen + exactly 5
        proposed, and the proposed paths are precisely the 5 the #22
        freeze would flip - no more, no less. A future #22 freeze must
        REVERSE the proposed half of this assertion deliberately."""
        census = recursive_status_census(load_label_ontology())
        proposed = {path for path, value in census if value == "proposed"}
        frozen = {path for path, value in census if value == "frozen"}
        other = [(p, v) for p, v in census if v not in ("frozen", "proposed")]
        self.assertEqual(len(census), 61)
        self.assertEqual(len(frozen), 56)
        self.assertEqual(other, [])
        self.assertEqual(
            proposed,
            {
                "status",
                "canonical_family.decision_status",
                "binary_label.derivation.ton_iot.decision_status",
                "binary_label.derivation.ciciot2023.decision_status",
                "binary_label.derivation.n_baiot.decision_status",
            },
        )

    def test_canonical_family_note_is_proposal_stage_wording(self):
        """The live note in config still carries the proposal-stage
        sentence; the #22 freeze is pre-authorized to replace it with
        the frozen-state sentence (metadata housekeeping only)."""
        ontology = load_label_ontology()
        self.assertEqual(ontology["canonical_family"]["note"], NOTE_CURRENT)
        self.assertNotIn(ontology["canonical_family"]["note"], NOTE_FROZEN)

    def test_decisions_md_records_decision_21_rev1(self):
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn("Rev 1 (proposal-consistency lock", md)
        self.assertIn("EXACTLY 5 status flips", md)
        self.assertIn(PROPOSAL_V1_SHA, md)
        self.assertIn(PREDICTED_FREEZE_ID, md)
        self.assertIn("56 frozen +\n    5 proposed = 61 total", md)
        self.assertIn("56 frozen + exactly 5 proposed", md)
        self.assertIn("pre-authorized to update the `canonical_family.note`", md)
        # NOTE_CURRENT quoted in DECISIONS.md (wrapped at 76 chars)
        self.assertIn(
            '"Final family assignments are NOT\n'
            '    frozen until the TON-IoT type inventory is complete and official\n'
            '    documents are reviewed."',
            md,
        )
        # NOTE_FROZEN quoted in DECISIONS.md (wrapped at 76 chars)
        self.assertIn(
            '"Final\n'
            '    family assignments are frozen under\n'
            '    LABEL-ONTOLOGY-ROOT-20260905-V1-FROZEN after completion of the\n'
            '    required inventory and official-document reviews."',
            md,
        )
        self.assertIn("the proposal source\n    commit `b59082a`", md)
        self.assertIn("this is\n    freeze-state metadata housekeeping only: no family assignment", md)
        self.assertIn("separate explicit user authorization", md)

    def test_label_ontology_md_section6_records_rev1(self):
        md = LABEL_ONTOLOGY_MD_PATH.read_text(encoding="utf-8")
        self.assertIn("Rev 1 (proposal-consistency lock, per user review of", md)
        self.assertIn("EXACTLY 5 status flips", md)
        self.assertIn("56 frozen and exactly 5 proposed", md)
        self.assertIn(PREDICTED_FREEZE_ID, md)
        self.assertIn("pre-authorized to update the `canonical_family.note`", md)
        # NOTE_CURRENT quoted in LABEL_ONTOLOGY.md (wrapped at 76 chars)
        self.assertIn(
            '"Final family assignments are NOT frozen\n'
            'until the TON-IoT type inventory is complete and official documents\n'
            'are reviewed."',
            md,
        )
        # NOTE_FROZEN quoted in LABEL_ONTOLOGY.md (wrapped at 76 chars)
        self.assertIn(
            '"Final family\n'
            'assignments are frozen under LABEL-ONTOLOGY-ROOT-20260905-V1-FROZEN\n'
            'after completion of the required inventory and official-document\n'
            'reviews."',
            md,
        )
        self.assertIn("`b59082a`", md)
        self.assertIn(PROPOSAL_V1_SHA, md)
        self.assertIn(FREEZE_V1R1_SHA, md)
        # the note flip is metadata-only: no family assignment changes
        self.assertIn("changing no\nfamily assignment", md)
        # ban and authorization gates restated
        self.assertIn("separate\nexplicit user authorization", md)
        self.assertIn("training remain forbidden", md)

    def test_rev1_config_untouched_statuswise(self):
        """Rev 1 changed docs only; the recursive census must still
        show the same 5 proposed paths (guards against any accidental
        config edit during the Rev 1 script run)."""
        ontology = load_label_ontology()
        self.assertEqual(ontology["status"], "proposed")
        self.assertEqual(
            ontology["canonical_family"]["decision_status"], "proposed"
        )
        census = recursive_status_census(ontology)
        self.assertEqual(sum(1 for _, v in census if v == "proposed"), 5)
        self.assertEqual(sum(1 for _, v in census if v == "frozen"), 56)


if __name__ == "__main__":
    unittest.main()
