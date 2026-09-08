"""CLI tests for the separate read-only post-install verifier."""

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
VERIFIER = (
    REPO_ROOT
    / "scripts"
    / "audits"
    / "verify_installed_feature_policy_v1r2.py"
)
SOURCES = {
    "baseline": (
        REPO_ROOT
        / "artifacts"
        / "freezes"
        / "feature_policy_pre_freeze_baseline.json"
    ),
    "target": (
        REPO_ROOT
        / "artifacts"
        / "proposals"
        / "feature_policy_freeze_target_v1r2.json"
    ),
    "applied": REPO_ROOT / "config" / "feature_policy.json",
    "label-ontology": REPO_ROOT / "config" / "label_ontology.json",
    "spec": (
        REPO_ROOT
        / "artifacts"
        / "proposals"
        / "feature_policy_freeze_target_spec_v1r2.json"
    ),
}
EXPECTED_VERIFIER_SHA = (
    "f6e9431f571d56cdbcdfe1fbd6846c0b8d7c60e9f7dfe3550af1ffd39ea6100e"
)


def sha256_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class PostInstallVerifierCliTests(unittest.TestCase):
    """Invoke the real CLI against distinct temporary input paths."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.paths = {
            "baseline": root / "preserved" / "feature_policy.json",
            "target": (
                root
                / "artifacts"
                / "proposals"
                / "feature_policy_freeze_target_v1r2.json"
            ),
            "applied": root / "config" / "feature_policy.json",
            "label-ontology": root / "config" / "label_ontology.json",
            "spec": (
                root
                / "artifacts"
                / "proposals"
                / "feature_policy_freeze_target_spec_v1r2.json"
            ),
        }
        for name, source in SOURCES.items():
            self.paths[name].parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, self.paths[name])

    def tearDown(self):
        self.temp_dir.cleanup()

    def mutate_json(self, name, operation):
        obj = json.loads(self.paths[name].read_text(encoding="utf-8"))
        operation(obj)
        self.paths[name].write_text(
            json.dumps(obj, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    def invoke(self, expected_exit):
        before = {name: path.read_bytes() for name, path in self.paths.items()}
        command = [sys.executable, "-B", str(VERIFIER)]
        for name, path in self.paths.items():
            command.extend(["--" + name, str(path)])
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            command,
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=10,
            env=env,
        )
        self.assertEqual(result.returncode, expected_exit, result.stdout)
        self.assertEqual(result.stderr, "")
        report = json.loads(result.stdout)
        after = {name: path.read_bytes() for name, path in self.paths.items()}
        self.assertEqual(before, after, "post-install verifier modified input")
        return report

    def assert_rejected(self):
        report = self.invoke(1)
        self.assertFalse(report["all_pass"])
        self.assertTrue(report["failures"] or report["errors"])
        self.assertFalse(report["authorization_granted"])
        self.assertFalse(report["data_gates_unlocked"])

    def test_correct_installed_target_passes_36_read_only_checks(self):
        self.assertEqual(sha256_file(VERIFIER), EXPECTED_VERIFIER_SHA)
        report = self.invoke(0)
        self.assertTrue(report["all_pass"])
        self.assertEqual(report["checks_total"], 36)
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["errors"], [])
        self.assertFalse(report["authorization_granted"])
        self.assertFalse(report["data_gates_unlocked"])

    def test_uninstalled_old_baseline_is_rejected(self):
        shutil.copyfile(self.paths["baseline"], self.paths["applied"])
        self.assert_rejected()

    def test_modified_admission_count_is_rejected(self):
        self.mutate_json(
            "applied",
            lambda obj: obj["admission_set_this_version"].__setitem__(
                "admitted_mapping_count", 1
            ),
        )
        self.assert_rejected()

    def test_modified_mi_original_reference_is_rejected(self):
        def corrupt_mi(obj):
            evidence = obj["semantic_core"][
                "review_outcome_2026_09_04"
            ]["resolved_points"][0]["evidence_source"]
            evidence[0] += " CORRUPTED"

        self.mutate_json("applied", corrupt_mi)
        self.assert_rejected()

    def test_modified_ontology_is_rejected(self):
        self.paths["label-ontology"].write_bytes(
            self.paths["label-ontology"].read_bytes() + b"\n"
        )
        self.assert_rejected()

    def test_modified_target_and_applied_together_are_rejected(self):
        self.mutate_json(
            "applied", lambda obj: obj.__setitem__("status", "proposed")
        )
        shutil.copyfile(self.paths["applied"], self.paths["target"])
        self.assert_rejected()

    def test_modified_preserved_baseline_is_rejected(self):
        self.paths["baseline"].write_bytes(
            self.paths["baseline"].read_bytes() + b"\n"
        )
        self.assert_rejected()

    def test_missing_gate_authorization_precondition_is_rejected(self):
        def remove_authorization_precondition(obj):
            obj["data_handling"]["training"]["preconditions"].pop()

        self.mutate_json("applied", remove_authorization_precondition)
        self.assert_rejected()


if __name__ == "__main__":
    unittest.main()
