import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LABEL_ONTOLOGY_PATH = REPO_ROOT / "config" / "label_ontology.json"

EXPECTED_ATTACK_TYPES = [
    "backdoor", "ddos", "dos", "injection",
    "password", "ransomware", "scanning", "xss", "mitm",
]

# Complete expected mapping table: source_type -> (canonical_family,
# semantic_disposition). Every entry must also carry
# decision_status == "proposed". This locks the entire mapping, so a
# wrong assignment (e.g. ddos -> ransomware) fails even when both names
# are individually valid families.
EXPECTED_MAPPING = {
    "normal": ("benign", "exact"),
    "backdoor": ("backdoor", "exact"),
    "ddos": ("ddos", "exact"),
    "dos": ("dos", "exact"),
    "injection": ("injection", "exact"),
    "password": ("password", "exact"),
    "ransomware": ("ransomware", "exact"),
    "scanning": ("recon", "derived"),
    "xss": ("web_attack", "derived"),
    "mitm": ("mitm", "exact"),
}

VALID_DISPOSITIONS = ["exact", "derived", "unresolved", "rejected"]
VALID_DECISION_STATUSES = ["proposed", "frozen"]


def load_label_ontology():
    with LABEL_ONTOLOGY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


class TonIotTypeMappingTests(unittest.TestCase):
    """Tests for the TON-IoT 9 attack classes -> canonical_family mapping."""

    def setUp(self):
        self.ontology = load_label_ontology()
        self.mapping = self.ontology["canonical_family"]["ton_iot_type_mapping"]
        self.entries = {
            e["source_type"]: e for e in self.mapping["entries"]
        }

    def test_full_expected_mapping_table(self):
        """Every source_type must map to exactly the expected family
        and disposition; all 10 entries are FROZEN as
        TON-IOT-TYPE-MAPPING-20260904-V1-FROZEN."""
        self.assertEqual(
            set(self.entries.keys()), set(EXPECTED_MAPPING.keys()),
            "entry set differs from the expected 10-entry table",
        )
        for source_type, (family, disposition) in EXPECTED_MAPPING.items():
            entry = self.entries[source_type]
            self.assertEqual(
                entry["canonical_family"], family,
                f"{source_type}: family is {entry['canonical_family']}, expected {family}",
            )
            self.assertEqual(
                entry["semantic_disposition"], disposition,
                f"{source_type}: disposition is {entry['semantic_disposition']}, expected {disposition}",
            )
            self.assertEqual(
                entry["decision_status"], "frozen",
                f"{source_type}: decision_status is not frozen",
            )

    def test_all_decision_statuses_are_frozen(self):
        """All 10 TON-IoT mapping entries must carry
        decision_status == "frozen" (TON-IOT-TYPE-MAPPING-20260904-V1-FROZEN)."""
        self.assertEqual(len(self.mapping["entries"]), 10)
        for entry in self.mapping["entries"]:
            self.assertEqual(
                entry["decision_status"], "frozen",
                f"{entry['source_type']}: decision_status is not frozen",
            )

    def test_freeze_metadata_recorded_in_description(self):
        """The mapping-level description must record the freeze
        identifier, the evidence v3 ZIP SHA-256, and the source commit."""
        description = self.mapping["description"]
        self.assertIn(
            "TON-IOT-TYPE-MAPPING-20260904-V1-FROZEN", description,
            "description lacks the freeze identifier",
        )
        self.assertIn(
            "f774457585db719bc223a89cc965aabef7019bec1f0f6209a0ce160e3a4eecc4",
            description,
            "description lacks the evidence v3 ZIP SHA-256",
        )
        self.assertIn(
            "b95e7bc", description,
            "description lacks the source commit",
        )

    def test_all_nine_attack_types_present(self):
        for attack_type in EXPECTED_ATTACK_TYPES:
            self.assertIn(attack_type, self.entries, f"missing {attack_type}")

    def test_normal_benign_invariant_present(self):
        normal = self.entries["normal"]
        self.assertEqual(normal["canonical_family"], "benign")
        self.assertEqual(normal["semantic_disposition"], "exact")

    def test_each_entry_has_required_fields(self):
        required = [
            "source_type", "canonical_family", "semantic_disposition",
            "decision_status", "evidence_source", "rationale",
        ]
        for entry in self.mapping["entries"]:
            for field in required:
                self.assertIn(field, entry, f"missing {field} in {entry['source_type']}")

    def test_evidence_and_rationale_nonempty(self):
        for entry in self.mapping["entries"]:
            self.assertTrue(entry["evidence_source"].strip())
            self.assertTrue(entry["rationale"].strip())

    def test_no_legacy_mapping_status_in_entries(self):
        for entry in self.mapping["entries"]:
            self.assertNotIn("mapping_status", entry)

    def test_coverage_invariant_recorded(self):
        inv = self.mapping["coverage_invariant"]
        self.assertIn("rule", inv)
        self.assertIn("evidence_source", inv)
        self.assertIn("TON-IOT-LABEL-CENSUS-20260903-V1-VERIFIED", inv["evidence_source"])

    def test_candidate_families_includes_all_mapped_families(self):
        candidates = set(self.ontology["canonical_family"]["candidate_families"])
        for entry in self.mapping["entries"]:
            self.assertIn(
                entry["canonical_family"], candidates,
                f"canonical_family {entry['canonical_family']} not in candidate_families",
            )

    def test_fixed_decision_families_in_candidate_families(self):
        """Every fixed_decision's canonical_family must be listed in
        candidate_families (regression guard: bashlite was once omitted)."""
        candidates = set(self.ontology["canonical_family"]["candidate_families"])
        for decision in self.ontology["canonical_family"]["fixed_decisions"]:
            self.assertIn(
                decision["canonical_family"], candidates,
                f"fixed decision family {decision['canonical_family']} "
                "missing from candidate_families",
            )

    def test_candidate_family_count_is_twelve(self):
        candidates = self.ontology["canonical_family"]["candidate_families"]
        self.assertEqual(len(candidates), 12)
        self.assertEqual(len(set(candidates)), 12, "duplicates in candidate_families")
        self.assertIn("bashlite", candidates)

    def test_mitm_rationale_acknowledges_ciciot2023_mitm_arp_spoofing(self):
        """The mitm rationale must not claim 'no other dataset carries
        mitm' (CICIoT2023 ships MITM-ArpSpoofing); it must instead defer
        cross-dataset comparison to the CICIoT2023 mapping freeze."""
        rationale = self.entries["mitm"]["rationale"]
        self.assertNotIn(
            "no other dataset in this study carries an mitm family", rationale,
        )
        self.assertIn("MITM-ArpSpoofing", rationale)
        self.assertIn("Spoofing category", rationale)
        self.assertIn("until the CICIoT2023 mapping freeze", rationale)

    def test_fixed_decisions_carry_dual_dimensions(self):
        """Each fixed decision must carry semantic_disposition and
        decision_status with valid enum values, plus a non-empty
        evidence_source (regression guard for the gafgyt -> bashlite
        entry that once lacked all three)."""
        decisions = self.ontology["canonical_family"]["fixed_decisions"]
        self.assertTrue(decisions)
        for decision in decisions:
            for field in ("semantic_disposition", "decision_status", "evidence_source"):
                self.assertIn(field, decision, f"{decision.get('source_family')} lacks {field}")
            self.assertIn(decision["semantic_disposition"], VALID_DISPOSITIONS)
            self.assertIn(decision["decision_status"], VALID_DECISION_STATUSES)
            self.assertTrue(decision["evidence_source"].strip())

    def test_bashlite_decision_is_exact_frozen_with_meidan_evidence(self):
        decisions = self.ontology["canonical_family"]["fixed_decisions"]
        bashlite = [d for d in decisions if d["canonical_family"] == "bashlite"]
        self.assertEqual(len(bashlite), 1)
        entry = bashlite[0]
        self.assertEqual(entry["semantic_disposition"], "exact")
        self.assertEqual(entry["decision_status"], "frozen")
        self.assertIn("Meidan", entry["evidence_source"])
        self.assertIn("also known as Gafgyt", entry["evidence_source"])

    def test_derived_entries_cite_ciciot2023_taxonomy(self):
        """The two derived mappings must cite the UNB CICIoT2023
        official taxonomy page as supporting evidence."""
        for source_type in ("scanning", "xss"):
            entry = self.entries[source_type]
            self.assertIn(
                "unb.ca/cic/datasets/iotdataset-2023.html",
                entry["evidence_source"],
                f"{source_type} evidence_source lacks the UNB CICIoT2023 taxonomy citation",
            )

    def test_exact_entries_use_identity_preserving_rationale(self):
        """Exact mappings for the 9 attack classes must not over-claim
        mechanisms beyond the cited evidence; they use the
        identity-preserving wording. (The normal entry is a census-backed
        coverage invariant, not an attack class, and is excluded.)"""
        for source_type, (_family, disposition) in EXPECTED_MAPPING.items():
            if disposition != "exact" or source_type == "normal":
                continue
            entry = self.entries[source_type]
            self.assertIn(
                "Identity-preserving mapping",
                entry["rationale"],
                f"{source_type} rationale lacks identity-preserving wording",
            )

    def test_cross_dataset_claims_are_conditional(self):
        """Positive cross-dataset comparison claims ("candidate for
        cross-dataset family comparison") must be conditional on a
        separate CICIoT2023 mapping freeze and subtype-coverage audit.
        Explicit negations ("no cross-dataset claim is made") are fine."""
        for entry in self.mapping["entries"]:
            rationale = entry["rationale"]
            if "cross-dataset family comparison" in rationale:
                self.assertIn(
                    "subject to separate CICIoT2023 mapping freeze", rationale,
                    f"{entry['source_type']} cross-dataset claim is not conditional",
                )
            self.assertNotIn(
                "genuine cross-dataset comparison",
                rationale,
                f"{entry['source_type']} claims genuine cross-dataset comparison",
            )


class OntologyWideKeyDisciplineTests(unittest.TestCase):
    """Recursive scan: no mapping_status key may remain at ANY level of
    label_ontology.json."""

    def test_no_mapping_status_key_anywhere(self):
        def walk(node, path=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    location = f"{path}.{key}" if path else key
                    self.assertNotEqual(
                        key, "mapping_status",
                        f"legacy key mapping_status found at {location}",
                    )
                    walk(value, location)
            elif isinstance(node, list):
                for index, item in enumerate(node):
                    walk(item, f"{path}[{index}]")

        walk(load_label_ontology())

    def test_canonical_family_root_uses_decision_status(self):
        cf = load_label_ontology()["canonical_family"]
        self.assertIn("decision_status", cf)
        self.assertIn(cf["decision_status"], VALID_DECISION_STATUSES)

    def test_ontology_root_and_canonical_family_remain_proposed(self):
        """The freeze covers ONLY the 10 ton_iot_type_mapping entries;
        the ontology root status and the canonical_family root
        decision_status must remain "proposed" until the CICIoT2023 and
        N-BaIoT mapping stages are frozen."""
        ontology = load_label_ontology()
        self.assertEqual(ontology["status"], "proposed")
        self.assertEqual(ontology["canonical_family"]["decision_status"], "proposed")

    def test_binary_label_derivation_uses_dual_dimensions(self):
        derivation = load_label_ontology()["binary_label"]["derivation"]
        for dataset, entry in derivation.items():
            self.assertNotIn("mapping_status", entry, f"legacy key in binary_label.{dataset}")
            self.assertIn("semantic_disposition", entry)
            self.assertIn("decision_status", entry)
            self.assertIn(entry["semantic_disposition"], VALID_DISPOSITIONS)
            self.assertIn(entry["decision_status"], VALID_DECISION_STATUSES)

    def test_binary_label_derivation_entries_remain_proposed(self):
        """binary_label derivation entries are NOT covered by the
        TON-IoT type-mapping freeze and must remain "proposed"."""
        derivation = load_label_ontology()["binary_label"]["derivation"]
        self.assertTrue(derivation)
        for dataset, entry in derivation.items():
            self.assertEqual(
                entry["decision_status"], "proposed",
                f"binary_label.{dataset}: decision_status is not proposed",
            )


if __name__ == "__main__":
    unittest.main()
