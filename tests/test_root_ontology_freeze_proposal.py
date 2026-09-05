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
    """After the #22 freeze (LABEL-ONTOLOGY-ROOT-20260905-V1-FROZEN,
    applied on explicit user authorization), the former proposal-time
    inputs are frozen: these tests assert the frozen root axes and the
    unchanged out-of-scope items."""

    def setUp(self):
        self.ontology = load_label_ontology()

    def test_root_and_axes_all_frozen_after_22(self):
        self.assertEqual(self.ontology["status"], "frozen")
        self.assertEqual(
            self.ontology["canonical_family"]["decision_status"], "frozen"
        )
        for dataset in ("ton_iot", "ciciot2023", "n_baiot"):
            self.assertEqual(
                self.ontology["binary_label"]["derivation"][dataset]["decision_status"],
                "frozen",
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

    def test_proposal_flipped_exactly_the_scoped_statuses(self):
        """After #22: the proposal-stage statuses were flipped by the
        authorized freeze to exactly the scoped frozen set."""
        ontology = load_label_ontology()
        self.assertEqual(ontology["status"], "frozen")
        self.assertEqual(ontology["canonical_family"]["decision_status"], "frozen")
        for dataset in ("ton_iot", "ciciot2023", "n_baiot"):
            self.assertEqual(
                ontology["binary_label"]["derivation"][dataset]["decision_status"],
                "frozen",
            )


class RootFreezeProposalRev1Tests(unittest.TestCase):
    """#21 Rev 1 (proposal-consistency lock): the future #22 freeze is
    EXACTLY 5 status flips, the canonical_family.note frozen-state
    wording is pre-authorized, and the predetermined freeze id and
    provenance minimums are recorded. Nothing is frozen yet."""

    def test_recursive_census_frozen_set_is_exactly_all(self):
        """REVERSED BY THE #22 FREEZE (user-authorized): before #22 the
        census was 61 fields = 56 frozen + exactly 5 proposed. The #22
        freeze flipped exactly the 5 enumerated proposed paths
        (root status, canonical_family.decision_status, three
        derivation entries) to frozen; the census now reads 61 frozen
        + 0 proposed with no other value."""
        census = recursive_status_census(load_label_ontology())
        frozen = {path for path, value in census if value == "frozen"}
        proposed = {path for path, value in census if value == "proposed"}
        other = [(p, v) for p, v in census if v not in ("frozen", "proposed")]
        self.assertEqual(len(census), 61)
        self.assertEqual(len(frozen), 61)
        self.assertEqual(other, [])
        self.assertEqual(proposed, set())
        # the five flipped paths must be present among the frozen set
        self.assertTrue(
            {
                "status",
                "canonical_family.decision_status",
                "binary_label.derivation.ton_iot.decision_status",
                "binary_label.derivation.ciciot2023.decision_status",
                "binary_label.derivation.n_baiot.decision_status",
            }.issubset(frozen)
        )

    def test_canonical_family_note_is_frozen_state_wording(self):
        """The pre-authorized #22 note update is applied: the live note
        carries the frozen-state sentence (metadata housekeeping only,
        no family assignment change)."""
        ontology = load_label_ontology()
        self.assertEqual(ontology["canonical_family"]["note"], NOTE_FROZEN)
        self.assertNotEqual(ontology["canonical_family"]["note"], NOTE_CURRENT)

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

    def test_rev1_config_then_22_freeze_statuswise(self):
        """Rev 1 changed docs only (census then: 5 proposed); the #22
        freeze then flipped exactly those 5, so the census now reads
        61 frozen + 0 proposed."""
        ontology = load_label_ontology()
        self.assertEqual(ontology["status"], "frozen")
        self.assertEqual(
            ontology["canonical_family"]["decision_status"], "frozen"
        )
        census = recursive_status_census(ontology)
        self.assertEqual(sum(1 for _, v in census if v == "proposed"), 0)
        self.assertEqual(sum(1 for _, v in census if v == "frozen"), 61)


class RootFreezeRecordTests(unittest.TestCase):
    """The #22 freeze record: DECISIONS.md #22 and the LABEL_ONTOLOGY.md
    frozen-state append must record the freeze id, the EXACTLY-5 scope,
    the full provenance chain, and the surviving ban; the live config
    must match the frozen bytes and the untouched feature policy."""

    FROZEN_ONTOLOGY_SHA = (
        "8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab"
    )
    PRE_FREEZE_ONTOLOGY_SHA = (
        "86cc9a246346f26d414260f9adf56235fca5d6185918ce404a71bea9945db8ee"
    )
    POLICY_SHA = (
        "2a903a4a0dd54e4307b7dce24599c39ce62b378b4cd8a95f8a633ffedb321b47"
    )

    def test_decisions_md_records_decision_22_freeze(self):
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn("22. ROOT-LEVEL ONTOLOGY FROZEN as", md)
        self.assertIn(PREDICTED_FREEZE_ID, md)
        self.assertIn(
            "EXACTLY 5 status/decision_status fields were flipped", md
        )
        self.assertIn("proposal source commit `b59082a`", md)
        self.assertIn(PROPOSAL_V1_SHA, md)
        self.assertIn(FREEZE_V1R1_SHA, md)
        self.assertIn("source commit of the pre-freeze state `3aa8932`", md)
        self.assertIn("61 frozen\n    + 0 proposed", md)
        self.assertIn("this DECISIONS.md #22 record", md)
        self.assertIn(
            "the ban is NOT lifted by\n    an ontology root freeze alone", md
        )

    def test_decisions_md_records_frozen_and_pre_freeze_ontology_sha(self):
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "config/label_ontology.json SHA-256\n"
            f"    `{self.FROZEN_ONTOLOGY_SHA}`\n"
            "    (pre-freeze\n"
            f"    `{self.PRE_FREEZE_ONTOLOGY_SHA}`);\n"
            "    this DECISIONS.md #22 record.",
            md,
        )

    def test_label_ontology_md_records_applied_freeze(self):
        md = LABEL_ONTOLOGY_MD_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "The #22 freeze is APPLIED as\n"
            f"`{PREDICTED_FREEZE_ID}` on explicit user\n"
            "authorization following the user's verification of this "
            "proposal\nchain.",
            md,
        )
        self.assertIn(
            "Exactly the five enumerated status/decision_status fields\n"
            "were flipped proposed -> frozen",
            md,
        )
        self.assertIn(
            "recursive census after the freeze reads 61 frozen + "
            "0 proposed",
            md,
        )
        self.assertIn(
            "`config/feature_policy.json` remains `proposed` and "
            "byte-identical",
            md,
        )
        self.assertIn(
            "data materialization, splitting, and\ntraining remain "
            "forbidden until the feature/label protocol freeze",
            md,
        )

    def test_live_config_matches_frozen_recorded_bytes(self):
        import hashlib

        digest = hashlib.sha256(
            LABEL_ONTOLOGY_PATH.read_bytes()
        ).hexdigest()
        self.assertEqual(digest, self.FROZEN_ONTOLOGY_SHA)
        ontology = load_label_ontology()
        self.assertEqual(ontology["canonical_family"]["note"], NOTE_FROZEN)

    def test_feature_policy_untouched_by_22(self):
        import hashlib

        digest = hashlib.sha256(
            FEATURE_POLICY_PATH.read_bytes()
        ).hexdigest()
        self.assertEqual(digest, self.POLICY_SHA)
        with FEATURE_POLICY_PATH.open(encoding="utf-8") as handle:
            policy = json.load(handle)
        self.assertEqual(policy["status"], "proposed")
        handling = policy["data_handling"]
        self.assertEqual(handling["materialization"], "forbidden before protocol freeze")
        self.assertEqual(handling["splitting"], "forbidden before protocol freeze")
        self.assertEqual(handling["training"], "forbidden before protocol freeze")


class RootFreezeRev1DocumentationConsistencyTests(unittest.TestCase):
    """#22 Rev 1 (documentation-consistency fix, per user independent
    re-verification of the V1 freeze evidence package): two stale
    current-status passages in LABEL_ONTOLOGY.md were corrected.
    These guards check the two target passages with WHITESPACE
    NORMALIZATION (so markdown line wrapping cannot cause spurious
    failures) and do NOT run a global word ban over historical
    records."""

    FREEZE_ID = "LABEL-ONTOLOGY-ROOT-20260905-V1-FROZEN"

    @staticmethod
    def _normalized(md):
        return " ".join(md.split())

    def _family_list_passage(self):
        md = LABEL_ONTOLOGY_MD_PATH.read_text(encoding="utf-8")
        start = md.index("Current ")
        end = md.index("Fixed decisions already made:")
        return self._normalized(md[start:end])

    def test_family_list_passage_states_frozen_status(self):
        """DOC-01: the canonical_family current-family list must say
        'Current frozen families (14)' (not 'Current proposed
        families'), keep the 14 names and their order, and state that
        spoofing and brute_force are now frozen under the #22 freeze
        id (not 'both pending final freeze')."""
        passage = self._family_list_passage()
        self.assertIn("Current frozen families (14):", passage)
        self.assertNotIn("Current proposed families", passage)
        self.assertNotIn("pending final freeze", passage)
        # the 14 family names, in order
        self.assertIn(
            "`benign`, `backdoor`, `bashlite`, `brute_force`, `ddos`, "
            "`dos`, `injection`, `mirai`, `password`, `ransomware`, "
            "`recon`, `web_attack`, `mitm`, `spoofing`",
            passage,
        )
        # historical provenance kept + frozen status stated
        self.assertIn("proposed by the CICIoT2023 v1 mapping", passage)
        self.assertIn("`brute_force` adopted at v2", passage)
        self.assertIn(
            f"both are now frozen under `{self.FREEZE_ID}` "
            "(DECISIONS.md #22)",
            passage,
        )

    def test_ton_intro_passage_time_qualifies_proposed_state(self):
        """DOC-02: the TON-IoT table intro must not describe the root
        as currently proposed; the historical proposed state is kept
        with an explicit time qualifier (at the TON-IoT mapping freeze,
        DECISIONS.md #16) and the subsequent root-level freeze
        (DECISIONS.md #22) is stated. The mapping table that follows
        stays untouched (first header row unchanged)."""
        md = LABEL_ONTOLOGY_MD_PATH.read_text(encoding="utf-8")
        start = md.index("### TON-IoT type")
        end = md.index("| source_type |")
        passage = self._normalized(md[start:end])
        self.assertIn(
            "At the time of the TON-IoT mapping freeze "
            "(DECISIONS.md #16), the ontology root and "
            "`canonical_family.decision_status` remained `proposed`.",
            passage,
        )
        self.assertIn(
            f"They were subsequently frozen under `{self.FREEZE_ID}` "
            "(DECISIONS.md #22).",
            passage,
        )
        # the unqualified present-tense claim must be gone
        self.assertNotIn("remain `proposed` until the", passage)
        self.assertNotIn("mappings are also frozen", passage)


if __name__ == "__main__":
    unittest.main()
