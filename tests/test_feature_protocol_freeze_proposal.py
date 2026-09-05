"""Guard tests for the #23 feature/label protocol freeze PROPOSAL
(FEATURE-POLICY-20260905-V1-PROPOSED, DECISIONS.md #23).

Proposal-stage invariants asserted here:
  - the four structured status fields in config/feature_policy.json
    are exactly the proposed set (recursive census; nothing else is
    a status field);
  - both config files stay byte-identical to the frozen/pre-proposal
    SHAs (the proposal flips nothing);
  - the three data_handling gates remain "forbidden before protocol
    freeze" verbatim;
  - the proto census artifact exists, reconciles with the frozen
    inventory, and records exactly the three raw values with no
    anomalies;
  - admission boundaries: unresolved/rejected dispositions must not
    appear in any admitted-mapping set; the admitted protocol
    indicator subset is exactly {tcp, udp} per the proposal wording;
  - DECISIONS.md #23 and the FEATURE_MAPPING_PROTOCOL.md section 6
    staging record exist with the required scope statements.
"""

import hashlib
import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURE_POLICY_PATH = REPO_ROOT / "config" / "feature_policy.json"
LABEL_ONTOLOGY_PATH = REPO_ROOT / "config" / "label_ontology.json"
DECISIONS_PATH = REPO_ROOT / "docs" / "DECISIONS.md"
FMP_PATH = REPO_ROOT / "docs" / "FEATURE_MAPPING_PROTOCOL.md"
CENSUS_PATH = (
    REPO_ROOT / "artifacts" / "datasets" / "proto_census"
    / "ton_iot_proto_20260905T110840Z.json"
)
INVENTORY_PATH = (
    REPO_ROOT / "artifacts" / "datasets" / "inventories"
    / "ton_iot_20260903T113048Z.json"
)

PROPOSED_ID = "FEATURE-POLICY-20260905-V1-PROPOSED"
PREDICTED_FREEZE_ID = "FEATURE-POLICY-20260905-V1-FROZEN"

FEATURE_POLICY_SHA = (
    "2a903a4a0dd54e4307b7dce24599c39ce62b378b4cd8a95f8a633ffedb321b47"
)
LABEL_ONTOLOGY_SHA = (
    "8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab"
)
CENSUS_SHA = (
    "89f06e9c3913e2d429be6021ff42f907727f36e69cebf5bc5639b9793e689830"
)

EXPECTED_PROPOSED_PATHS = {
    "status",
    "semantic_core.candidate_examples[0].decision_status",
    "semantic_core.candidate_examples[1].decision_status",
    "semantic_core.review_outcome_2026_09_04.resolved_points[0]"
    ".decision_status",
}

CENSUS_COUNTS = {"tcp": 168747, "udp": 42015, "icmp": 281}
CENSUS_TOTAL_ROWS = 211043


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def recursive_status_census(node, path=""):
    """Collect every (path, value) whose dict key is `status` or
    `decision_status` with a string value."""
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


class FeaturePolicyProposalStateTests(unittest.TestCase):
    """The #23 proposal leaves config/feature_policy.json untouched:
    the four structured status fields are exactly the proposed set."""

    def setUp(self):
        with FEATURE_POLICY_PATH.open(encoding="utf-8") as handle:
            self.policy = json.load(handle)

    def test_recursive_census_proposed_set_is_exactly_four(self):
        census = recursive_status_census(self.policy)
        proposed = {path for path, value in census if value == "proposed"}
        other = [(p, v) for p, v in census if v not in ("proposed", "frozen")]
        self.assertEqual(len(census), 4)
        self.assertEqual(
            proposed,
            EXPECTED_PROPOSED_PATHS,
            "the proposed set must be exactly the four enumerated paths",
        )
        self.assertEqual(other, [])

    def test_candidate_example_dispositions_unchanged(self):
        examples = self.policy["semantic_core"]["candidate_examples"]
        self.assertEqual(examples[0]["semantic_disposition"], "unresolved")
        self.assertEqual(examples[1]["semantic_disposition"], "rejected")
        self.assertEqual(examples[0]["canonical_concept"],
                         "total_transferred_bytes")
        self.assertEqual(examples[1]["canonical_concept"],
                         "decayed_window_statistics")

    def test_mi_dir_resolved_point_still_derived_proposed(self):
        point = self.policy["semantic_core"]["review_outcome_2026_09_04"][
            "resolved_points"
        ][0]
        self.assertEqual(point["semantic_disposition"], "derived")
        self.assertEqual(point["decision_status"], "proposed")

    def test_data_handling_bans_verbatim(self):
        handling = self.policy["data_handling"]
        for gate in ("materialization", "splitting", "training"):
            self.assertEqual(
                handling[gate], "forbidden before protocol freeze", gate
            )


class ProposalConfigInvarianceTests(unittest.TestCase):
    """The proposal changes no config byte: both files match the
    frozen/pre-proposal SHAs."""

    def test_feature_policy_byte_identical(self):
        self.assertEqual(sha256_file(FEATURE_POLICY_PATH), FEATURE_POLICY_SHA)

    def test_label_ontology_byte_identical(self):
        self.assertEqual(sha256_file(LABEL_ONTOLOGY_PATH), LABEL_ONTOLOGY_SHA)


class ProtoCensusArtifactTests(unittest.TestCase):
    """The one-off authorized proto census artifact: identity,
    reconciliation, and no-anomaly invariants."""

    @classmethod
    def setUpClass(cls):
        cls.census = json.loads(CENSUS_PATH.read_text(encoding="utf-8"))

    def test_artifact_sha(self):
        self.assertEqual(sha256_file(CENSUS_PATH), CENSUS_SHA)

    def test_census_source_identity(self):
        inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
        entry = inventory["files"][0]
        self.assertEqual(self.census["source"]["sha256"], entry["sha256"])
        self.assertEqual(self.census["source"]["relative_path"],
                         entry["relative_path"])
        self.assertEqual(self.census["source"]["column"], "proto")

    def test_census_counts_reconcile_with_inventory(self):
        self.assertEqual(self.census["proto_value_counts"], CENSUS_COUNTS)
        self.assertEqual(self.census["total_rows"], CENSUS_TOTAL_ROWS)
        recon = self.census["reconciliation"]
        self.assertTrue(recon["row_count_match"])
        self.assertTrue(recon["sum_equals_row_count"])
        self.assertEqual(recon["distinct_raw_values"], 3)
        self.assertEqual(
            sum(self.census["proto_value_counts"].values()),
            CENSUS_TOTAL_ROWS,
        )

    def test_census_no_anomalies(self):
        anomalies = self.census["anomalies"]
        self.assertEqual(anomalies["empty_string"], 0)
        self.assertEqual(anomalies["whitespace_only"], 0)
        self.assertEqual(anomalies["placeholder_like_values"], {})
        self.assertEqual(anomalies["row_field_count_mismatch"], 0)
        self.assertEqual(anomalies["parse_errors"], 0)

    def test_census_is_audit_only_not_encoder_vocabulary(self):
        notes = " ".join(self.census["notes"])
        self.assertIn("must NOT be used as an all-data encoder", notes)
        self.assertIn("training split", notes)
        self.assertFalse(self.census["paper_eligible"])
        self.assertEqual(self.census["normalization_status"], "proposed")


class ProposalAdmissionBoundaryTests(unittest.TestCase):
    """Admission boundaries: unresolved/rejected records must not be
    admitted; the admitted protocol-indicator subset is exactly the
    {tcp, udp} subset; icmp stays unresolved."""

    def test_unresolved_and_rejected_not_admitted(self):
        """No record with semantic_disposition unresolved or rejected
        may be presented as an admitted (exact/derived-and-admitted)
        mapping. In the current config the two candidate examples are
        the only records carrying these dispositions and both carry
        explicit non-admission gate_notes."""
        with FEATURE_POLICY_PATH.open(encoding="utf-8") as handle:
            policy = json.load(handle)
        examples = policy["semantic_core"]["candidate_examples"]
        for example in examples:
            if example["semantic_disposition"] in ("unresolved", "rejected"):
                self.assertIn(
                    "REVIEW OUTCOME 2026-09-04", example["gate_note"]
                )
                self.assertIn(
                    "docs/FIELD_SEMANTICS_REVIEW.md", example["gate_note"]
                )

    def test_proposal_admits_exactly_tcp_udp_subset(self):
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn("EXACTLY the subset {tcp, udp} is proposed", md)
        self.assertIn("icmp stays `unresolved`", md)
        self.assertIn("no correspondence is\n          invented", md)
        # the decision record must NOT claim the eight columns match
        self.assertNotIn("eight columns are equivalent", md)

    def test_packet_count_stays_unresolved(self):
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn("packet_count: stays `unresolved`", md)

    def test_gate_target_values_listed(self):
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn(
            '"forbidden before protocol freeze" to\n'
            '        "permitted after protocol freeze (#24)',
            md,
        )
        # gates stay forbidden until #24
        self.assertIn(
            "the gates stay\n        forbidden until then", md
        )


class ProposalRecordTests(unittest.TestCase):
    """DECISIONS.md #23 and the FEATURE_MAPPING_PROTOCOL.md section 6
    staging record exist with the required scope statements."""

    def test_decisions_md_records_decision_23(self):
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn("23. FEATURE/LABEL PROTOCOL FREEZE PROPOSED as", md)
        self.assertIn(PROPOSED_ID, md)
        self.assertIn(PREDICTED_FREEZE_ID, md)
        self.assertIn("no status is flipped", md)
        self.assertIn("one-off", md)
        self.assertIn("audit", md)

    def test_decisions_md_scopes_the_four_flips(self):
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        for path in EXPECTED_PROPOSED_PATHS:
            if path == "status":
                self.assertIn("`status` (policy root)", md)
            elif "candidate_examples[0]" in path:
                self.assertIn(
                    "candidate_examples[0].decision_status", md
                )
            elif "candidate_examples[1]" in path:
                self.assertIn(
                    "candidate_examples[1].decision_status", md
                )
            else:
                self.assertIn(
                    "resolved_points[0].\n        decision_status", md
                )

    def test_decisions_md_states_not_executed(self):
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn("#24 execution requires separate explicit", md)
        self.assertIn("Nothing is frozen in this record", md)
        self.assertIn("user review of this proposal is\n    pending", md)

    def test_fmp_section6_staging_record(self):
        md = FMP_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "## 6. Feature/label protocol freeze proposal (staging record)",
            md,
        )
        self.assertIn(PROPOSED_ID, md)
        self.assertIn("All statuses are UNCHANGED at proposal time", md)
        self.assertIn("own authorization", md)
        # section 5 ban sentence intact above the new section
        self.assertIn(
            "no data copies are created.\n\n## 6.", md
        )


if __name__ == "__main__":
    unittest.main()
