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
VERIFIER = ROOT / "scripts" / "verify_materialization_request_v1.py"


def file_hashes(root: Path) -> Dict[str, str]:
    result: Dict[str, str] = {}
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        result[path.relative_to(root).as_posix()] = hashlib.sha256(
            path.read_bytes()).hexdigest()
    return result


def write_json(path: Path, value: Any) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


class MaterializationRequestVerifierTests(unittest.TestCase):
    maxDiff = None

    def run_verifier(self, root: Path) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, str(VERIFIER), "--root", str(root)],
            text=True, capture_output=True, check=False, env=env)

    def with_copy(self, mutation: Callable[[Path], None]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as temporary:
            copied = Path(temporary) / "request"
            shutil.copytree(ROOT, copied)
            mutation(copied)
            return self.run_verifier(copied)

    def test_exact_package_passes_without_mutation(self) -> None:
        before = file_hashes(ROOT)
        result = self.run_verifier(ROOT)
        after = file_hashes(ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("authorization_granted = false", result.stdout)
        self.assertIn("data_gate_unlocked   = false", result.stdout)
        self.assertIn("raw_csvs_opened      = false", result.stdout)
        self.assertEqual(before, after)

    def test_rejects_authorization_flip(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "proposal/materialization_execution_request_v1.json"
            obj = json.loads(path.read_text(encoding="utf-8"))
            obj["authorization"]["authorization_granted"] = True
            write_json(path, obj)

        result = self.with_copy(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("authorization remains false", result.stdout)

    def test_rejects_splitting_scope(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "proposal/materialization_execution_request_v1.json"
            obj = json.loads(path.read_text(encoding="utf-8"))
            obj["scope"]["splitting"] = "permitted"
            write_json(path, obj)

        result = self.with_copy(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("scope keeps splitting forbidden", result.stdout)

    def test_rejects_frozen_policy_mutation(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "inputs/protocol/feature_policy.json"
            obj = json.loads(path.read_text(encoding="utf-8"))
            obj["status"] = "proposed"
            write_json(path, obj)

        result = self.with_copy(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bundled input SHA-256", result.stdout)
        self.assertIn("feature policy is frozen", result.stdout)

    def test_rejects_cic_inventory_mutation(self) -> None:
        def mutate(root: Path) -> None:
            path = root / "inputs/inventories/ciciot2023_20260903T142539Z.json"
            obj = json.loads(path.read_text(encoding="utf-8"))
            obj["files"][0]["sha256"] = "0" * 64
            write_json(path, obj)

        result = self.with_copy(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("bundled input SHA-256", result.stdout)

    def test_rejects_quality_exception_mutation(self) -> None:
        def mutate(root: Path) -> None:
            path = root / (
                "inputs/quality_exceptions/ciciot2023_20260903T142617Z.json")
            obj = json.loads(path.read_text(encoding="utf-8"))
            obj["exceptions"][0]["physical_line"] -= 1
            write_json(path, obj)

        result = self.with_copy(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("CIC exceptions bind exact inventoried files and final rows",
                      result.stdout)

    def test_rejects_raw_csv_in_request_package(self) -> None:
        def mutate(root: Path) -> None:
            (root / "unexpected.csv").write_text("x\n1\n", encoding="utf-8")

        result = self.with_copy(mutate)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("request package contains no raw CSV", result.stdout)


if __name__ == "__main__":
    unittest.main()
