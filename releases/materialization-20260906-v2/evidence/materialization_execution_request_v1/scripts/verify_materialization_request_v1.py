#!/usr/bin/env python3
"""Read-only verifier for MATERIALIZATION-20260906-V1-PROPOSED.

This verifier reads only the small files bundled in the request package. It
does not locate, open, hash, or otherwise inspect raw dataset CSV files, and it
does not create an output or staging directory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Tuple


EXPECTED_HASHES = {
    "inputs/acquisitions/ciciot2023_20260903T142351Z.json":
        "eec07c71d736c004fd0c64dff567495cfa38aec1330a059222ef15c435574f7c",
    "inputs/censuses/ton_iot_20260903T233742Z.json":
        "128fe883208eef10cd2f41bf8c5ee73bf518cb61b5d95c86cff40214565edfa0",
    "inputs/inventories/ciciot2023_20260903T142539Z.json":
        "d31472b21836eb5a5cfa9535e1f29d58c0a4a1f136586938172a3e77bbe2f45f",
    "inputs/inventories/n_baiot_20260903T224404Z.json":
        "9ffdf7e9245470fc4f066b8fb6d8ebae03e0194e7698e5fde87b13a7f2fe30da",
    "inputs/inventories/ton_iot_20260903T113048Z.json":
        "66179d1ba2601ff3175e90cbfb4ed21d28c859b5780258d5e36dd8bb2303c55a",
    "inputs/protocol/feature_policy.json":
        "e81a55c16f9439b0356295353e8b342de19d5c5606d868952592f913beda714b",
    "inputs/protocol/label_ontology.json":
        "8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab",
    "inputs/quality_exceptions/ciciot2023_20260903T142617Z.json":
        "36ef134ff6117867c51888749434f2d02efc59ec4ad6e93e94371f08d59e5bae",
    "inputs/reviews/feature_protocol_24_independent_acceptance.md":
        "c28c73112daae1126bb45094f1e4dd64df98d673018bbeca345ed914128d90c3",
}

REQUEST_PATH = "proposal/materialization_execution_request_v1.json"


class DuplicateKeyError(ValueError):
    pass


def _no_duplicate_pairs(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=_no_duplicate_pairs)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class Checks:
    def __init__(self) -> None:
        self.results: List[Tuple[bool, str]] = []

    def check(self, condition: bool, detail: str) -> None:
        self.results.append((bool(condition), detail))

    def equal(self, actual: Any, expected: Any, detail: str) -> None:
        self.check(actual == expected,
                   f"{detail}: observed={actual!r} expected={expected!r}")

    def report(self) -> int:
        for passed, detail in self.results:
            print(f"[{'PASS' if passed else 'FAIL'}] {detail}")
        passed = sum(1 for ok, _ in self.results if ok)
        total = len(self.results)
        print(f"SUMMARY {passed}/{total} checks passed")
        print("authorization_granted = false")
        print("data_gate_unlocked   = false")
        print("raw_csvs_opened      = false")
        return 0 if passed == total else 1


def inventory_checks(checks: Checks, dataset_id: str, inventory: Dict[str, Any],
                     expected_files: int, expected_bytes: int,
                     expected_rows: int, expected_columns: int) -> None:
    files = inventory["files"]
    checks.equal(inventory["dataset_id"], dataset_id,
                 f"{dataset_id} inventory dataset_id")
    checks.equal(inventory["file_count"], expected_files,
                 f"{dataset_id} inventory file_count")
    checks.equal(len(files), expected_files,
                 f"{dataset_id} inventory member count")
    checks.equal(inventory["total_bytes"], expected_bytes,
                 f"{dataset_id} inventory total_bytes")
    checks.equal(sum(item["bytes"] for item in files), expected_bytes,
                 f"{dataset_id} per-file bytes reconcile")
    checks.equal(inventory["total_rows"], expected_rows,
                 f"{dataset_id} inventory total_rows")
    checks.equal(sum(item["row_count"] for item in files), expected_rows,
                 f"{dataset_id} per-file rows reconcile")
    paths = [item["relative_path"] for item in files]
    hashes = [item["sha256"] for item in files]
    checks.equal(len(paths), len(set(paths)),
                 f"{dataset_id} relative paths unique")
    checks.equal(len(hashes), len(set(hashes)),
                 f"{dataset_id} source hashes unique")
    checks.equal({item["column_count"] for item in files}, {expected_columns},
                 f"{dataset_id} column count fixed")
    checks.equal(len({tuple(item["columns"]) for item in files}), 1,
                 f"{dataset_id} parsed header fixed")


def verify(root: Path) -> int:
    checks = Checks()
    root = root.resolve()

    raw_csvs = sorted(root.rglob("*.csv"))
    checks.equal(raw_csvs, [], "request package contains no raw CSV")

    for relative, expected in EXPECTED_HASHES.items():
        path = root / relative
        checks.check(path.is_file(), f"bundled input exists: {relative}")
        if path.is_file():
            checks.equal(sha256(path), expected,
                         f"bundled input SHA-256: {relative}")

    json_paths = sorted(root.rglob("*.json"))
    json_docs: Dict[str, Any] = {}
    for path in json_paths:
        relative = path.relative_to(root).as_posix()
        try:
            json_docs[relative] = load_json(path)
            checks.check(True, f"JSON parses with duplicate-key rejection: {relative}")
        except (OSError, UnicodeError, json.JSONDecodeError, DuplicateKeyError) as exc:
            checks.check(False, f"JSON parses with duplicate-key rejection: {relative}: {exc}")

    request = json_docs[REQUEST_PATH]
    policy = json_docs["inputs/protocol/feature_policy.json"]
    ontology = json_docs["inputs/protocol/label_ontology.json"]
    ton = json_docs["inputs/inventories/ton_iot_20260903T113048Z.json"]
    cic = json_docs["inputs/inventories/ciciot2023_20260903T142539Z.json"]
    nb = json_docs["inputs/inventories/n_baiot_20260903T224404Z.json"]
    census = json_docs["inputs/censuses/ton_iot_20260903T233742Z.json"]
    exceptions = json_docs[
        "inputs/quality_exceptions/ciciot2023_20260903T142617Z.json"]

    checks.equal(request["request_id"], "MATERIALIZATION-20260906-V1-PROPOSED",
                 "request identity")
    checks.equal(request["status"], "prepared_not_authorized",
                 "request status")
    checks.equal(request["scope"]["requested_operation"], "materialization",
                 "single requested operation")
    checks.equal(request["scope"]["materialization_only"], True,
                 "materialization-only flag")
    for operation in ("splitting", "training", "sampling", "balancing",
                      "model_fitting", "encoder_fitting",
                      "semantic_core_construction", "raw_input_mutation",
                      "frozen_config_mutation"):
        checks.equal(request["scope"][operation], "forbidden",
                     f"scope keeps {operation} forbidden")
    checks.equal(request["authorization"]["authorization_granted"], False,
                 "authorization remains false")
    checks.equal(request["authorization"]["data_gate_unlocked"], False,
                 "data gate remains locked")
    checks.equal(request["implementation_boundary"]["executor_included"], False,
                 "no executor is represented as reviewed")

    checks.equal(policy["status"], "frozen", "feature policy is frozen")
    checks.equal(ontology["status"], "frozen", "label ontology is frozen")
    for gate in ("materialization", "splitting", "training"):
        obj = policy["data_handling"][gate]
        checks.equal(obj["current"], "forbidden before protocol freeze",
                     f"{gate} current gate wording retained")
        checks.check(any("separate explicit user authorization for THIS gate"
                         in item for item in obj["preconditions"]),
                     f"{gate} retains separate authorization precondition")

    inventory_checks(checks, "ton_iot", ton, 1, 29902775, 211043, 44)
    inventory_checks(checks, "ciciot2023", cic, 309, 8943771319,
                     46776700, 39)
    inventory_checks(checks, "n_baiot", nb, 90, 8140825610, 7062606, 115)

    checks.equal(ton["all_rows_well_formed"], True,
                 "TON-IoT rows are inventoried well formed")
    checks.equal(cic["all_rows_well_formed"], False,
                 "CIC inventory exposes its registered malformed rows")
    checks.equal(nb["all_rows_well_formed"], True,
                 "N-BaIoT rows are inventoried well formed")

    exception_rows = exceptions["exceptions"]
    checks.equal(exceptions["exception_count"], 3,
                 "CIC exception_count")
    checks.equal(len(exception_rows), 3, "CIC exception member count")
    cic_by_path = {item["relative_path"]: item for item in cic["files"]}
    expected_exception_paths = {
        "CSV/DoS-UDP_Flood/DoS-UDP_Flood7.pcap.csv",
        "CSV/DoS-UDP_Flood/DoS-UDP_Flood8.pcap.csv",
        "CSV/DoS-UDP_Flood/DoS-UDP_Flood9.pcap.csv",
    }
    checks.equal({item["relative_path"] for item in exception_rows},
                 expected_exception_paths, "CIC exact exception paths")
    exception_bindings_ok = True
    for item in exception_rows:
        source = cic_by_path.get(item["relative_path"])
        exception_bindings_ok = exception_bindings_ok and source is not None
        if source is not None:
            exception_bindings_ok = exception_bindings_ok and (
                item["file_sha256"] == source["sha256"]
                and item["file_bytes"] == source["bytes"]
                and item["logical_row_count_in_file"] == source["row_count"]
                and item["physical_line"] == source["row_count"] + 1
                and item["is_last_line"] is True
                and item["expected_column_count"] == 39
                and item["observed_column_count_line_scan"] < 39
            )
    checks.check(exception_bindings_ok,
                 "CIC exceptions bind exact inventoried files and final rows")

    demo = [item for item in nb["files"]
            if item["relative_path"] == "demonstrate_structure.csv"]
    checks.equal(len(demo), 1, "N-BaIoT has one structure example")
    checks.equal((demo[0]["bytes"], demo[0]["row_count"], demo[0]["sha256"]),
                 (1776, 0,
                  "7ef0a9e20164c601b8f79311174a32758e5a3bd4e8bb525627369af8cf3fcb6f"),
                 "N-BaIoT structure example exact identity")

    expected_totals = {
        "inventoried_csv_files": 400,
        "materialized_data_shards": 399,
        "source_bytes": 17114499704,
        "raw_rows": 54050349,
        "accepted_rows": 54050346,
        "registered_excluded_rows": 3,
    }
    checks.equal(request["frozen_inputs"]["totals"], expected_totals,
                 "request aggregate input/output counts")

    ton_columns = ton["files"][0]["columns"]
    proposal_excluded = request["deterministic_materialization_contract"][
        "ton_iot"]["excluded_feature_columns"]
    policy_excluded = policy["ton_iot_exclusions"]["permanent"]["columns"]
    policy_ports = policy["ton_iot_exclusions"]["port_columns"]["columns"]
    checks.equal(set(proposal_excluded), set(policy_excluded + policy_ports),
                 "TON exclusions equal frozen permanent plus port columns")
    ton_features = [name for name in ton_columns if name not in proposal_excluded]
    checks.equal(len(ton_features), 32, "TON output feature count")
    checks.equal(request["deterministic_materialization_contract"]["ton_iot"]
                 ["output_feature_count"], 32,
                 "request declares TON 32 features")
    categorical = policy["ton_iot_exclusions"]["categorical_native_only"]["columns"]
    checks.check(set(categorical).issubset(ton_features),
                 "TON permitted categoricals stay native features")
    checks.equal(cic["files"][0]["columns"],
                 policy["primary_native_feature_sets"]["ciciot2023"]["columns"],
                 "CIC 39-column inventory matches frozen native feature order")

    ton_map = ontology["canonical_family"]["ton_iot_type_mapping"]["entries"]
    checks.equal({item["source_type"] for item in ton_map},
                 set(census["type_counts"]),
                 "TON frozen type map covers census values")
    checks.equal(census["total_rows"], 211043,
                 "TON census total rows")
    checks.equal(sum(census["label_counts"].values()), 211043,
                 "TON census label rows reconcile")

    cic_categories = {PurePosixPath(item["relative_path"]).parts[1]
                      for item in cic["files"]}
    cic_map = ontology["canonical_family"]["ciciot2023_type_mapping"]["entries"]
    checks.equal({item["source_type"] for item in cic_map}, cic_categories,
                 "CIC frozen map covers all and only inventoried categories")
    checks.equal(len(cic_categories), 34, "CIC category count")

    nb_pairs = set()
    nb_paths_ok = True
    for item in nb["files"]:
        path = PurePosixPath(item["relative_path"])
        if item["relative_path"] == "demonstrate_structure.csv":
            continue
        if path.name == "benign_traffic.csv" and len(path.parts) == 2:
            nb_pairs.add(("benign", "benign_traffic"))
        elif len(path.parts) == 3 and path.suffix == ".csv":
            nb_pairs.add((path.parts[1], path.stem))
        else:
            nb_paths_ok = False
    checks.check(nb_paths_ok, "N-BaIoT paths match frozen derivation grammar")
    nb_map = ontology["canonical_family"]["n_baiot_type_mapping"]["entries"]
    checks.equal({(item["source_family"], item["source_subtype"])
                  for item in nb_map}, nb_pairs,
                 "N-BaIoT frozen map covers all and only inventoried labels")

    budget = request["disk_budget"]
    source_bytes = expected_totals["source_bytes"]
    output_cap = (3 * source_bytes + 1) // 2
    checks.equal(budget["hard_output_cap_bytes"], output_cap,
                 "hard output cap formula")
    checks.equal(budget["minimum_free_bytes_before_execution"],
                 output_cap + budget["scratch_and_validation_reserve_bytes"],
                 "minimum free-space formula")
    observation = budget["preparation_time_observation"]
    checks.equal(observation["passes"], False,
                 "preparation storage observation blocks execution")
    checks.equal(observation["shortfall_bytes"],
                 observation["minimum_free_bytes"] - observation["available_bytes"],
                 "storage shortfall arithmetic")
    checks.check(Path(request["output"]["root"]).is_absolute(),
                 "fixed output root is absolute")
    checks.check(Path(request["output"]["staging_root"]).is_absolute(),
                 "fixed staging root is absolute")
    checks.check(Path(request["output"]["root"]).parent ==
                 Path(request["output"]["staging_root"]).parent,
                 "output and staging roots share a filesystem parent")

    return checks.report()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root", type=Path,
        default=Path(__file__).resolve().parents[1],
        help="request package root (default: parent of scripts directory)")
    args = parser.parse_args()
    return verify(args.root)


if __name__ == "__main__":
    sys.exit(main())
