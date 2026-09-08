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
import zipfile
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Tuple
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "materialize_dataset_native_v1r2.py"
REAL_CONTRACT = ROOT / "contract" / "materialization_contract_v1r2.json"
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
    text = raw.decode("utf-8-sig").rstrip("\n")
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
        "header_sha256": hashlib.sha256("\x1f".join(columns).encode("utf-8")).hexdigest(),
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
        self.contract["contract_id"] = "SYNTHETIC-MATERIALIZATION-CONTRACT-V1R2"
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
        return self.package / "contract" / "materialization_contract_v1r2.json"

    @property
    def executor_path(self) -> Path:
        return self.package / "scripts" / "materialize_dataset_native_v1r2.py"

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
        runtime = self.contract["runtime_evidence_binding"]
        runtime.update({
            "archive_root": "synthetic_approved",
            "contract_local_path": "contract/materialization_contract_v1r2.json",
            "executor_local_path": "scripts/materialize_dataset_native_v1r2.py",
        })
        runtime["required_local_files"] = sorted({
            runtime["contract_local_path"], runtime["executor_local_path"],
            self.contract["input_binding"]["feature_policy"]["file"],
            self.contract["input_binding"]["label_ontology"]["file"],
            self.contract["input_binding"]["ton_label_census"]["file"],
            self.contract["input_binding"]["cic_quality_exceptions"]["file"],
            self.contract["baseline_request"]["request_json"],
            *(item["file"] for item in
              self.contract["input_binding"]["inventories"].values()),
        })
        write_json(self.contract_path, self.contract)

    def rewrite_contract(self) -> None:
        write_json(self.contract_path, self.contract)

    def install_executor(self) -> None:
        self.executor_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(SCRIPT, self.executor_path)

    def build_evidence_zip(self, destination: Path) -> Dict[str, str]:
        self.install_executor()
        manifest_path = self.package / "MANIFEST_SHA256.txt"
        files = sorted(
            (path for path in self.package.rglob("*")
             if path.is_file() and path != manifest_path),
            key=lambda path: path.relative_to(self.package).as_posix().encode("utf-8"))
        manifest = "".join(
            "%s  %s\n" % (sha256(path), path.relative_to(self.package).as_posix())
            for path in files)
        with manifest_path.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(manifest)
        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted((item for item in self.package.rglob("*") if item.is_file()),
                               key=lambda item: item.relative_to(self.package).as_posix().encode("utf-8")):
                archive.write(path, "synthetic_approved/" +
                              path.relative_to(self.package).as_posix())
        return {
            "archive_root": "synthetic_approved",
            "manifest_sha256": sha256(manifest_path),
            "contract_sha256": sha256(self.contract_path),
            "executor_sha256": sha256(self.executor_path),
        }


def tree_hashes(root: Path) -> Dict[str, str]:
    return {path.relative_to(root).as_posix(): sha256(path)
            for path in sorted(root.rglob("*")) if path.is_file()}


def tree_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file()) \
        if root.exists() else 0


def read_ledger(output: Path, dataset_id: str) -> list:
    path = output / "datasets" / dataset_id / "lineage" / "shards.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


class MaterializerSyntheticTests(unittest.TestCase):
    maxDiff = None

    def test_frozen_ton_header_recipe_with_bom_crlf(self) -> None:
        inventory = json.loads((ROOT / "inputs/inventories/ton_iot_20260903T113048Z.json").read_text())
        item = inventory["files"][0]
        raw = b"\xef\xbb\xbf" + ",".join(item["columns"]).encode() + b"\r\n"
        self.assertEqual(item["header_sha256"], "024f793b346cb855a35269b079a95db373cfad64e9ba2f448e5a8678660e2e20")
        self.assertNotEqual(hashlib.sha256(raw).hexdigest(), item["header_sha256"])
        self.assertEqual(materializer.validate_source_header(raw, Path("invented.csv"), item), item["columns"])

    def test_bom_crlf_cli_full_render_and_replay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            ton = case.source_roots["ton_iot"] / "train_test_network.csv"
            ton.write_bytes(b"\xef\xbb\xbf" + ton.read_bytes().replace(b"\n", b"\r\n"))
            case.refresh_metadata()
            result = self.run_cli(case, self.prepare_cli_authorization(case))
            self.assertEqual(result.returncode, 0, result.stderr)
            ledger = read_ledger(case.output, "ton_iot")[0]
            self.assertEqual((case.output / ledger["features_file"]).read_bytes(),
                             (FIXTURES / "expected/ton_features.csv").read_bytes())
            self.assertEqual((case.output / ledger["labels_file"]).read_bytes(),
                             (FIXTURES / "expected/ton_labels.csv").read_bytes())
            self.assertIn('"event": "preflight_complete"', result.stderr)
            self.assertIn('"event": "shard_replay_pass"', result.stderr)

    def test_raw_header_digest_is_not_accepted_as_inventory_recipe(self) -> None:
        raw = b"a,b\n"
        item = {"columns": ["a", "b"], "header_sha256": hashlib.sha256(raw).hexdigest()}
        with self.assertRaisesRegex(materializer.MaterializationError, "header SHA-256"):
            materializer.validate_source_header(raw, Path("invented.csv"), item)

    def test_column_drift_is_rejected_even_with_rebound_recipe(self) -> None:
        item = {"columns": ["a", "b"], "header_sha256": hashlib.sha256(b"b\x1fa").hexdigest()}
        with self.assertRaisesRegex(materializer.MaterializationError, "source header mismatch"):
            materializer.validate_source_header(b"b,a\n", Path("invented.csv"), item)

    def test_bom_is_not_stripped_from_a_data_value(self) -> None:
        self.assertEqual(materializer.parse_physical_csv_line(b"\xef\xbb\xbfvalue,x\n", Path("invented.csv"), 2),
                         ["\ufeffvalue", "x"])

    def test_header_recipe_change_cannot_bypass_full_file_hash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            inv = build_inventory("ton_iot", case.source_roots["ton_iot"])
            item = inv["files"][0]
            item["sha256"] = "0" * 64
            with self.assertRaisesRegex(materializer.MaterializationError, "source SHA-256 mismatch"):
                materializer.scan_source_file(case.source_roots["ton_iot"], item, {})

    def make_case(self, temporary: str) -> SyntheticCase:
        return SyntheticCase(Path(temporary))

    def run_case(self, case: SyntheticCase, **kwargs: Any) -> Dict[str, Any]:
        return materializer._execute_authorized(
            case.contract_path, case.source_roots,
            free_bytes=lambda _path: 10**9, **kwargs)

    def prepare_cli_authorization(self, case: SyntheticCase) -> Dict[str, Path]:
        request_zip = case.base / "request.zip"
        with zipfile.ZipFile(request_zip, "w") as archive:
            archive.writestr("SYNTHETIC_ONLY.txt", "invented request fixture\n")
        case.contract["baseline_request"]["request_zip_sha256"] = sha256(request_zip)
        case.rewrite_contract()
        evidence_zip = case.base / "evidence.zip"
        identity = case.build_evidence_zip(evidence_zip)
        authorization = {
            "schema_version": 1,
            "kind": "materialization_execution_authorization",
            "authorization_id": "SYNTHETIC-AUTHORIZATION",
            "contract_id": case.contract["contract_id"],
            "request_zip_sha256": sha256(request_zip),
            "executor_evidence_zip_sha256": sha256(evidence_zip),
            "evidence_archive_root": identity["archive_root"],
            "evidence_manifest_sha256": identity["manifest_sha256"],
            "contract_sha256": identity["contract_sha256"],
            "executor_sha256": identity["executor_sha256"],
            "output_root": str(case.output),
            "authorized_by_user": True,
            "operations": case.contract["authorization"]["required_operations"],
        }
        auth_path = case.base / "authorization.json"
        decisions = case.base / "DECISIONS.md"
        write_json(auth_path, authorization)
        decisions.write_text("\n".join(str(value) for value in [
            authorization["authorization_id"], authorization["contract_id"],
            authorization["request_zip_sha256"],
            authorization["executor_evidence_zip_sha256"],
            authorization["evidence_archive_root"],
            authorization["evidence_manifest_sha256"],
            authorization["contract_sha256"], authorization["executor_sha256"],
            authorization["output_root"],
        ]) + "\n", encoding="utf-8")
        return {
            "request_zip": request_zip, "evidence_zip": evidence_zip,
            "authorization": auth_path, "decisions": decisions,
        }

    def run_cli(self, case: SyntheticCase, evidence: Mapping[str, Path],
                roots: Optional[Mapping[str, Path]] = None) -> subprocess.CompletedProcess[str]:
        selected = roots or case.source_roots
        return subprocess.run(
            [sys.executable, str(case.executor_path),
             "--contract", str(case.contract_path), "--execute",
             "--authorization-record", str(evidence["authorization"]),
             "--request-zip", str(evidence["request_zip"]),
             "--executor-evidence-zip", str(evidence["evidence_zip"]),
             "--decisions", str(evidence["decisions"]),
             "--ton-root", str(selected["ton_iot"]),
             "--cic-root", str(selected["ciciot2023"]),
             "--nb-root", str(selected["n_baiot"])],
            text=True, capture_output=True, check=False,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"})

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
            evidence = self.prepare_cli_authorization(case)
            result = self.run_cli(case, evidence)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(case.output.is_dir())
            self.assertIn('"splitting_run": false', result.stdout)
            self.assertIn('"training_run": false', result.stdout)

    def test_cli_rejects_contract_drift_before_source_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            evidence = self.prepare_cli_authorization(case)
            excluded = case.contract["feature_contract"]["ton_iot"]["excluded"]
            excluded[excluded.index("src_ip")] = "proto"
            case.rewrite_contract()
            trap = case.base / "source-must-not-be-opened"
            roots = {dataset: trap for dataset in case.source_roots}
            result = self.run_cli(case, evidence, roots)
            self.assertEqual(result.returncode, 2)
            self.assertIn("local parsed contract differs from approved contract", result.stderr)
            self.assertNotIn("source root", result.stderr)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

    def test_cli_rejects_contract_whitespace_drift_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            evidence = self.prepare_cli_authorization(case)
            with case.contract_path.open("ab") as handle:
                handle.write(b"\n")
            trap = case.base / "source-must-not-be-opened"
            roots = {dataset: trap for dataset in case.source_roots}
            result = self.run_cli(case, evidence, roots)
            self.assertEqual(result.returncode, 2)
            self.assertIn("local runtime file differs from approved evidence", result.stderr)
            self.assertNotIn("source root", result.stderr)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

    def test_cli_rejects_executor_drift_before_source_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            evidence = self.prepare_cli_authorization(case)
            with case.executor_path.open("a", encoding="utf-8") as handle:
                handle.write("\n# synthetic post-review drift\n")
            trap = case.base / "source-must-not-be-opened"
            roots = {dataset: trap for dataset in case.source_roots}
            result = self.run_cli(case, evidence, roots)
            self.assertEqual(result.returncode, 2)
            self.assertIn("local runtime file differs from approved evidence", result.stderr)
            self.assertNotIn("source root", result.stderr)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

    def test_cli_rejects_runtime_input_drift_before_source_access(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            evidence = self.prepare_cli_authorization(case)
            policy = case.package / "inputs/protocol/feature_policy.json"
            with policy.open("ab") as handle:
                handle.write(b" ")
            trap = case.base / "source-must-not-be-opened"
            roots = {dataset: trap for dataset in case.source_roots}
            result = self.run_cli(case, evidence, roots)
            self.assertEqual(result.returncode, 2)
            self.assertIn("local runtime file differs from approved evidence", result.stderr)
            self.assertNotIn("source root", result.stderr)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

    def test_cli_rejects_manifest_inconsistent_evidence_zip(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            evidence = self.prepare_cli_authorization(case)
            corrupted = case.base / "manifest-inconsistent-evidence.zip"
            with zipfile.ZipFile(evidence["evidence_zip"], "r") as source, \
                    zipfile.ZipFile(corrupted, "w") as destination:
                for info in source.infolist():
                    data = source.read(info.filename)
                    if info.filename.endswith("/scripts/materialize_dataset_native_v1r2.py"):
                        data += b"\n# archive member drift\n"
                    destination.writestr(info, data)
            authorization = json.loads(
                evidence["authorization"].read_text(encoding="utf-8"))
            authorization["executor_evidence_zip_sha256"] = sha256(corrupted)
            write_json(evidence["authorization"], authorization)
            with evidence["decisions"].open("a", encoding="utf-8") as handle:
                handle.write(sha256(corrupted) + "\n")
            evidence = dict(evidence)
            evidence["evidence_zip"] = corrupted
            trap = case.base / "source-must-not-be-opened"
            roots = {dataset: trap for dataset in case.source_roots}
            result = self.run_cli(case, evidence, roots)
            self.assertEqual(result.returncode, 2)
            self.assertIn("evidence MANIFEST hash mismatch", result.stderr)
            self.assertNotIn("source root", result.stderr)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

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

    def test_zero_row_structure_identity_is_preflighted(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            structure = case.source_roots["n_baiot"] / "demonstrate_structure.csv"
            with structure.open("ab") as handle:
                handle.write(b"999,999\n")
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "byte size mismatch"):
                self.run_case(case)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

    def test_rebound_structure_file_must_still_have_zero_rows(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            structure = case.source_roots["n_baiot"] / "demonstrate_structure.csv"
            with structure.open("ab") as handle:
                handle.write(b"999,999\n")
            case.refresh_metadata()
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "must be the one frozen zero-row file"):
                self.run_case(case)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

    def test_unregistered_non_lf_normal_record_fails_before_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            ton = case.source_roots["ton_iot"] / "train_test_network.csv"
            ton.write_bytes(ton.read_bytes().removesuffix(b"\n"))
            case.refresh_metadata()
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "unregistered non-LF terminal record"):
                self.run_case(case)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

    def test_exact_registered_cic_exceptions_are_non_lf_and_succeed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            exception_path = case.package / "inputs/quality_exceptions/cic.json"
            exception_data = json.loads(exception_path.read_text(encoding="utf-8"))
            self.assertEqual([item["ends_with_newline"]
                              for item in exception_data["exceptions"]],
                             [False, False, False])
            for path in (case.source_roots["ciciot2023"] /
                         "CSV/DoS-UDP_Flood").glob("*.csv"):
                self.assertFalse(path.read_bytes().endswith(b"\n"))
            result = self.run_case(case)
            self.assertEqual(
                result["dataset_results"]["ciciot2023"]["source_rows_excluded"], 3)

    def test_registered_exception_rebound_with_lf_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            target = (case.source_roots["ciciot2023"] /
                      "CSV/DoS-UDP_Flood/DoS-UDP_Flood7.pcap.csv")
            target.write_bytes(target.read_bytes() + b"\n")
            case.refresh_metadata()
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "must be a non-LF final line"):
                self.run_case(case)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

    def test_hash_only_replay_has_no_disk_peak_or_replay_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            cic = (case.source_roots["ciciot2023"] /
                   "CSV/Benign_Final/Benign_Final1.pcap.csv")
            cic.write_text("Header_Length,Protocol Type\n" +
                           "x" * 50000 + ",6\n" + "y" * 50000 + ",17\n",
                           encoding="utf-8")
            case.refresh_metadata()
            baseline = self.run_case(case)
            final_bytes = tree_bytes(case.output)
            self.assertEqual(baseline["output_bytes"], final_bytes)
            shutil.rmtree(case.output)
            reserve = 1024
            case.contract["storage"].update({
                "hard_output_cap_bytes": final_bytes,
                "scratch_reserve_bytes": reserve,
                "minimum_free_bytes": final_bytes + reserve,
            })
            case.rewrite_contract()
            capacity = final_bytes + reserve
            observed_staging_bytes = []
            replay_snapshots = []
            original_replay = materializer.replay_shard

            def controlled_free(_path: Path) -> int:
                current = tree_bytes(case.staging)
                observed_staging_bytes.append(current)
                return max(0, capacity - current)

            def replay_spy(*args: Any, **kwargs: Any) -> Any:
                before = tree_hashes(case.staging)
                result = original_replay(*args, **kwargs)
                after = tree_hashes(case.staging)
                replay_snapshots.append((before, after))
                return result

            with patch.object(materializer, "replay_shard", replay_spy):
                result = materializer._execute_authorized(
                    case.contract_path, case.source_roots,
                    free_bytes=controlled_free)
            self.assertEqual(result["output_bytes"], final_bytes)
            self.assertEqual(tree_bytes(case.output), final_bytes)
            self.assertLessEqual(max(observed_staging_bytes), final_bytes)
            self.assertEqual(len(replay_snapshots), 7)
            self.assertTrue(all(before == after
                                for before, after in replay_snapshots))
            self.assertFalse(any(".replay-" in path.parts
                                 for path in case.output.rglob("*")))

    def test_unregistered_malformed_row_fails_before_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            exception_path = case.package / "inputs/quality_exceptions/cic.json"
            changed = json.loads(exception_path.read_text(encoding="utf-8"))
            changed["exceptions"][0]["relative_path"] = \
                "CSV/DoS-UDP_Flood/not-the-registered-file.csv"
            write_json(exception_path, changed)
            case.contract["input_binding"]["cic_quality_exceptions"]["sha256"] = \
                sha256(exception_path)
            case.rewrite_contract()
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "unregistered malformed row"):
                self.run_case(case)
            self.assertFalse(case.output.exists())
            self.assertFalse(case.staging.exists())

    def test_unexpected_label_preserves_owned_staging_for_audit(self) -> None:
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
            self.assertTrue(case.staging.is_dir())
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

    def test_hard_budget_breach_preserves_owned_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            case.contract["storage"]["hard_output_cap_bytes"] = 1
            case.rewrite_contract()
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "hard output cap exceeded"):
                self.run_case(case)
            self.assertFalse(case.output.exists())
            self.assertTrue(case.staging.is_dir())

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

    def test_atomic_publish_refuses_late_destination_without_replacement(self) -> None:
        for destination_kind in ("empty_directory", "nonempty_directory",
                                 "regular_file", "symlink"):
            with self.subTest(destination_kind=destination_kind), \
                    tempfile.TemporaryDirectory() as temporary:
                case = self.make_case(temporary)
                original_validate = materializer.validate_bound_metadata
                calls = 0
                sentinel_target = case.destination / "symlink-target"

                def late_destination(*args: Any, **kwargs: Any) -> Dict[str, Any]:
                    nonlocal calls
                    result = original_validate(*args, **kwargs)
                    calls += 1
                    if calls == 2:
                        if destination_kind in ("empty_directory", "nonempty_directory"):
                            case.output.mkdir()
                            if destination_kind == "nonempty_directory":
                                (case.output / "sentinel").write_text(
                                    "keep", encoding="utf-8")
                        elif destination_kind == "regular_file":
                            case.output.write_text("keep", encoding="utf-8")
                        else:
                            sentinel_target.write_text("keep", encoding="utf-8")
                            case.output.symlink_to(sentinel_target)
                    return result

                with patch.object(materializer, "validate_bound_metadata",
                                  late_destination):
                    with self.assertRaisesRegex(
                            materializer.MaterializationError,
                            "final output appeared before publication"):
                        self.run_case(case)
                if destination_kind == "nonempty_directory":
                    self.assertEqual((case.output / "sentinel").read_text(), "keep")
                elif destination_kind == "regular_file":
                    self.assertEqual(case.output.read_text(), "keep")
                elif destination_kind == "symlink":
                    self.assertTrue(case.output.is_symlink())
                    self.assertEqual(sentinel_target.read_text(), "keep")
                else:
                    self.assertTrue(case.output.is_dir())
                    self.assertEqual(list(case.output.iterdir()), [])
                self.assertTrue(case.staging.is_dir())

    def test_replaced_staging_and_displaced_owned_tree_are_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            original_render = materializer.render_shard
            displaced = case.destination / "displaced-owned-staging"
            injected = False

            def replace_staging(*args: Any, **kwargs: Any) -> Any:
                nonlocal injected
                result = original_render(*args, **kwargs)
                if not injected:
                    injected = True
                    case.staging.rename(displaced)
                    case.staging.mkdir()
                    (case.staging / "FOREIGN_SENTINEL").write_text(
                        "keep", encoding="utf-8")
                    raise materializer.MaterializationError(
                        "synthetic replaced staging identity")
                return result

            with patch.object(materializer, "render_shard", replace_staging):
                with self.assertRaisesRegex(materializer.MaterializationError,
                                            "foreign staging identity preserved"):
                    self.run_case(case)
            self.assertEqual(
                (case.staging / "FOREIGN_SENTINEL").read_text(encoding="utf-8"),
                "keep")
            self.assertTrue(displaced.is_dir())
            self.assertFalse(case.output.exists())

    def test_injected_failure_preserves_owned_staging_and_neighbor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            case = self.make_case(temporary)
            neighbor = case.destination / "neighbor"
            neighbor.write_text("keep", encoding="utf-8")
            with self.assertRaisesRegex(materializer.MaterializationError,
                                        "synthetic injected failure"):
                self.run_case(case, fault_after_shards=1)
            self.assertFalse(case.output.exists())
            self.assertTrue(case.staging.is_dir())
            self.assertEqual(neighbor.read_text(encoding="utf-8"), "keep")

    def test_foreign_staging_identity_is_reported_without_deletion(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            output = base / "published"
            staging = base / ".published.staging"
            lease = materializer.create_staging_lease(output, staging)
            displaced = base / "owned-displaced"
            staging.rename(displaced)
            staging.mkdir()
            sentinel = staging / "sentinel"
            sentinel.write_text("keep", encoding="utf-8")
            detail = materializer.describe_preserved_staging(lease)
            lease.close()
            self.assertIn("foreign staging identity preserved", detail)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep")
            self.assertTrue(displaced.is_dir())


if __name__ == "__main__":
    unittest.main()
