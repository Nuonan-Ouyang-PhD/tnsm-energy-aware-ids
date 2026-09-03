import csv
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tnsm_exp.dataset_registry import inventory_csv_tree, register_acquisition


class DatasetRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "config").mkdir()
        (self.root / "config" / "datasets.json").write_text(
            json.dumps(
                {
                    "datasets": {
                        "fixture": {
                            "display_name": "Fixture",
                            "official_page": "https://example.invalid/fixture",
                            "access_method": "fixture",
                            "selected_scope": "fixture",
                            "license_note": "fixture",
                            "label_source": "CSV column",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        (self.root / "SOURCE_COMMIT").write_text("b" * 40 + "\n", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def test_acquisition_hashes_exact_bytes(self):
        incoming = self.root / "incoming"
        incoming.mkdir()
        payload = b"official bytes\n"
        (incoming / "dataset.zip").write_bytes(payload)
        output = self.root / "acquisition.json"
        _, result = register_acquisition(self.root, "fixture", incoming, output)
        self.assertEqual(result["file_count"], 1)
        self.assertEqual(result["total_bytes"], len(payload))
        self.assertEqual(result["files"][0]["sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(result["source_commit"], "b" * 40)

    def test_acquisition_refuses_empty_files(self):
        incoming = self.root / "incoming"
        incoming.mkdir()
        (incoming / "empty.zip").touch()
        with self.assertRaises(ValueError):
            register_acquisition(self.root, "fixture", incoming, self.root / "out.json")

    def test_csv_inventory_counts_rows_and_columns(self):
        extracted = self.root / "extracted"
        extracted.mkdir()
        with (extracted / "data.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["feature_a", "feature_b", "Label"])
            writer.writerow([1, 2, "Benign"])
            writer.writerow([3, 4, "Attack"])
        _, result = inventory_csv_tree(
            self.root,
            "fixture",
            extracted,
            self.root / "inventory.json",
        )
        self.assertEqual(result["file_count"], 1)
        self.assertEqual(result["total_rows"], 2)
        self.assertTrue(result["all_rows_well_formed"])
        self.assertEqual(result["files"][0]["column_count"], 3)

    def test_csv_inventory_detects_malformed_rows(self):
        extracted = self.root / "extracted"
        extracted.mkdir()
        (extracted / "data.csv").write_text("a,b\n1\n", encoding="utf-8")
        _, result = inventory_csv_tree(
            self.root,
            "fixture",
            extracted,
            self.root / "inventory.json",
        )
        self.assertFalse(result["all_rows_well_formed"])
        self.assertEqual(result["files"][0]["malformed_rows"], 1)


if __name__ == "__main__":
    unittest.main()

