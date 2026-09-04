import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LABEL_ONTOLOGY_PATH = REPO_ROOT / "config" / "label_ontology.json"

EXPECTED_ATTACK_TYPES = [
    "backdoor", "ddos", "dos", "injection",
    "password", "ransomware", "scanning", "xss", "mitm",
]

VALID_DISPOSITIONS = ["exact", "derived", "unresolved", "rejected"]
VALID_DECISION_STATUSES = ["proposed", "frozen"]


def load_label_ontology():
    with LABEL_ONTOLOGY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


class TonIotTypeMappingTests(unittest.TestCase):
    """Tests for the TON-IoT 9 attack classes → canonical_family mapping.

    Verifies that:
    - All 9 attack types from the census are present.
    - normal → benign is recorded as the coverage invariant.
    - Each entry has the required fields with valid enum values.
    - No legacy mapping_status key remains.
    """

    def setUp(self):
        self.ontology = load_label_ontology()
        self.mapping = self.ontology["canonical_family"]["ton_iot_type_mapping"]
        self.entries = {
            e["source_type"]: e for e in self.mapping["entries"]
        }

    def test_all_nine_attack_types_present(self):
        for attack_type in EXPECTED_ATTACK_TYPES:
            self.assertIn(attack_type, self.entries, f"missing {attack_type}")

    def test_normal_benign_invariant_present(self):
        self.assertIn("normal", self.entries)
        normal = self.entries["normal"]
        self.assertEqual(normal["canonical_family"], "benign")

    def test_total_entry_count_is_ten(self):
        self.assertEqual(len(self.mapping["entries"]), 10)

    def test_each_entry_has_required_fields(self):
        required = [
            "source_type", "canonical_family", "semantic_disposition",
            "decision_status", "evidence_source", "rationale",
        ]
        for entry in self.mapping["entries"]:
            for field in required:
                self.assertIn(field, entry, f"missing {field} in {entry['source_type']}")

    def test_each_entry_has_valid_disposition_and_decision(self):
        for entry in self.mapping["entries"]:
            self.assertIn(
                entry["semantic_disposition"], VALID_DISPOSITIONS,
                f"invalid disposition in {entry['source_type']}",
            )
            self.assertIn(
                entry["decision_status"], VALID_DECISION_STATUSES,
                f"invalid decision_status in {entry['source_type']}",
            )

    def test_all_decision_statuses_are_proposed(self):
        for entry in self.mapping["entries"]:
            self.assertEqual(
                entry["decision_status"], "proposed",
                f"{entry['source_type']} is not proposed",
            )

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

    def test_scanning_maps_to_recon_not_recon_label(self):
        """scanning → recon is a derived mapping; the name differs by design."""
        self.assertEqual(self.entries["scanning"]["canonical_family"], "recon")
        self.assertEqual(self.entries["scanning"]["semantic_disposition"], "derived")

    def test_xss_maps_to_web_attack(self):
        self.assertEqual(self.entries["xss"]["canonical_family"], "web_attack")
        self.assertEqual(self.entries["xss"]["semantic_disposition"], "derived")

    def test_mitm_is_independent_family(self):
        self.assertEqual(self.entries["mitm"]["canonical_family"], "mitm")
        self.assertEqual(self.entries["mitm"]["semantic_disposition"], "exact")

    def test_no_legacy_mapping_status_in_binary_label(self):
        """binary_label derivation entries must use the new dual-dimension fields."""
        for dataset, entry in self.ontology["binary_label"]["derivation"].items():
            self.assertNotIn("mapping_status", entry, f"legacy key in binary_label.{dataset}")
            self.assertIn("semantic_disposition", entry)
            self.assertIn("decision_status", entry)


if __name__ == "__main__":
    unittest.main()
