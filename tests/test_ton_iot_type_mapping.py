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
        and disposition; anything else fails."""
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
                entry["decision_status"], "proposed",
                f"{source_type}: decision_status is not proposed",
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

    def test_bashlite_fixed_decision_present(self):
        decisions = self.ontology["canonical_family"]["fixed_decisions"]
        self.assertTrue(
            any(d["canonical_family"] == "bashlite" for d in decisions)
        )

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

    def test_binary_label_derivation_uses_dual_dimensions(self):
        derivation = load_label_ontology()["binary_label"]["derivation"]
        for dataset, entry in derivation.items():
            self.assertNotIn("mapping_status", entry, f"legacy key in binary_label.{dataset}")
            self.assertIn("semantic_disposition", entry)
            self.assertIn("decision_status", entry)
            self.assertIn(entry["semantic_disposition"], VALID_DISPOSITIONS)
            self.assertIn(entry["decision_status"], VALID_DECISION_STATUSES)


if __name__ == "__main__":
    unittest.main()
