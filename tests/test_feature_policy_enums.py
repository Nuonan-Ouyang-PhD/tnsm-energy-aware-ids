import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
FEATURE_POLICY_PATH = REPO_ROOT / "config" / "feature_policy.json"

SEMANTIC_DISPOSITION_VALUES = ["exact", "derived", "unresolved", "rejected"]
DECISION_STATUS_VALUES = ["proposed", "frozen"]
REVIEW_DATE_KEY = "review_outcome_2026_09_04"


def load_feature_policy():
    with FEATURE_POLICY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


class MappingEnumerationTests(unittest.TestCase):
    """Enum-consistency tests for the semantic_core mapping records.

    The review verifier (2026-09-04) found that candidate mappings used
    mapping_status values outside the declared enum. The policy now
    separates semantic_disposition (exact/derived/unresolved/rejected)
    from decision_status (proposed/frozen); every mapping record must
    use both, and no legacy `mapping_status` key may remain.
    """

    def test_enums_are_declared(self):
        policy = load_feature_policy()
        core = policy["semantic_core"]
        self.assertEqual(
            sorted(core["semantic_disposition_values"]),
            sorted(SEMANTIC_DISPOSITION_VALUES),
        )
        self.assertEqual(
            sorted(core["decision_status_values"]), sorted(DECISION_STATUS_VALUES)
        )
        self.assertNotIn("mapping_status_values", core)

    def test_mapping_record_fields_declare_both_dimensions(self):
        policy = load_feature_policy()
        fields = policy["semantic_core"]["mapping_record_fields"]
        self.assertIn("semantic_disposition", fields)
        self.assertIn("decision_status", fields)
        self.assertNotIn("mapping_status", fields)

    def test_candidate_examples_use_both_dimensions_and_valid_enums(self):
        policy = load_feature_policy()
        examples = policy["semantic_core"]["candidate_examples"]
        self.assertGreaterEqual(len(examples), 2)
        for example in examples:
            self.assertIn("semantic_disposition", example)
            self.assertIn("decision_status", example)
            self.assertNotIn("mapping_status", example)
            self.assertIn(example["semantic_disposition"], SEMANTIC_DISPOSITION_VALUES)
            self.assertIn(example["decision_status"], DECISION_STATUS_VALUES)

    def test_review_outcome_resolved_points_use_both_dimensions(self):
        policy = load_feature_policy()
        review = policy["semantic_core"][REVIEW_DATE_KEY]
        resolved = review["resolved_points"]
        self.assertTrue(resolved, "MI_dir resolution must be recorded")
        for point in resolved:
            self.assertIn("semantic_disposition", point)
            self.assertIn("decision_status", point)
            self.assertIn(point["semantic_disposition"], SEMANTIC_DISPOSITION_VALUES)
            self.assertIn(point["decision_status"], DECISION_STATUS_VALUES)

    def test_no_legacy_mapping_status_key_anywhere(self):
        def walk(node):
            if isinstance(node, dict):
                for key, value in node.items():
                    self.assertNotEqual(key, "mapping_status")
                    walk(value)
            elif isinstance(node, list):
                for item in node:
                    walk(item)

        walk(load_feature_policy())


class RegistryConsistencyTests(unittest.TestCase):
    """Registered reference docs must exist and match their recorded
    SHA-256 and byte size, so the evidence package can be verified
    independently."""

    def setUp(self):
        self.registry_path = (
            REPO_ROOT / "references" / "dataset_docs" / "registry.json"
        )
        with self.registry_path.open(encoding="utf-8") as handle:
            self.registry = json.load(handle)

    def test_registered_files_exist_and_match_hashes(self):
        import hashlib

        for entry in self.registry["entries"]:
            path = self.registry_path.parent / entry["file"]
            self.assertTrue(path.is_file(), f"missing registered file {entry['file']}")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            self.assertEqual(digest, entry["sha256"])
            if "size_bytes" in entry:
                self.assertEqual(path.stat().st_size, entry["size_bytes"])

    def test_meidan_entry_records_version_and_publication_doi(self):
        entries = [
            e for e in self.registry["entries"] if "meidan2018" in e["file"]
        ]
        self.assertEqual(len(entries), 1)
        entry = entries[0]
        self.assertIn("v1", entry["arxiv_version"])
        self.assertIn("10.1109/MPRV.2018.03367731", entry["source_description"])
        self.assertIn("arXiv v1 PDF linked by UCI", entry["source_description"])


if __name__ == "__main__":
    unittest.main()
