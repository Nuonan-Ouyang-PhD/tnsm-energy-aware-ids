from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Callable, Dict


ROOT = Path(__file__).resolve().parents[1]
VERIFIER = ROOT / "scripts" / "verify_executor_evidence_v1r2.py"
CONTRACT = "contract/materialization_contract_v1r2.json"


def hashes(root: Path) -> Dict[str, str]:
    return {path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(root.rglob("*")) if path.is_file()}


def write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


class ExecutorEvidenceVerifierTests(unittest.TestCase):
    def run_verifier(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(VERIFIER), "--root", str(root)],
            text=True, capture_output=True, check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})

    def altered(self, mutation: Callable[[Dict[str, Any]], None]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "evidence"
            shutil.copytree(ROOT, copied)
            path = copied / CONTRACT
            contract = json.loads(path.read_text(encoding="utf-8"))
            mutation(contract)
            write_json(path, contract)
            return self.run_verifier(copied)

    def test_exact_evidence_passes_without_mutation(self) -> None:
        before = hashes(ROOT)
        result = self.run_verifier(ROOT)
        after = hashes(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("authorization_granted = false", result.stdout)
        self.assertIn("real_csvs_opened      = false", result.stdout)
        self.assertIn("real_output_created   = false", result.stdout)
        self.assertEqual(before, after)

    def test_rejects_output_equal_to_staging(self) -> None:
        result = self.altered(lambda value: value["output_binding"].update(
            {"staging_root": value["output_binding"]["root"]}))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("output and staging roots are distinct", result.stdout)

    def test_rejects_reversed_ton_binary_rule(self) -> None:
        def mutation(value: Dict[str, Any]) -> None:
            value["label_sidecar"]["ton_iot"]["binary_label_map"] = {
                "0": "attack", "1": "benign"}
        result = self.altered(mutation)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("TON binary rule direct assertion", result.stdout)

    def test_rejects_wrong_cic_inventory_binding(self) -> None:
        def mutation(value: Dict[str, Any]) -> None:
            value["input_binding"]["inventories"]["ciciot2023"]["sha256"] = "0" * 64
        result = self.altered(mutation)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ciciot2023 contract/request inventory hash", result.stdout)

    def test_rejects_missing_source_subtype_sidecar_column(self) -> None:
        def mutation(value: Dict[str, Any]) -> None:
            value["label_sidecar"]["columns"].remove("source_subtype")
        result = self.altered(mutation)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("complete label sidecar header", result.stdout)

    def test_rejects_authorization_flip(self) -> None:
        result = self.altered(lambda value: value["authorization"].update(
            {"granted": True}))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("contract does not authorize execution", result.stdout)

    def test_rejects_frozen_config_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "evidence"
            shutil.copytree(ROOT, copied)
            policy = copied / "inputs/protocol/feature_policy.json"
            value = json.loads(policy.read_text(encoding="utf-8"))
            value["status"] = "proposed"
            write_json(policy, value)
            result = self.run_verifier(copied)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("SHA-256: inputs/protocol/feature_policy.json", result.stdout)

    def test_rejects_missing_runtime_executor_binding(self) -> None:
        def mutation(value: Dict[str, Any]) -> None:
            value["runtime_evidence_binding"]["required_local_files"].remove(
                value["runtime_evidence_binding"]["executor_local_path"])
        result = self.altered(mutation)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("complete runtime local-file binding", result.stdout)

    def test_rejects_nonexclusive_publish_contract(self) -> None:
        result = self.altered(lambda value: value["output_binding"].update(
            {"publish": "ordinary atomic rename"}))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("atomic no-clobber primitive", result.stdout)

    def test_rejects_generalized_missing_lf_exception(self) -> None:
        result = self.altered(lambda value: value["source_csv_reading"].update(
            {"only_terminal_newline_exception": "all final lines may omit LF"}))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("only three fully bound CIC final rows", result.stdout)

    def test_rejects_automatic_failure_deletion(self) -> None:
        result = self.altered(lambda value: value["failure_safety"].update(
            {"automatic_failure_deletion": "permitted"}))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("automatic pathname deletion is forbidden", result.stdout)


if __name__ == "__main__":
    unittest.main()
