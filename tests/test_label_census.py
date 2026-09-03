import subprocess
import tempfile
import unittest
from pathlib import Path

from tnsm_exp.label_census import census_labels
from tnsm_exp.dataset_registry import DirtyWorktreeError


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class LabelCensusTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "config", "user.name", "Test")
        (self.root / "tracked.txt").write_text("committed\n", encoding="utf-8")
        # Mirror the real repo: raw dataset files are gitignored, so the
        # census input CSV does not trip the dirty-worktree gate.
        (self.root / ".gitignore").write_text("*.csv\n", encoding="utf-8")
        git(self.root, "add", "tracked.txt", ".gitignore")
        git(self.root, "commit", "-q", "-m", "initial")
        self.csv_path = self.root / "train_test_network.csv"

    def tearDown(self):
        self.temporary.cleanup()

    def _write_csv(self, content: str) -> None:
        self.csv_path.write_text(content, encoding="utf-8")

    def test_basic_census_counts(self):
        self._write_csv(
            "src_ip,label,type\n"
            "1.1.1.1,0,normal\n"
            "2.2.2.2,1,ddos\n"
            "3.3.3.3,1,ddos\n"
            "4.4.4.4,1,scan\n"
        )
        output_path, result = census_labels(self.root, "ton_iot", self.csv_path)
        self.assertTrue(output_path.exists())
        self.assertEqual(result["total_rows"], 4)
        self.assertEqual(result["label_counts"], {"0": 1, "1": 3})
        self.assertEqual(result["type_counts"], {"ddos": 2, "normal": 1, "scan": 1})
        self.assertEqual(
            result["label_type_cross_counts"],
            {"0||normal": 1, "1||ddos": 2, "1||scan": 1},
        )
        self.assertEqual(result["paper_eligible"], False)
        self.assertEqual(result["anomalies"], [])
        self.assertIn("source_commit", result)
        self.assertIn("source_csv_sha256", result)

    def test_sha256_mismatch_refused(self):
        self._write_csv("label,type\n0,normal\n")
        with self.assertRaises(ValueError):
            census_labels(
                self.root,
                "ton_iot",
                self.csv_path,
                expected_sha256="0" * 64,
            )

    def test_row_count_mismatch_refused(self):
        self._write_csv("label,type\n0,normal\n0,normal\n")
        with self.assertRaises(ValueError):
            census_labels(
                self.root,
                "ton_iot",
                self.csv_path,
                expected_total_rows=1,
            )

    def test_non_binary_label_recorded_as_anomaly(self):
        self._write_csv(
            "label,type\n0,normal\n2,weird\n"
        )
        _, result = census_labels(self.root, "ton_iot", self.csv_path)
        self.assertEqual(len(result["anomalies"]), 1)
        self.assertEqual(result["anomalies"][0]["kind"], "non_binary_label_value")
        self.assertEqual(result["anomalies"][0]["raw_label"], "2")

    def test_label_type_contradiction_detected(self):
        # label=0 (benign expected) but type is an attack name
        self._write_csv("label,type\n0,ddos\n1,normal\n")
        _, result = census_labels(self.root, "ton_iot", self.csv_path)
        kinds = [a["kind"] for a in result["anomalies"]]
        self.assertEqual(kinds.count("label_type_potential_contradiction"), 2)

    def test_whitespace_and_case_recorded_not_normalized(self):
        # raw values with whitespace/case variants must be kept verbatim
        self._write_csv(
            "label,type\n"
            "0, normal\n"
            "0,Normal\n"
            "1, DDoS \n"
            "0,normal\n"
        )
        _, result = census_labels(self.root, "ton_iot", self.csv_path)
        # verbatim raw values
        self.assertEqual(
            result["type_counts"],
            {" DDoS ": 1, " normal": 1, "Normal": 1, "normal": 1},
        )
        # whitespace/case flags captured
        self.assertTrue(
            result["type_value_profiles"]["Normal"]["lowercase_variant_differs"]
        )
        self.assertTrue(
            result["type_value_profiles"][" DDoS "]["has_leading_or_trailing_whitespace"]
        )
        # proposals only
        self.assertEqual(result["normalization_status"], "proposed")
        self.assertEqual(
            result["normalization_candidates"]["type"],
            {" normal": "normal", " DDoS ": "ddos", "Normal": "normal"},
        )

    def test_empty_and_whitespace_missing_counts(self):
        self._write_csv("label,type\n0,\n ,attack\n1,ddos\n")
        _, result = census_labels(self.root, "ton_iot", self.csv_path)
        self.assertEqual(result["missing_counts"]["type_empty_string"], 1)
        self.assertEqual(result["missing_counts"]["label_whitespace_only"], 1)

    def test_field_count_mismatch_counted(self):
        self._write_csv("label,type,extra\n0,normal,x\n1,ddos\n")
        _, result = census_labels(self.root, "ton_iot", self.csv_path)
        self.assertEqual(result["missing_counts"]["row_field_count_mismatch"], 1)
        self.assertEqual(result["total_rows"], 2)

    def test_missing_columns_refused(self):
        self._write_csv("src_ip,dst_ip\n1.1.1.1,2.2.2.2\n")
        with self.assertRaises(ValueError):
            census_labels(self.root, "ton_iot", self.csv_path)

    def test_refuses_overwrite(self):
        self._write_csv("label,type\n0,normal\n")
        first_path, _ = census_labels(self.root, "ton_iot", self.csv_path)
        with self.assertRaises(FileExistsError):
            census_labels(self.root, "ton_iot", self.csv_path)
        self.assertTrue(first_path.exists())

    def test_refuses_dirty_worktree(self):
        self._write_csv("label,type\n0,normal\n")
        (self.root / "untracked.py").write_text("x = 1\n", encoding="utf-8")
        with self.assertRaises(DirtyWorktreeError):
            census_labels(self.root, "ton_iot", self.csv_path)
if __name__ == "__main__":
    unittest.main()
