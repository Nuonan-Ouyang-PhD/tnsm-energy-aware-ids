import json
import tempfile
import unittest
from pathlib import Path

from tnsm_exp.quality_exceptions import register_quality_exceptions


class QualityExceptionTests(unittest.TestCase):
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
                            "label_source": "Directory and filename",
                        }
                    }
                }
            ),
            encoding="utf-8",
        )
        (self.root / "SOURCE_COMMIT").write_text("b" * 40 + "\n", encoding="utf-8")

    def tearDown(self):
        self.temporary.cleanup()

    def test_registers_malformed_line_with_byte_evidence(self):
        extracted = self.root / "extracted"
        extracted.mkdir()
        # 2-col header, one good row, one truncated last line without newline
        (extracted / "data.csv").write_bytes(b"a,b\n1,2\n3")
        _, result = register_quality_exceptions(
            self.root,
            "fixture",
            extracted,
            self.root / "exceptions.json",
        )
        self.assertEqual(result["exception_count"], 1)
        record = result["exceptions"][0]
        self.assertEqual(record["relative_path"], "data.csv")
        self.assertEqual(record["physical_line"], 3)
        self.assertEqual(record["expected_column_count"], 2)
        self.assertEqual(record["observed_column_count_line_scan"], 1)
        self.assertEqual(record["raw_line_bytes"], 1)
        self.assertFalse(record["ends_with_newline"])
        self.assertTrue(record["is_last_line"])
        self.assertEqual(record["raw_line_sha256"], __import__("hashlib").sha256(b"3").hexdigest())
        self.assertIn("deterministic", result["policy"])

    def test_clean_tree_yields_zero_exceptions(self):
        extracted = self.root / "extracted"
        extracted.mkdir()
        (extracted / "data.csv").write_bytes(b"a,b\n1,2\n")
        _, result = register_quality_exceptions(
            self.root,
            "fixture",
            extracted,
            self.root / "exceptions.json",
        )
        self.assertEqual(result["exception_count"], 0)
        self.assertEqual(result["files_scanned"], 1)
        self.assertEqual(result["exceptions"], [])

    def test_refuses_overwrite(self):
        extracted = self.root / "extracted"
        extracted.mkdir()
        (extracted / "data.csv").write_bytes(b"a,b\n1,2\n")
        output = self.root / "exceptions.json"
        register_quality_exceptions(self.root, "fixture", extracted, output)
        with self.assertRaises(FileExistsError):
            register_quality_exceptions(self.root, "fixture", extracted, output)

    def test_empty_physical_lines_are_ignored(self):
        extracted = self.root / "extracted"
        extracted.mkdir()
        # csv.reader yields [] for a blank line; inventory skips them, so the
        # exception scan must skip them as well
        (extracted / "data.csv").write_bytes(b"a,b\n1,2\n\n3,4\n")
        _, result = register_quality_exceptions(
            self.root,
            "fixture",
            extracted,
            self.root / "exceptions.json",
        )
        self.assertEqual(result["exception_count"], 0)


if __name__ == "__main__":
    unittest.main()
