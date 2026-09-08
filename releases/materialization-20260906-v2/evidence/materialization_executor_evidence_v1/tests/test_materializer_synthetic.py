from __future__ import annotations

import copy
import csv
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "materialize_dataset_native_v1.py"
REAL_CONTRACT = ROOT / "contract" / "materialization_contract_v1r1.json"
FIXTURES = ROOT / "tests" / "fixtures"

spec = importlib.util.spec_from_file_location("materializer_v1", SCRIPT)
assert spec is not None and spec.loader is not None
materializer = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = materializer
spec.loader.exec_module(materializer)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def parsed_line(raw: bytes) -> list:
    text = raw.decode("utf-8").rstrip("\n")
    if text.endswith("\r"):
        text = text[:-1]
    return next(csv.reader([text], strict=True))


def inventory_item(path: Path, root: Path) -> Dict[str, Any]:
    lines = path.read_bytes().splitlines(keepends=True)
    columns = parsed_line(lines[0])
    malformed = sum(len(parsed_line(line)) != len(columns) for line in lines[1:])
    return {
        "bytes": path.stat().st_size,
        "column_count": len(columns),
        "columns": columns,
        "header_sha256": hashlib.sha256(lines[0]).hexdigest(),
        "malformed_rows": malformed,
        "relative_path": path.relative_to(root).as_posix(),
        "row_count": len(lines) - 1,
        "sha256": sha256(path),
    }


def build_inventory(dataset_id: str, root: Path) -> Dict[str, Any]:
    # Reverse first to prove that the executor, not fixture discovery order,
    # supplies the normative UTF-8 bytewise ordering.
    paths = list(reversed(sorted(root.rglob("*.csv"))))
    files = [inventory_item(path, root) for path in paths]
    return {
        "all_rows_well_formed": all(item["malformed_rows"] == 0 for item in files),
        "created_at_utc": "2000-01-01T00:00:00Z",
        "dataset_id": dataset_id,
        "display_name": dataset_id,
        "file_count": len(files),
        "files": files,
        "input_name": dataset_id,
        "kind": "dataset_csv_inventory",
        "label_source": "synthetic fixture",
        "paper_eligible": False,
        "schema_version": 1,
        "source_commit": "synthetic",
        "total_bytes": sum(item["bytes"] for item in files),
        "total_rows": sum(item["row_count"] for item in files),
    }


def build_exceptions(cic_root: Path, inventory: Mapping[str, Any]) -> Dict[str, Any]:
    by_path = {item["relative_path"]: item for item in inventory["files"]}
    exceptions = []
    for number in (7, 8, 9):
        relative = "CSV/DoS-UDP_Flood/DoS-UDP_Flood%d.pcap.csv" % number
        path = cic_root / Pure(relative)
        source = by_path[relative]
        lines = path.read_bytes().splitlines(keepends=True)
        raw = lines[-1]
        row = parsed_line(raw)
        exceptions.append({
            "ends_with_newline": raw.endswith(b"\n"),
            "expected_column_count": 2,
            "file_bytes": source["bytes"],
            "file_sha256": source["sha256"],
            "first_40_bytes_hex": raw[:40].hex(),
            "is_last_line": True,
            "logical_row_count_in_file": source["row_count"],
            "observed_column_count_line_scan": len(row),
            "physical_line": source["row_count"] + 1,
            "raw_line_bytes": len(raw),
            "raw_line_sha256": hashlib.sha256(raw).hexdigest(),
            "relative_path": relative,
        })
    return {
        "created_at_utc": "2000-01-01T00:00:00Z",
        "dataset_id": "ciciot2023",
        "display_name": "synthetic",
        "exception_count": 3,
        "exceptions": exceptions,
        "files_scanned": inventory["file_count"],
        "input_name": "ciciot2023",
        "kind": "dataset_quality_exceptions",
        "paper_eligible": False,
        "policy": "synthetic exact final-line exclusions",
        "schema_version": 1,
        "source_commit": "synthetic",
    }


def Pure(relative: str) -> Path:
    return Path(*relative.split("/"))


def build_ontology() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "kind": "label_ontology",
        "status": "frozen",
        "canonical_family": {
            "ton_iot_type_mapping": {"entries": [
                {"source_type": "normal", "canonical_family": "benign"},
                {"source_type": "ddos", "canonical_family": "ddos"},
            ]},
            "ciciot2023_type_mapping": {"entries": [
                {"source_type": "Benign_Final", "canonical_family": "benign"},
                {"source_type": "DoS-UDP_Flood", "canonical_family": "dos"},
            ]},
            "n_baiot_type_mapping": {"entries": [
                {"source_family": "benign", "source_subtype": "benign_traffic",
                 "canonical_family": "benign"},
                {"source_family": "mirai_attacks_extracted", "source_subtype": "ack",
                 "canonical_family": "mirai"},
            ]},
        },
    }


class SyntheticCase:
    def __init__(self, base: Path) -> None:
        self.base = base
        self.package = base / "package"
        self.sources = base / "sources"
        self.destination = base / "destination"
        self.destination.mkdir(parents=True)
        (self.package / "contract").mkdir(parents=True)
        for dataset_id in ("ton_iot", "ciciot2023", "n_baiot"):
            shutil.copytree(FIXTURES / "source" / dataset_id,
                            self.sources / dataset_id)
        self.source_roots = {
            "ton_iot": self.sources / "ton_iot",
            "ciciot2023": self.sources / "ciciot2023",
            "n_baiot": self.sources / "n_baiot",
        }
        self.contract = json.loads(REAL_CONTRACT.read_text(encoding="utf-8"))
        self.contract["contract_id"] = "SYNTHETIC-MATERIALIZATION-CONTRACT-V1"
        self.contract["status"] = "synthetic_test_only"
        self.contract["output_binding"].update({
            "binding_status": "synthetic temporary directory",
            "root": str(self.destination / "published"),
            "staging_root": str(self.destination / ".published.staging"),
        })
        self.contract["storage"].update({
            "source_bytes": 0,
            "hard_output_cap_bytes": 1000000,
            "scratch_reserve_bytes": 0,
            "minimum_free_bytes": 1,
            "current_location_observation_passes": True,
        })
        self.contract["feature_contract"] = {
            "ton_iot": {
                "source_columns": 8,
                "output_columns": 2,
                "excluded": ["label", "type", "src_ip", "dst_ip",
                             "src_port", "dst_port"],
            },
            "ciciot2023": {"source_columns": 2, "output_columns": 2,
                            "excluded": []},
            "n_baiot": {"source_columns": 2, "output_columns": 2,
                         "excluded": []},
        }
        self.contract["expected_real_output"] = {
            "inventoried_csv_files": 8,
            "feature_shards": 7,
            "label_shards": 7,
            "source_rows": 13,
            "excluded_rows": 3,
            "materialized_rows": 10,
            "per_dataset": {
                "ton_iot": {"shards": 1, "features": 2, "rows": 2,
                            "benign": 1, "attack": 1},
                "ciciot2023": {"shards": 4, "features": 2, "rows": 5,
                               "benign": 2, "attack": 3},
                "n_baiot": {"shards": 2, "features": 2, "rows": 3,
                            "benign": 2, "attack": 1},
            },
        }
        self.refresh_metadata()

    @property
    def contract_path(self) -> Path:
        return self.package / "contract" / "materialization_contract_v1r1.json"

    @property
    def output(self) -> Path:
        return Path(self.contract["output_binding"]["root"])

    @property
    def staging(self) -> Path:
        return Path(self.contract["output_binding"]["staging_root"])

    def refresh_metadata(self, preserve_exceptions: bool = False) -> None:
        inputs = self.package / "inputs"
        policy_path = inputs / "protocol" / "feature_policy.json"
        ontology_path = inputs / "protocol" / "label_ontology.json"
        request_path = inputs / "request" / "materialization_execution_request_v1.json"
        census_path = inputs / "censuses" / "ton_iot.json"
        exception_path = inputs / "quality_exceptions" / "cic.json"
        write_json(policy_path, {"schema_version": 1, "kind": "feature_policy",
                                 "status": "frozen"})
        write_json(ontology_path, build_ontology())
        write_json(request_path, {"request_id": "synthetic"})
        write_json(census_path, {"kind": "synthetic_census"})
        inventories: Dict[str, Dict[str, Any]] = {}
        for dataset_id, root in self.source_roots.items():
            inventories[dataset_id] = build_inventory(dataset_id, root)
            path = inputs / "inventories" / (dataset_id + ".json")
            write_json(path, inventories[dataset_id])
            self.contract["input_binding"]["inventories"][dataset_id] = {
                "file": path.relative_to(self.package).as_posix(),
                "sha256": sha256(path),
            }
        if not preserve_exceptions:
            write_json(exception_path,
                       build_exceptions(self.source_roots["ciciot2023"],
                                        inventories["ciciot2023"]))
        self.contract["input_binding"]["feature_policy"] = {
            "file": policy_path.relative_to(self.package).as_posix(),
            "sha256": sha256(policy_path), "status": "frozen"}
        self.contract["input_binding"]["label_ontology"] = {
            "file": ontology_path.relative_to(self.package).as_posix(),
            "sha256": sha256(ontology_path), "status": "frozen"}
        self.contract["input_binding"]["ton_label_census"] = {
            "file": census_path.relative_to(self.package).as_posix(),
            "sha256": sha256(census_path)}
        self.contract["input_binding"]["cic_quality_exceptions"] = {
            "file": exception_path.relative_to(self.package).as_posix(),
            "sha256": sha256(exception_path)}
        self.contract["baseline_request"]["request_json"] = \
            request_path.relative_to(self.package).as_posix()
        self.contract["baseline_request"]["request_json_sha256"] = sha256(request_path)
        self.contract["storage"]["source_bytes"] = sum(
            item["total_bytes"] for item in inventories.values())
        write_json(self.contract_path, self.contract)

    def rewrite_contract(self) -> None:
        write_json(self.contract_path, self.contract)


def tree_hashes(root: Path) -> Dict[str, str]:
    return {path.relative_to(root).as_posix(): sha256(path)
            for path in sorted(root.rglob("*")) if path.is_file()}


def read_ledger(output: Path, dataset_id: str) -> list:
    path = output / "datasets" / dataset_id / "lineage" / "shards.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class MaterializerSyntheticTests(unittest.TestCase):
    maxDiff = None

    def make_case(self, temporary: str) -> SyntheticCase:
        return SyntheticCase(Path(temporary))

    def run_case(self, case: SyntheticCase, **kwargs: Any) -> Dict[str, Any]:
        return materializer._execute_authorized(
            case.contract_path, case.source_roots,
            free_bytes=lambda _path: 10**9, **kwargs)

    def test_static_expected_outputs_and_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            result = self.run_case(case)
            self.assertTrue(case.output.is_dir())
            self.assertFalse(case.staging.exists())
            self.assertEqual(result["dataset_results"]["ton_iot"]["rows_materialized"], 2)

            ledgers = {dataset: read_ledger(case.output, dataset)
                       for dataset in ("ton_iot", "ciciot2023", "n_baiot")}
            expected = {
                ("ton_iot", "train_test_network.csv"):
                    ("ton_features.csv", "ton_labels.csv"),
                ("ciciot2023", "CSV/Benign_Final/Benign_Final1.pcap.csv"):
                    ("cic_benign_features.csv", "cic_benign_labels.csv"),
                ("ciciot2023", "CSV/DoS-UDP_Flood/DoS-UDP_Flood7.pcap.csv"):
                    ("cic_attack7_features.csv", "cic_attack7_labels.csv"),
                ("ciciot2023", "CSV/DoS-UDP_Flood/DoS-UDP_Flood8.pcap.csv"):
                    ("cic_attack8_features.csv", "cic_attack8_labels.csv"),
                ("ciciot2023", "CSV/DoS-UDP_Flood/DoS-UDP_Flood9.pcap.csv"):
                    ("cic_attack9_features.csv", "cic_attack9_labels.csv"),
                ("n_baiot", "CamA/benign_traffic.csv"):
                    ("nb_benign_features.csv", "nb_benign_labels.csv"),
                ("n_baiot", "CamA/mirai_attacks_extracted/ack.csv"):
                    ("nb_attack_features.csv", "nb_attack_labels.csv"),
            }
            for dataset_id, entries in ledgers.items():
                self.assertEqual([entry["shard_ordinal"] for entry in entries],
                                 list(range(1, len(entries) + 1)))
                self.assertEqual([entry["source_file"] for entry in entries],
                                 sorted((entry["source_file"] for entry in entries),
                                        key=lambda value: value.encode("utf-8")))
                for entry in entries:
                    expected_features, expected_labels = expected[
                        (dataset_id, entry["source_file"])]
                    self.assertEqual((case.output / entry["features_file"]).read_bytes(),
                                     (FIXTURES / "expected" / expected_features).read_bytes())
                    self.assertEqual((case.output / entry["labels_file"]).read_bytes(),
                                     (FIXTURES / "expected" / expected_labels).read_bytes())
                    self.assertRegex(entry["shard_id"], r"^\d{4}-[0-9a-f]{16}$")

            self.assertIsNone(ledgers["ton_iot"][0]["device_id"])
            self.assertIsNone(ledgers["ton_iot"][0]["capture_id"])
            self.assertIsNone(ledgers["ciciot2023"][0]["device_id"])
            self.assertIsInstance(ledgers["ciciot2023"][0]["capture_id"], str)
            for entry in ledgers["n_baiot"]:
                self.assertIsInstance(entry["capture_id"], list)
                self.assertEqual(len(entry["capture_id"]), 3)
            excluded = [item for entry in ledgers["ciciot2023"]
                        for item in entry["excluded_rows"]]
            self.assertEqual(len(excluded), 3)
            self.assertEqual({tuple(item.keys()) for item in excluded}, {
                ("physical_line", "source_row", "raw_line_bytes", "raw_line_sha256",
                 "observed_column_count", "expected_column_count")})
            self.assertEqual({item["source_row"] for item in excluded}, {2})
            materializer.verify_root_manifest(case.output)
            manifest = (case.output / "MANIFEST_SHA256.txt").read_text(encoding="utf-8")
            self.assertNotIn("MANIFEST_SHA256.txt", manifest)

    def test_full_tree_is_reproducible_across_independent_runs(self) -> None:
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            case_a = self.make_case(first)
            case_b = self.make_case(second)
            self.run_case(case_a)
            self.run_case(case_b)
            self.assertEqual(tree_hashes(case_a.output), tree_hashes(case_b.output))

    def test_cli_refuses_before_source_access_without_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            trap = Path(temporary) / "source-does-not-exist"
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--contract", str(REAL_CONTRACT),
                 "--execute", "--ton-root", str(trap), "--cic-root", str(trap),
                 "--nb-root", str(trap)], text=True, capture_output=True, check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            self.assertEqual(result.returncode, 2)
            self.assertIn("complete authorization evidence is required", result.stderr)
            self.assertNotIn("source root", result.stderr)

    def test_cli_positive_guard_and_synthetic_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            request_zip = case.base / "request.zip"
            evidence_zip = case.base / "evidence.zip"
            request_zip.write_bytes(b"synthetic accepted request")
            evidence_zip.write_bytes(b"synthetic approved executor evidence")
            case.contract["baseline_request"]["request_zip_sha256"] = sha256(request_zip)
            case.rewrite_contract()
            authorization = {
                "schema_version": 1,
                "kind": "materialization_execution_authorization",
                "authorization_id": "SYNTHETIC-AUTHORIZATION",
                "contract_id": case.contract["contract_id"],
                "request_zip_sha256": sha256(request_zip),
                "executor_evidence_zip_sha256": sha256(evidence_zip),
                "output_root": str(case.output),
                "authorized_by_user": True,
                "operations": case.contract["authorization"]["required_operations"],
            }
            auth_path = case.base / "authorization.json"
            decisions = case.base / "DECISIONS.md"
            write_json(auth_path, authorization)
            decisions.write_text("\n".join([
                authorization["authorization_id"], case.contract["contract_id"],
                sha256(request_zip), sha256(evidence_zip), str(case.output)]) + "\n",
                encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "--contract", str(case.contract_path),
                 "--execute", "--authorization-record", str(auth_path),
                 "--request-zip", str(request_zip),
                 "--executor-evidence-zip", str(evidence_zip),
                 "--decisions", str(decisions),
                 "--ton-root", str(case.source_roots["ton_iot"]),
                 "--cic-root", str(case.source_roots["ciciot2023"]),
                 "--nb-root", str(case.source_roots["n_baiot"])],
                text=True, capture_output=True, check=False,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(case.output.is_dir())
            self.assertIn('"splitting_run": false', result.stdout)
            self.assertIn('"training_run": false', result.stdout)

    def test_wrong_source_identity_fails_before_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            with (case.source_roots["ton_iot"] / "train_test_network.csv").open("ab") as handle:
                handle.write(b"changed\n")
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "byte size mismatch"):
                self.run_case(case)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

    def test_unregistered_malformed_row_fails_before_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            exception_path = case.package / "inputs/quality_exceptions/cic.json"
            empty = json.loads(exception_path.read_text(encoding="utf-8"))
            empty["exception_count"] = 0
            empty["exceptions"] = []
            write_json(exception_path, empty)
            case.contract["input_binding"]["cic_quality_exceptions"]["sha256"] = \
                sha256(exception_path)
            case.rewrite_contract()
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "unregistered malformed row"):
                self.run_case(case)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

    def test_unexpected_label_cleans_only_current_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            ton = case.source_roots["ton_iot"] / "train_test_network.csv"
            ton.write_text(ton.read_text(encoding="utf-8").replace(
                ",0,normal\n", ",2,normal\n"), encoding="utf-8")
            case.refresh_metadata()
            neighbor = case.destination / "keep-me"
            neighbor.write_text("sentinel", encoding="utf-8")
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "unexpected TON label"):
                self.run_case(case)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())
            self.assertEqual(neighbor.read_text(encoding="utf-8"), "sentinel")

    def test_insufficient_space_creates_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "insufficient free space"):
                materializer._execute_authorized(
                    case.contract_path, case.source_roots,
                    free_bytes=lambda _path: 0)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

    def test_hard_budget_breach_cleans_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            case.contract["storage"]["hard_output_cap_bytes"] = 1
            case.rewrite_contract()
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "hard output cap exceeded"):
                self.run_case(case)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

    def test_existing_output_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            case.output.mkdir()
            sentinel = case.output / "sentinel"
            sentinel.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "already exists"):
                self.run_case(case)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            self.assertFalse(case.staging.exists())

    def test_existing_staging_is_not_modified(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            case.staging.mkdir()
            sentinel = case.staging / "sentinel"
            sentinel.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "staging already exists"):
                self.run_case(case)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            self.assertFalse(case.output.exists())

    def test_injected_failure_cleanup_is_contained(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            neighbor = case.destination / "neighbor"
            neighbor.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "synthetic injected failure"):
                self.run_case(case, fault_after_shards=1)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())
            self.assertEqual(neighbor.read_text(encoding="utf-8"), "keep")

    def test_cleanup_rejects_wrong_staging_name(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            output = base / "published"
            wrong = base / "other-staging"
            wrong.mkdir()
            sentinel = wrong / "sentinel"
            sentinel.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "refusing cleanup"):
                materializer.safe_cleanup_created_staging(wrong, output, True)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")


if __name__ == "__main__":
    unittest.main()
