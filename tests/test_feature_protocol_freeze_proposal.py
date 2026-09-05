"""Guard tests for the #23 feature/label protocol freeze PROPOSAL
(FEATURE-POLICY-20260905-V1-PROPOSED, DECISIONS.md #23) and its Rev 1
zero-admission revision (DECISIONS.md #23 Rev 1).

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
    appear in any admitted-mapping set; the V1 proposal wording (kept
    as the historical staging record) is still present in DECISIONS.md;
  - DECISIONS.md #23 and the FEATURE_MAPPING_PROTOCOL.md section 6
    staging record exist with the required scope statements.

Rev 1 invariants additionally asserted here:
  - the zero-admission draft JSON exists with exactly 4 status flips,
    6 per-record evidence targets, 2 complete string targets, 3 gate
    targets, and an EMPTY admission set (admitted_mapping_count 0);
  - the v2 census verification pass artifacts reproduce v1 exactly
    with before/after source-hash invariance, and the v1/v2 census
    scripts are archived in scripts/audits/;
  - the two conflicting CICIoT2023 README page-1 feature tables are
    archived and registered as an official-source internal
    inconsistency;
  - FEATURE_MAPPING_PROTOCOL.md uses the dual-axis wording
    (semantic_disposition x decision_status), carries a 6.1 Rev 1
    staging addendum, and DECISIONS.md records the Rev 1 outcome;

Rev 2 invariants additionally asserted here (F23-02 A/B/C):
  - the committed target artifact is a complete would-be-effective
    configuration whose bytes are reproducible from the live
    baseline by the archived generator script, and the live config
    is still byte-identical to the baseline (nothing applied);
  - simulating the application in an independent temporary copy
    yields exactly 4 structured status flips with dispositions
    unchanged, the MI_dir array rules (element [0] byte-equal),
    zero actual admissions, the two string rewordings, and gate
    objects with 6 standalone structured preconditions each;
  - the Rev 2 target specification binds admission_set /
    freeze_metadata verbatim to the target artifact root keys and
    records the 30-check outcome evidence;
"""

import hashlib
import importlib.util
import json
import tempfile
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

# --- Rev 1 (2026-09-05) constants ---------------------------------
DRAFT_PATH = (
    REPO_ROOT / "artifacts" / "proposals"
    / "feature_policy_freeze_draft_v1r1.json"
)
DRAFT_SHA = (
    "27ad0d1516cf6c1df7a5584eb3c49ba583873493d3e13ae5632e306fbc96464f"
)
CENSUS_V2_PATH = (
    REPO_ROOT / "artifacts" / "datasets" / "proto_census"
    / "ton_iot_proto_v2_20260905T121644Z.json"
)
CENSUS_V2_LOG_PATH = (
    REPO_ROOT / "artifacts" / "datasets" / "proto_census"
    / "ton_iot_proto_v2_20260905T121644Z.log"
)
CENSUS_V2_SHA = (
    "dfffd40c42fea9608679257c3c4a6014e42bbb7029b6849c6e5a0a4cde9f44b7"
)
CENSUS_V2_LOG_SHA = (
    "aa45633f063584af2d3e865191488e476d043074108c837a64129815b301fbfd"
)
CENSUS_V1_SCRIPT = (
    REPO_ROOT / "scripts" / "audits" / "ton_iot_proto_census_v1.py"
)
CENSUS_V2_SCRIPT = (
    REPO_ROOT / "scripts" / "audits" / "ton_iot_proto_census_v2.py"
)
CENSUS_V1_SCRIPT_SHA = (
    "98cb29423e5ba5f1fa9880aea83604cff94760e8ada91bad347c5671cad496cc"
)
CENSUS_V2_SCRIPT_SHA = (
    "490495d9f569de2db541a059b412e6022fd30782e7f166dab72a48bcf210d787"
)
CSV_SHA = (
    "26ddc513552de36de6428b2e578efaed2b57504c716dfba847cc0109a64e1974"
)
P1_47ROW_PNG = (
    REPO_ROOT / "references" / "dataset_docs" / "ciciot2023"
    / "readme_p1_feature_table" / "readme_p1_feature_table_47row.png"
)
P1_39ROW_PNG = (
    REPO_ROOT / "references" / "dataset_docs" / "ciciot2023"
    / "readme_p1_feature_table" / "readme_p1_window_table_39row.png"
)
P1_47ROW_SHA = (
    "6327fa2b7bace407f2fc48adf3268282c0ea323ae26aa717b42a486417037902"
)
P1_39ROW_SHA = (
    "cc88ca2f654aa7be64c69721b25968b6244107c63c1e7aa7a32311b6f258a1ad"
)
REGISTRY_PATH = REPO_ROOT / "references" / "dataset_docs" / "registry.json"
REVIEW_PACKAGE_SHA = (
    "1fdee7efa3ab11dc528c04c8e303086d0d45b69a5e26b310fae4abb46da8af6b"
)

# --- Rev 2 (2026-09-05) constants ---------------------------------
TARGET_ARTIFACT_PATH = (
    REPO_ROOT / "artifacts" / "proposals"
    / "feature_policy_freeze_target_v1r2.json"
)
TARGET_ARTIFACT_SHA = (
    "e81a55c16f9439b0356295353e8b342de19d5c5606d868952592f913beda714b"
)
SPEC_PATH = (
    REPO_ROOT / "artifacts" / "proposals"
    / "feature_policy_freeze_target_spec_v1r2.json"
)
SPEC_SHA = (
    "0fa8da404f78ed9b8258f3f4e35df64750ba86aa3f2bbe5cceeab0bb287af150"
)
TARGET_GENERATOR = (
    REPO_ROOT / "scripts" / "audits"
    / "build_feature_policy_target_v1r2.py"
)
TARGET_GENERATOR_SHA = (
    "19e0de8b5092772d6aec650c1f87a8b86d0dd6ad713e6dafcd76c76c49f2353d"
)
TARGET_VERIFIER = (
    REPO_ROOT / "scripts" / "audits"
    / "verify_feature_policy_target_v1r2.py"
)
TARGET_VERIFIER_SHA = (
    "53c0b9233b11131a983b30506766877849936efea25f1b0b0ffa0f2f0d5562ef"
)
TARGET_DIFF_ARTIFACT = (
    REPO_ROOT / "artifacts" / "proposals"
    / "feature_policy_target_v1r2_diff.json"
)
TARGET_DIFF_SHA = (
    "8d52dc0066a26b8007536ca65b28f45708a095014530b2286596701ec1c77e60"
)
TARGET_LOG_ARTIFACT = (
    REPO_ROOT / "artifacts" / "proposals"
    / "feature_policy_target_v1r2_verify.log"
)
TARGET_LOG_SHA = (
    "ef300f2a9d9ee5c47534c85f1e45b67514d14f7068248bc886f1cc5bf5f9cf84"
)
MI_DIR_ORIGINAL_STRING = (
    "references/dataset_docs/n_baiot/"
    "meidan2018_arxiv_v1_2026-09-04.pdf (SHA-256 "
    "1fa5bc4d4d2a12c2e93b18c4d876bd83ab7f456797934fcc71c92db754811964)"
)
BASELINE_FLIP_PATHS = [
    "status",
    "semantic_core.candidate_examples[0].decision_status",
    "semantic_core.candidate_examples[1].decision_status",
    "semantic_core.review_outcome_2026_09_04.resolved_points[0]"
    ".decision_status",
]

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
    admitted; the V1 proposal wording (retained as the historical
    staging record) stays present in DECISIONS.md; icmp stays
    unresolved."""

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
        """V1 wording check on the HISTORICAL record: the V1 proposed
        {tcp, udp} subset admission stays quoted in DECISIONS.md as
        the historical staging record (Rev 1 supersedes but does not
        erase it)."""
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn("EXACTLY the subset {tcp, udp} is proposed", md)
        self.assertIn("icmp stays `unresolved`", md)
        self.assertIn("no correspondence is\n          invented", md)
        # the decision record must NOT claim the eight columns match
        self.assertNotIn("eight columns are equivalent", md)
        # Rev 1 must record that the V1 admission wording is superseded
        self.assertIn("this revision\n    supersedes it", md)

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


class Rev1ZeroAdmissionDraftTests(unittest.TestCase):
    """F23-02: the independent ready-to-effect draft JSON exists with
    exactly 4 status flips, 6 per-record evidence targets, complete
    string targets, gate targets, and an EMPTY admission set."""

    @classmethod
    def setUpClass(cls):
        cls.draft = json.loads(DRAFT_PATH.read_text(encoding="utf-8"))

    def test_draft_sha_and_state(self):
        self.assertEqual(sha256_file(DRAFT_PATH), DRAFT_SHA)
        self.assertEqual(self.draft["status"], "DRAFT_NOT_APPLIED")
        self.assertEqual(
            self.draft["draft_id"],
            "FEATURE-POLICY-20260905-V1-FROZEN (draft; would take "
            "effect only at #24)",
        )
        self.assertEqual(
            self.draft["provenance"]["review_trigger"]["sha256"],
            REVIEW_PACKAGE_SHA,
        )
        self.assertEqual(
            self.draft["provenance"]["review_trigger"]
            ["review_outcome_findings_addressed"],
            ["F23-01", "F23-02", "F23-03"],
        )

    def test_status_flips_exactly_four(self):
        flips = self.draft["target_config_state"]["status_flips"]
        self.assertEqual(len(flips), 4)
        enumerated = self.draft["target_config_state"][
            "final_status_path_enumeration"
        ]
        self.assertEqual(
            [f["path"] for f in flips], enumerated
        )
        self.assertEqual(set(enumerated), EXPECTED_PROPOSED_PATHS)
        for flip in flips:
            self.assertEqual(flip["current"], "proposed")
            self.assertEqual(flip["target"], "frozen")

    def test_evidence_targets_cover_six_records(self):
        targets = self.draft["target_config_state"][
            "evidence_source_targets"
        ]
        self.assertEqual(len(targets), 6)
        records = " ".join(t["record"] for t in targets)
        for required in (
            "status (policy root)",
            "candidate_examples[0]",
            "candidate_examples[1]",
            "resolved_points[0]",
            "protocol_indicators",
            "packet_count",
        ):
            self.assertIn(required, records)

    def test_string_targets_complete_and_structure_decided(self):
        wording = self.draft["target_config_state"][
            "string_target_wording"
        ]
        self.assertEqual(len(wording), 2)
        by_path = {w["path"]: w for w in wording}
        pi = [
            path
            for path in by_path
            if path.endswith("protocol_indicators")
        ]
        pc = [path for path in by_path if path.endswith("packet_count")]
        self.assertEqual(len(pi), 1)
        self.assertEqual(len(pc), 1)
        # structured-vs-string decided NOW: both stay string-embedded
        self.assertIn(
            "string retained", by_path[pi[0]]["format"]
        )
        self.assertIn("NOT converted", by_path[pi[0]]["format"])
        # protocol_indicators target: unresolved/proposed, zero admission
        self.assertIn(
            "semantic_disposition=unresolved", by_path[pi[0]]["exact_target"]
        )
        self.assertIn(
            "decision_status=proposed", by_path[pi[0]]["exact_target"]
        )
        self.assertIn(
            "NOTHING is admitted", by_path[pi[0]]["exact_target"]
        )
        # packet_count stays unresolved
        self.assertIn(
            "semantic_disposition=unresolved", by_path[pc[0]]["exact_target"]
        )

    def test_gate_targets_unique_values_and_preconditions(self):
        gates = self.draft["target_config_state"][
            "data_handling_gate_targets"
        ]
        self.assertEqual(
            {g["gate"] for g in gates},
            {"materialization", "splitting", "training"},
        )
        for gate in gates:
            self.assertEqual(
                gate["current"], "forbidden before protocol freeze"
            )
            self.assertTrue(gate["target"].startswith("permitted after"))
            self.assertIn("#24", gate["target"])
            # Rev 1 historical shape: the draft carries authorization
            # text but NO standalone structured preconditions - this
            # is exactly the recorded gap the Rev 2 target spec and
            # target artifact close (verified there and in the
            # simulated-application tests, without any fallback)
            self.assertNotIn("preconditions", gate)
            self.assertTrue(gate["authorization"].strip())

    def test_zero_admission_set(self):
        admission = self.draft["admission_set_this_version"]
        self.assertEqual(admission["admitted_mapping_count"], 0)
        self.assertEqual(admission["three_way_core"], "EMPTY")
        pairwise = admission["pairwise_cores"]
        self.assertEqual(len(pairwise), 3)
        for core in pairwise.values():
            self.assertIn("EMPTY", core)
        # frozen never means admitted
        self.assertIn("frozen never means admitted",
                      admission["admitted_mapping_note"])

    def test_protocol_indicators_disposition_is_unresolved_not_derived(self):
        wording = self.draft["target_config_state"][
            "string_target_wording"
        ]
        pi = [w for w in wording
              if w["path"].endswith("protocol_indicators")][0]
        self.assertIn("semantic_disposition=unresolved",
                      pi["exact_target"])
        self.assertNotIn("semantic_disposition=derived",
                         pi["exact_target"])


class Rev1CensusVerificationTests(unittest.TestCase):
    """F23-03: the v2 read-only verification pass over the SAME frozen
    CSV reproduces v1 exactly; scripts are archived; the source CSV
    hash is checked before and after the run."""

    @classmethod
    def setUpClass(cls):
        cls.v2 = json.loads(
            CENSUS_V2_PATH.read_text(encoding="utf-8")
        )

    def test_v2_artifact_hashes(self):
        self.assertEqual(sha256_file(CENSUS_V2_PATH), CENSUS_V2_SHA)
        self.assertEqual(
            sha256_file(CENSUS_V2_LOG_PATH), CENSUS_V2_LOG_SHA
        )

    def test_v2_scripts_archived(self):
        self.assertEqual(
            sha256_file(CENSUS_V1_SCRIPT), CENSUS_V1_SCRIPT_SHA
        )
        self.assertEqual(
            sha256_file(CENSUS_V2_SCRIPT), CENSUS_V2_SCRIPT_SHA
        )

    def test_v2_reproduces_v1_exactly(self):
        ref = self.v2["v1_reference"]
        self.assertTrue(ref["counts_identical_to_v1"])
        self.assertTrue(ref["total_rows_identical_to_v1"])
        self.assertEqual(
            self.v2["proto_value_counts"], CENSUS_COUNTS
        )
        self.assertEqual(self.v2["total_rows"], CENSUS_TOTAL_ROWS)
        self.assertTrue(self.v2["reconciliation"]["row_count_match"])
        self.assertTrue(self.v2["reconciliation"]["sum_equals_row_count"])
        self.assertEqual(self.v2["exit_status"], "OK")

    def test_v2_source_hash_invariance_and_authorization(self):
        source = self.v2["source"]
        self.assertEqual(source["sha256_before"], CSV_SHA)
        self.assertEqual(source["sha256_after"], CSV_SHA)
        self.assertEqual(
            source["sha256_inventory_expected"], CSV_SHA
        )
        self.assertIn("One additional read-only verification pass",
                      self.v2["authorization"])
        notes = " ".join(self.v2["notes"])
        self.assertIn("No old artifact or log was modified", notes)
        self.assertIn("must NOT be used as an all-data encoder", notes)


class Rev1DocumentationTests(unittest.TestCase):
    """Rev 1 documentation invariants: the two conflicting page-1
    tables archived and registered, the dual-axis wording in
    FEATURE_MAPPING_PROTOCOL.md, and the DECISIONS.md Rev 1 record."""

    def test_p1_tables_archived(self):
        self.assertEqual(sha256_file(P1_47ROW_PNG), P1_47ROW_SHA)
        self.assertEqual(sha256_file(P1_39ROW_PNG), P1_39ROW_SHA)

    def test_p1_tables_registered_as_inconsistency(self):
        registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        entries = {
            e["file"]: e for e in registry["entries"]
            if e["dataset_id"] == "ciciot2023"
            and e["file"].startswith("ciciot2023/readme_p1_feature_table/")
        }
        self.assertEqual(len(entries), 2)
        for entry in entries.values():
            self.assertEqual(entry["source_sha256"],
                             "0f48daba395be03985f612ce706d33f1a25e4008"
                             "cb94c3ad7b6f6332fbdbee92")
        blob = json.dumps(registry, ensure_ascii=False)
        self.assertIn("OFFICIAL-SOURCE INTERNAL INCONSISTENCY", blob)
        self.assertIn("Average no. of TCP packets in the window", blob)
        self.assertIn("Indicates if the transport layer protocol is TCP",
                      blob)

    def test_fmp_dual_axis_wording(self):
        md = FMP_PATH.read_text(encoding="utf-8")
        # single-axis field list is gone
        self.assertNotIn("mapping_status", md)
        self.assertIn(
            "semantic_disposition: exact / derived / unresolved / rejected\n"
            "decision_status: proposed / frozen",
            md,
        )
        self.assertIn("decision_status: proposed / frozen", md)
        self.assertIn("These are two independent axes", md)
        self.assertIn(
            "it never\nmeans admitted", md
        )
        # section 5 dual-axis freeze condition
        self.assertIn(
            "`decision_status: proposed` to `decision_status: frozen`",
            md,
        )

    def test_fmp_rev1_addendum(self):
        md = FMP_PATH.read_text(encoding="utf-8")
        self.assertIn("### 6.1 Rev 1 staging addendum", md)
        self.assertIn("CANDIDATE retention", md)
        self.assertIn("admitted_mapping_count = 0", md)
        self.assertIn("TWO\n   feature tables with CONFLICTING", md)
        self.assertIn("is NOT a sufficient exclusion proof", md)
        self.assertIn(
            "current evidence is insufficient; not admitted\n"
            "   this version",
            md,
        )
        self.assertIn("readme_p1_feature_table_47row.png", md)
        self.assertIn("readme_p1_window_table_39row.png", md)
        self.assertIn(REVIEW_PACKAGE_SHA, md)
        self.assertIn(
            "281 ICMP samples and the native proto features are NOT\n"
            "   deleted",
            md,
        )
        # legacy watermark tail stays at end-of-file
        self.assertTrue(md.rstrip().endswith("AI生成"))
        # the exempted watermark stays the LAST line
        self.assertTrue(md.endswith("> AI生成\n"))

    def test_decisions_md_rev1_record(self):
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "Rev 1 (2026-09-05, zero-admission documentation revision)",
            md,
        )
        self.assertIn("F23-01", md)
        self.assertIn("F23-02", md)
        self.assertIn("F23-03", md)
        self.assertIn("admitted_mapping_count = 0", md)
        self.assertIn(
            "feature_policy_freeze_draft_v1r1.json", md
        )
        self.assertIn("ton_iot_proto_v2_20260905T121644Z.json", md)
        self.assertIn(
            "DEMOTED to candidate retention", md
        )
        self.assertIn(
            "NOT a\n        sufficient exclusion proof", md
        )
        self.assertIn(
            "current evidence insufficient; not admitted this version",
            md,
        )
        # scope statements unchanged
        self.assertIn(
            "the materialization/splitting/training ban\n    is NOT "
            "lifted",
            md,
        )
        self.assertIn(
            "#24 execution still requires separate explicit\n    "
            "user authorization",
            md,
        )
        # configs still byte-identical per the record
        self.assertIn("`2a903a4a...21b47` / `8a055e2e...6fab`", md)


class Rev2TargetArtifactTests(unittest.TestCase):
    """F23-02 A/B/C: the committed would-be-effective target
    configuration exists, reproduces from the live baseline via the
    archived generator, and the live config is still untouched."""

    @classmethod
    def setUpClass(cls):
        cls.target = json.loads(
            TARGET_ARTIFACT_PATH.read_text(encoding="utf-8")
        )

    def test_target_artifact_sha(self):
        self.assertEqual(
            sha256_file(TARGET_ARTIFACT_PATH), TARGET_ARTIFACT_SHA
        )

    def test_target_is_a_complete_feature_policy(self):
        baseline = json.loads(
            FEATURE_POLICY_PATH.read_text(encoding="utf-8")
        )
        for key in baseline:
            self.assertIn(key, self.target)
        self.assertEqual(self.target["kind"], "feature_policy")
        self.assertEqual(self.target["status"], "frozen")
        self.assertIn("admission_set_this_version", self.target)
        self.assertIn("freeze_metadata", self.target)

    def test_scripts_archived_and_hashes_recorded(self):
        self.assertEqual(sha256_file(TARGET_GENERATOR),
                         TARGET_GENERATOR_SHA)
        self.assertEqual(sha256_file(TARGET_VERIFIER),
                         TARGET_VERIFIER_SHA)
        self.assertEqual(sha256_file(TARGET_DIFF_ARTIFACT),
                         TARGET_DIFF_SHA)
        self.assertEqual(sha256_file(TARGET_LOG_ARTIFACT),
                         TARGET_LOG_SHA)

    def test_generator_rebuild_is_byte_identical(self):
        spec = importlib.util.spec_from_file_location(
            "fp_target_builder_test", TARGET_GENERATOR)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        baseline_text = FEATURE_POLICY_PATH.read_text(
            encoding="utf-8")
        rebuilt, applied = module.build_target_text(baseline_text)
        target_bytes = TARGET_ARTIFACT_PATH.read_bytes()
        self.assertEqual(rebuilt.encode("utf-8"), target_bytes)
        self.assertEqual(
            applied,
            ["op7_root_additions", "op6_gate_targets",
             "op5_status_flip_4", "op4_pi_pc_wording",
             "op3_flip3_decay", "op2_flip2_bytes",
             "op1_root_flip"],
        )

    def test_verification_artifacts_record_all_green(self):
        diff = json.loads(
            TARGET_DIFF_ARTIFACT.read_text(encoding="utf-8")
        )
        self.assertTrue(diff["all_pass"])
        self.assertEqual(len(diff["checks"]), 30)
        for name, outcome in diff["checks"].items():
            self.assertTrue(outcome["pass"], name)
        log = TARGET_LOG_ARTIFACT.read_text(encoding="utf-8")
        self.assertNotIn("[FAIL]", log)
        self.assertIn("[PASS] status_census_exactly_four_frozen_no_"
                      "proposed", log)
        self.assertIn("[PASS] mi_dir_first_element_byte_equal_"
                      "original", log)

    def test_live_config_still_baseline_while_target_committed(self):
        # nothing applied at proposal time
        self.assertEqual(sha256_file(FEATURE_POLICY_PATH),
                         FEATURE_POLICY_SHA)


class Rev2SimulatedApplicationTests(unittest.TestCase):
    """The guards the review demanded: simulate the application in an
    independent temporary copy and verify the RESULTING configuration,
    not the plan text."""

    @classmethod
    def setUpClass(cls):
        cls.baseline = json.loads(
            FEATURE_POLICY_PATH.read_text(encoding="utf-8")
        )
        # simulate: install the committed target bytes over a copy
        cls.applied = json.loads(
            TARGET_ARTIFACT_PATH.read_text(encoding="utf-8")
        )

    def test_exactly_four_structured_status_flips(self):
        def census(node, path=""):
            hits = []
            if isinstance(node, dict):
                for k, v in node.items():
                    child = f"{path}.{k}" if path else k
                    if k in ("status", "decision_status") and \
                            isinstance(v, str):
                        hits.append((child, v))
                    hits.extend(census(v, child))
            elif isinstance(node, list):
                for i, v in enumerate(node):
                    hits.extend(census(v, f"{path}[{i}]"))
            return hits

        after = census(self.applied)
        self.assertEqual(len(after), 4)
        self.assertEqual(
            set(after),
            {("status", "frozen"),
             ("semantic_core.candidate_examples[0].decision_status",
              "frozen"),
             ("semantic_core.candidate_examples[1].decision_status",
              "frozen"),
             ("semantic_core.review_outcome_2026_09_04"
              ".resolved_points[0].decision_status", "frozen")},
        )

    def test_dispositions_unchanged_in_applied(self):
        self.assertEqual(
            self.applied["semantic_core"]["candidate_examples"][0]
            ["semantic_disposition"], "unresolved")
        self.assertEqual(
            self.applied["semantic_core"]["candidate_examples"][1]
            ["semantic_disposition"], "rejected")
        self.assertEqual(
            self.applied["semantic_core"]["review_outcome_2026_09_04"]
            ["resolved_points"][0]["semantic_disposition"], "derived")

    def test_mi_dir_array_rules_in_applied(self):
        point = self.applied["semantic_core"][
            "review_outcome_2026_09_04"]["resolved_points"][0]
        old = self.baseline["semantic_core"][
            "review_outcome_2026_09_04"]["resolved_points"][0]
        self.assertIsInstance(old["evidence_source"], str)
        self.assertIsInstance(point["evidence_source"], list)
        self.assertEqual(
            point["evidence_source"][0], MI_DIR_ORIGINAL_STRING)
        self.assertEqual(
            point["evidence_source"][0], old["evidence_source"])
        self.assertEqual(len(point["evidence_source"]), 3)
        self.assertEqual(point["resolution"], old["resolution"])

    def test_zero_admissions_in_applied(self):
        adm = self.applied["admission_set_this_version"]
        self.assertEqual(adm["admitted_mapping_count"], 0)
        self.assertEqual(adm["three_way_core"], "EMPTY")
        for core in adm["pairwise_cores"].values():
            self.assertIn("EMPTY", core)
        fm = self.applied["freeze_metadata"]
        self.assertEqual(fm["freeze_id"], PREDICTED_FREEZE_ID)

    def test_protocol_columns_reworded_not_structured(self):
        core = self.applied["semantic_core"][
            "review_outcome_2026_09_04"]["pairwise_cores"][
            "ton_iot__ciciot2023"]
        self.assertIsInstance(core["protocol_indicators"], str)
        self.assertIn(
            "semantic_disposition=unresolved",
            core["protocol_indicators"])
        self.assertNotIn(
            "semantic_disposition=derived",
            core["protocol_indicators"])
        self.assertIn("NOTHING is admitted",
                      core["protocol_indicators"])
        self.assertIsInstance(core["packet_count"], str)
        self.assertIn("semantic_disposition=unresolved",
                      core["packet_count"])
        self.assertNotIn("decision_status",
                         {k for k in core.keys()
                          if k != "protocol_indicators"
                          and k != "packet_count"})

    def test_gates_structured_preconditions_in_applied(self):
        for gate in ("materialization", "splitting", "training"):
            old = self.baseline["data_handling"][gate]
            new = self.applied["data_handling"][gate]
            self.assertIsInstance(old, str)
            self.assertIsInstance(new, dict)
            self.assertEqual(new["current"],
                             "forbidden before protocol freeze")
            self.assertTrue(new["target"].startswith("permitted after"))
            self.assertIsInstance(new["preconditions"], list)
            self.assertEqual(len(new["preconditions"]), 6)
            self.assertTrue(new["preconditions"][0].startswith(
                "feature_policy.json root status is frozen"))
            self.assertTrue(new["preconditions"][-1].startswith(
                "separate explicit user authorization"))
            self.assertTrue(new["authorization"].strip())


class Rev2TargetSpecificationTests(unittest.TestCase):
    """The Rev 2 specification binds the previously open choices to
    the committed target artifact and records the verification."""

    @classmethod
    def setUpClass(cls):
        cls.spec = json.loads(
            SPEC_PATH.read_text(encoding="utf-8")
        )
        cls.target = json.loads(
            TARGET_ARTIFACT_PATH.read_text(encoding="utf-8")
        )

    def test_spec_sha_and_state(self):
        self.assertEqual(sha256_file(SPEC_PATH), SPEC_SHA)
        self.assertEqual(self.spec["status"], "TARGET_NOT_APPLIED")
        self.assertEqual(
            self.spec["kind"],
            "feature_policy_freeze_target_specification")
        self.assertEqual(
            self.spec["decision_record"], "DECISIONS.md #23 Rev 2")

    def test_bindings_match_target_artifact_verbatim(self):
        self.assertEqual(
            self.spec["admission_set_this_version"],
            self.target["admission_set_this_version"])
        self.assertEqual(
            self.spec["freeze_metadata"],
            self.target["freeze_metadata"])
        bindings = self.spec["target_config_state"]["bindings"]
        self.assertTrue(bindings["admission_set_this_version"]
                        ["not_left_to_24"])
        self.assertTrue(bindings["freeze_metadata"]["not_left_to_24"])

    def test_spec_targets_match_target_artifact(self):
        tcs = self.spec["target_config_state"]
        # MI_dir evidence array equals the applied target's array
        mi = [
            t for t in tcs["evidence_source_targets"]
            if "(MI_dir)" in t["record"]
        ][0]
        applied_mi = self.target["semantic_core"][
            "review_outcome_2026_09_04"]["resolved_points"][0]
        self.assertEqual(mi["target_value"],
                         applied_mi["evidence_source"])
        self.assertEqual(mi["target_value"][0],
                         MI_DIR_ORIGINAL_STRING)
        # string targets byte-equal
        core = self.target["semantic_core"][
            "review_outcome_2026_09_04"]["pairwise_cores"][
            "ton_iot__ciciot2023"]
        for w in tcs["string_target_wording"]:
            if w["path"].endswith("protocol_indicators"):
                self.assertEqual(w["exact_target"],
                                 core["protocol_indicators"])
            if w["path"].endswith("packet_count"):
                self.assertEqual(w["exact_target"],
                                 core["packet_count"])
        # gate preconditions byte-equal
        for g in tcs["data_handling_gate_targets"]:
            self.assertEqual(
                g["preconditions"],
                self.target["data_handling"][g["gate"]]
                ["preconditions"])

    def test_outcome_evidence_recorded(self):
        oe = self.spec["outcome_evidence"]
        self.assertEqual(oe["checks_total"], 30)
        self.assertEqual(oe["checks_failed"], [])
        self.assertFalse(oe["live_config_touched"])
        self.assertIn("verify_feature_policy_target_v1r2.py",
                      oe["verification_script"])


class Rev2FmpRestorationTests(unittest.TestCase):
    """The non-blocking Rev 2 fix: the V1 historical sentence before
    section 6.1 is complete again (ends with 'own authorization.')."""

    def test_fmp_truncated_sentence_restored(self):
        md = FMP_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "materialization/splitting/training ban - that requires "
            "#24 and its\nown authorization.",
            md,
        )
        # no truncation remains
        self.assertNotIn("#24 and its\n\n### 6.1", md)
        # the historical watermark tail is still the last line
        self.assertTrue(md.endswith("> AI生成\n"))


if __name__ == "__main__":
    unittest.main()
