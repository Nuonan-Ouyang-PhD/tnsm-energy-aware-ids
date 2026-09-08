#!/usr/bin/env python3
"""Deterministic dataset-native materializer with a fail-closed run guard.

The command-line entry point cannot read a source CSV until it has validated a
separate user authorization record, the accepted request ZIP, the approved
executor-evidence ZIP, and an append-only decision record. Synthetic tests call
the internal authorized function directly with invented temporary fixtures;
that internal function is deliberately not exposed as a CLI bypass.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import shutil
import sys
import tempfile
from collections import Counter
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple


class MaterializationError(RuntimeError):
    """Fail-closed contract or execution error."""


class DuplicateKeyError(ValueError):
    pass


def _no_duplicate_pairs(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError("duplicate JSON key: %s" % key)
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"),
                          object_pairs_hook=_no_duplicate_pairs)
    except (OSError, UnicodeError, json.JSONDecodeError, DuplicateKeyError) as exc:
        raise MaterializationError("cannot load JSON %s: %s" % (path, exc)) from exc


def canonical_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
        "utf-8")


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
    except OSError as exc:
        raise MaterializationError("cannot hash %s: %s" % (path, exc)) from exc
    return digest.hexdigest()


def utf8_sort(values: Iterable[str]) -> List[str]:
    return sorted(values, key=lambda item: item.encode("utf-8"))


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


def nearest_existing_parent(path: Path) -> Path:
    candidate = path.resolve(strict=False)
    while not candidate.exists():
        if candidate.parent == candidate:
            raise MaterializationError("no existing ancestor for output path")
        candidate = candidate.parent
    if not candidate.is_dir():
        raise MaterializationError("nearest output ancestor is not a directory: %s" % candidate)
    return candidate


def default_free_bytes(path: Path) -> int:
    return shutil.disk_usage(str(path)).free


def parse_physical_csv_line(raw: bytes, path: Path, physical_line: int) -> List[str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise MaterializationError(
            "%s physical line %d is not strict UTF-8" % (path, physical_line)) from exc
    if text.endswith("\n"):
        text = text[:-1]
        if text.endswith("\r"):
            text = text[:-1]
    elif text.endswith("\r"):
        text = text[:-1]
    try:
        rows = list(csv.reader([text], delimiter=",", quotechar='"',
                               doublequote=True, strict=True))
    except csv.Error as exc:
        raise MaterializationError(
            "%s physical line %d is not a single valid CSV record: %s" %
            (path, physical_line, exc)) from exc
    if len(rows) != 1:
        raise MaterializationError(
            "%s physical line %d did not yield exactly one record" %
            (path, physical_line))
    return rows[0]


def hash_raw_line(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


@dataclass(frozen=True)
class SourceScan:
    relative_path: str
    source_path: Path
    row_count: int
    excluded_rows: Tuple[Dict[str, Any], ...]
    sha256: str
    bytes: int


@dataclass
class RenderedShard:
    dataset_id: str
    relative_path: str
    row_count: int
    excluded_rows: List[Dict[str, Any]]
    binary_counts: Counter
    features_sha256: str
    features_bytes: int
    labels_sha256: str
    labels_bytes: int
    source_sha256_replayed: str


class ByteBudget:
    def __init__(self, hard_cap: int) -> None:
        self.hard_cap = hard_cap
        self.written = 0

    def reserve(self, amount: int) -> None:
        if amount < 0 or self.written + amount > self.hard_cap:
            raise MaterializationError(
                "hard output cap exceeded: attempted=%d cap=%d" %
                (self.written + amount, self.hard_cap))
        self.written += amount


class BudgetTextSink:
    """Minimal text sink for csv.writer with byte-accurate budget control."""

    def __init__(self, handle: Any, budget: Optional[ByteBudget]) -> None:
        self.handle = handle
        self.budget = budget

    def write(self, text: str) -> int:
        data = text.encode("utf-8")
        if self.budget is not None:
            self.budget.reserve(len(data))
        self.handle.write(data)
        return len(text)


def write_canonical_json(path: Path, value: Any,
                         budget: Optional[ByteBudget]) -> None:
    data = canonical_json_bytes(value)
    if budget is not None:
        budget.reserve(len(data))
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(data)
    except OSError as exc:
        raise MaterializationError("cannot write %s: %s" % (path, exc)) from exc


def write_canonical_jsonl(path: Path, values: Sequence[Mapping[str, Any]],
                          budget: Optional[ByteBudget]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            for value in values:
                data = canonical_json_bytes(value)
                if budget is not None:
                    budget.reserve(len(data))
                handle.write(data)
    except OSError as exc:
        raise MaterializationError("cannot write %s: %s" % (path, exc)) from exc


def contract_package_root(contract_path: Path) -> Path:
    resolved = contract_path.resolve()
    if resolved.parent.name != "contract":
        raise MaterializationError("contract must be inside a contract directory")
    return resolved.parents[1]


def validate_contract_shape(contract: Mapping[str, Any]) -> None:
    if contract.get("kind") != "materialization_executor_contract":
        raise MaterializationError("wrong contract kind")
    if contract.get("operation") != "materialization":
        raise MaterializationError("contract is not materialization-only")
    if contract["authorization"]["granted"] is not False:
        raise MaterializationError("the evidence contract must not grant authorization")
    required_operations = contract["authorization"]["required_operations"]
    if required_operations != {
            "materialization": True,
            "splitting": False,
            "training": False,
            "encoder_fitting": False,
            "model_fitting": False}:
        raise MaterializationError("operation boundary changed")
    label = contract["label_sidecar"]
    if label["columns"] != ["binary_label", "canonical_family", "source_family",
                            "source_subtype"]:
        raise MaterializationError("label sidecar columns changed")
    if label["binary_label_values"] != ["benign", "attack"]:
        raise MaterializationError("binary label values changed")
    if label["ton_iot"]["binary_label_map"] != {"0": "benign", "1": "attack"}:
        raise MaterializationError("TON binary label rule changed")
    if label["ton_iot"]["source_family"] != "" or \
            label["ciciot2023"]["source_family"] != "":
        raise MaterializationError("TON/CIC source_family must be an empty CSV cell")
    output = contract["output_binding"]
    root = Path(output["root"])
    staging = Path(output["staging_root"])
    if not root.is_absolute() or not staging.is_absolute() or root == staging:
        raise MaterializationError("output and staging must be distinct absolute paths")
    if root.parent != staging.parent:
        raise MaterializationError("output and staging must share one parent")
    if staging.name != ".%s.staging" % root.name:
        raise MaterializationError("staging name is not the exact safe sibling form")
    ordering = contract["ordering"]
    if ordering["shard_ordinal_scope"] != "restart independently for each dataset" or \
            ordering["shard_ordinal_start"] != 1 or \
            ordering["shard_ordinal_format"] != "four decimal digits, zero padded":
        raise MaterializationError("shard ordinal rule changed")
    if contract["root_manifest"]["self_entry"] is not False:
        raise MaterializationError("root manifest must exclude itself")
    source_csv = contract["source_csv_reading"]
    if source_csv["record_boundary"] != \
            "one physical LF-terminated line is one CSV record" or \
            not source_csv["quoted_multiline_fields"].startswith("forbidden") or \
            source_csv["terminal_newline"] != \
            "required for every source record, including the final physical line":
        raise MaterializationError("source CSV physical-record contract changed")


def validate_bound_metadata(contract: Mapping[str, Any], package_root: Path) -> Dict[str, Any]:
    documents: Dict[str, Any] = {}
    bindings: List[Tuple[str, Mapping[str, Any]]] = [
        ("feature_policy", contract["input_binding"]["feature_policy"]),
        ("label_ontology", contract["input_binding"]["label_ontology"]),
        ("ton_label_census", contract["input_binding"]["ton_label_census"]),
        ("cic_quality_exceptions", contract["input_binding"]["cic_quality_exceptions"]),
    ]
    bindings.extend((dataset_id, item) for dataset_id, item in
                    contract["input_binding"]["inventories"].items())
    bindings.append(("baseline_request", {
        "file": contract["baseline_request"]["request_json"],
        "sha256": contract["baseline_request"]["request_json_sha256"],
    }))
    for name, binding in bindings:
        path = package_root / binding["file"]
        if not path.is_file():
            raise MaterializationError("missing bound metadata: %s" % path)
        observed = sha256_path(path)
        if observed != binding["sha256"]:
            raise MaterializationError(
                "bound metadata hash mismatch for %s: %s" % (name, observed))
        documents[name] = load_json(path)
    if documents["feature_policy"].get("status") != "frozen" or \
            documents["label_ontology"].get("status") != "frozen":
        raise MaterializationError("live protocol copies are not frozen")
    return documents


def validate_authorization(contract: Mapping[str, Any], authorization_path: Path,
                           request_zip: Path, evidence_zip: Path,
                           decisions_path: Path) -> Dict[str, Any]:
    """Validate all external authorization evidence before source access."""
    if not authorization_path.is_file():
        raise MaterializationError("authorization record missing")
    authorization = load_json(authorization_path)
    if authorization.get("kind") != "materialization_execution_authorization":
        raise MaterializationError("wrong authorization record kind")
    if authorization.get("authorized_by_user") is not True:
        raise MaterializationError("explicit user authorization is absent")
    if authorization.get("contract_id") != contract["contract_id"]:
        raise MaterializationError("authorization contract_id mismatch")
    if authorization.get("request_zip_sha256") != \
            contract["baseline_request"]["request_zip_sha256"]:
        raise MaterializationError("authorization request ZIP binding mismatch")
    if authorization.get("operations") != \
            contract["authorization"]["required_operations"]:
        raise MaterializationError("authorization operation boundary mismatch")
    if authorization.get("output_root") != contract["output_binding"]["root"]:
        raise MaterializationError("authorization output root mismatch")
    if not request_zip.is_file() or sha256_path(request_zip) != \
            contract["baseline_request"]["request_zip_sha256"]:
        raise MaterializationError("accepted request ZIP is missing or changed")
    if not evidence_zip.is_file():
        raise MaterializationError("approved executor evidence ZIP missing")
    evidence_hash = sha256_path(evidence_zip)
    if authorization.get("executor_evidence_zip_sha256") != evidence_hash:
        raise MaterializationError("executor evidence ZIP binding mismatch")
    if not decisions_path.is_file():
        raise MaterializationError("DECISIONS.md missing")
    try:
        decisions = decisions_path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise MaterializationError("cannot read DECISIONS.md: %s" % exc) from exc
    required_text = [
        authorization.get("authorization_id"),
        contract["contract_id"],
        contract["baseline_request"]["request_zip_sha256"],
        evidence_hash,
        contract["output_binding"]["root"],
    ]
    if any(not isinstance(item, str) or not item or item not in decisions
           for item in required_text):
        raise MaterializationError("DECISIONS.md does not contain every authorization binding")
    return authorization


def validate_output_paths(contract: Mapping[str, Any], source_roots: Mapping[str, Path],
                          free_bytes: Callable[[Path], int]) -> Tuple[Path, Path]:
    output = Path(contract["output_binding"]["root"]).resolve(strict=False)
    staging = Path(contract["output_binding"]["staging_root"]).resolve(strict=False)
    if output == staging or output.parent != staging.parent or \
            staging.name != ".%s.staging" % output.name:
        raise MaterializationError("unsafe output/staging relationship")
    if output == Path(output.anchor) or staging == Path(staging.anchor):
        raise MaterializationError("filesystem root cannot be an output or staging path")
    if output.exists():
        raise MaterializationError("final output already exists; overwrite forbidden")
    if staging.exists():
        raise MaterializationError("staging already exists; modification forbidden")
    if not output.parent.is_dir():
        raise MaterializationError("fixed output parent must already exist")
    for dataset_id, source in source_roots.items():
        resolved = source.resolve(strict=False)
        if _is_relative_to(output, resolved) or _is_relative_to(staging, resolved) or \
                _is_relative_to(resolved, output) or _is_relative_to(resolved, staging):
            raise MaterializationError("%s source overlaps output paths" % dataset_id)
    ancestor = nearest_existing_parent(output.parent)
    observed_free = free_bytes(ancestor)
    minimum = int(contract["storage"]["minimum_free_bytes"])
    if observed_free < minimum:
        raise MaterializationError(
            "insufficient free space: observed=%d required=%d" %
            (observed_free, minimum))
    return output, staging


def expected_exception_index(exception_manifest: Mapping[str, Any]) -> Dict[Tuple[str, int], Dict[str, Any]]:
    result: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for item in exception_manifest["exceptions"]:
        key = (item["relative_path"], item["physical_line"])
        if key in result:
            raise MaterializationError("duplicate quality exception")
        result[key] = item
    return result


def normalize_excluded_row(item: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "physical_line": int(item["physical_line"]),
        "source_row": int(item["physical_line"]) - 1,
        "raw_line_bytes": int(item["raw_line_bytes"]),
        "raw_line_sha256": item["raw_line_sha256"],
        "observed_column_count": int(item["observed_column_count_line_scan"]),
        "expected_column_count": int(item["expected_column_count"]),
    }


def match_exception(relative_path: str, physical_line: int, raw: bytes,
                    observed_columns: int, source_item: Mapping[str, Any],
                    exception_index: Mapping[Tuple[str, int], Mapping[str, Any]]) -> Optional[Dict[str, Any]]:
    item = exception_index.get((relative_path, physical_line))
    if item is None:
        return None
    conditions = [
        item["file_sha256"] == source_item["sha256"],
        item["file_bytes"] == source_item["bytes"],
        item["is_last_line"] is True,
        item["logical_row_count_in_file"] == source_item["row_count"],
        item["physical_line"] == source_item["row_count"] + 1,
        item["raw_line_bytes"] == len(raw),
        item["raw_line_sha256"] == hash_raw_line(raw),
        item["observed_column_count_line_scan"] == observed_columns,
        item["expected_column_count"] == source_item["column_count"],
    ]
    if not all(conditions):
        raise MaterializationError(
            "registered exception does not exactly match %s line %d" %
            (relative_path, physical_line))
    return normalize_excluded_row(item)


def scan_source_file(root: Path, source_item: Mapping[str, Any],
                     exception_index: Mapping[Tuple[str, int], Mapping[str, Any]]) -> SourceScan:
    relative_path = source_item["relative_path"]
    path = root / PurePosixPath(relative_path)
    if path.is_symlink() or not path.is_file():
        raise MaterializationError("source is missing, non-regular, or symlinked: %s" % path)
    stat_result = path.stat()
    if stat_result.st_size != source_item["bytes"]:
        raise MaterializationError("source byte size mismatch: %s" % relative_path)
    digest = hashlib.sha256()
    row_count = 0
    excluded: List[Dict[str, Any]] = []
    seen_exception_keys: Set[Tuple[str, int]] = set()
    try:
        with path.open("rb") as handle:
            header_raw = handle.readline()
            digest.update(header_raw)
            header = parse_physical_csv_line(header_raw, path, 1)
            if header != source_item["columns"]:
                raise MaterializationError("source header mismatch: %s" % relative_path)
            for physical_line, raw in enumerate(handle, start=2):
                digest.update(raw)
                row_count += 1
                row = parse_physical_csv_line(raw, path, physical_line)
                if len(row) != source_item["column_count"]:
                    matched = match_exception(relative_path, physical_line, raw,
                                              len(row), source_item, exception_index)
                    if matched is None:
                        raise MaterializationError(
                            "unregistered malformed row: %s line %d" %
                            (relative_path, physical_line))
                    excluded.append(matched)
                    seen_exception_keys.add((relative_path, physical_line))
                elif (relative_path, physical_line) in exception_index:
                    raise MaterializationError(
                        "registered exception is unexpectedly well formed: %s line %d" %
                        (relative_path, physical_line))
    except OSError as exc:
        raise MaterializationError("cannot scan source %s: %s" % (path, exc)) from exc
    if row_count != source_item["row_count"]:
        raise MaterializationError("source row count mismatch: %s" % relative_path)
    observed_hash = digest.hexdigest()
    if observed_hash != source_item["sha256"]:
        raise MaterializationError("source SHA-256 mismatch: %s" % relative_path)
    expected_keys = {key for key in exception_index if key[0] == relative_path}
    if seen_exception_keys != expected_keys:
        raise MaterializationError("registered exception coverage mismatch: %s" % relative_path)
    return SourceScan(relative_path=relative_path, source_path=path,
                      row_count=row_count, excluded_rows=tuple(excluded),
                      sha256=observed_hash, bytes=stat_result.st_size)


def data_source_items(dataset_id: str, inventory: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    items = list(inventory["files"])
    if dataset_id == "n_baiot":
        items = [item for item in items
                 if item["relative_path"] != "demonstrate_structure.csv"]
    return sorted(items, key=lambda item: item["relative_path"].encode("utf-8"))


def validate_source_set(dataset_id: str, root: Path,
                        inventory: Mapping[str, Any]) -> None:
    if root.is_symlink() or not root.is_dir():
        raise MaterializationError("source root missing, non-directory, or symlinked: %s" % root)
    actual: List[str] = []
    for path in root.rglob("*.csv"):
        if path.is_symlink() or not path.is_file():
            raise MaterializationError("symlinked or non-regular CSV under source root: %s" % path)
        actual.append(path.relative_to(root).as_posix())
    expected = [item["relative_path"] for item in inventory["files"]]
    if utf8_sort(actual) != utf8_sort(expected):
        raise MaterializationError("%s source CSV set differs from inventory" % dataset_id)


def preflight_sources(contract: Mapping[str, Any], documents: Mapping[str, Any],
                      source_roots: Mapping[str, Path]) -> Dict[str, List[SourceScan]]:
    exception_index = expected_exception_index(documents["cic_quality_exceptions"])
    result: Dict[str, List[SourceScan]] = {}
    seen_exceptions: Set[Tuple[str, int]] = set()
    for dataset_id in contract["ordering"]["dataset_order"]:
        inventory = documents[dataset_id]
        root = source_roots[dataset_id]
        validate_source_set(dataset_id, root, inventory)
        scans: List[SourceScan] = []
        for item in data_source_items(dataset_id, inventory):
            index = exception_index if dataset_id == "ciciot2023" else {}
            scan = scan_source_file(root, item, index)
            scans.append(scan)
            for excluded in scan.excluded_rows:
                seen_exceptions.add((scan.relative_path, excluded["physical_line"]))
        result[dataset_id] = scans
    if seen_exceptions != set(exception_index):
        raise MaterializationError("not every registered CIC exception was observed")
    return result


def ontology_lookups(ontology: Mapping[str, Any]) -> Dict[str, Any]:
    canonical = ontology["canonical_family"]
    ton = {item["source_type"]: item["canonical_family"]
           for item in canonical["ton_iot_type_mapping"]["entries"]}
    cic = {item["source_type"]: item["canonical_family"]
           for item in canonical["ciciot2023_type_mapping"]["entries"]}
    nb = {(item["source_family"], item["source_subtype"]):
          item["canonical_family"]
          for item in canonical["n_baiot_type_mapping"]["entries"]}
    return {"ton_iot": ton, "ciciot2023": cic, "n_baiot": nb}


def source_metadata(dataset_id: str, relative_path: str) -> Dict[str, Any]:
    parts = PurePosixPath(relative_path).parts
    if dataset_id == "ton_iot":
        return {"device_id": None, "capture_id": None,
                "source_family": None, "source_subtype": None}
    if dataset_id == "ciciot2023":
        if len(parts) != 3 or parts[0] != "CSV" or not parts[2].endswith(".pcap.csv"):
            raise MaterializationError("unexpected CIC source path: %s" % relative_path)
        category = parts[1]
        capture = parts[2][:-len(".pcap.csv")]
        return {"device_id": None, "capture_id": capture,
                "source_family": "", "source_subtype": category}
    if dataset_id == "n_baiot":
        if len(parts) == 2 and parts[1] == "benign_traffic.csv":
            device, family, subtype = parts[0], "benign", "benign_traffic"
        elif len(parts) == 3 and parts[2].endswith(".csv"):
            device, family, subtype = parts[0], parts[1], parts[2][:-4]
        else:
            raise MaterializationError("unexpected N-BaIoT source path: %s" % relative_path)
        return {"device_id": device,
                "capture_id": [device, family, subtype],
                "source_family": family, "source_subtype": subtype}
    raise MaterializationError("unexpected dataset_id: %s" % dataset_id)


def feature_columns(contract: Mapping[str, Any], dataset_id: str,
                    source_columns: Sequence[str]) -> List[str]:
    excluded = set(contract["feature_contract"][dataset_id]["excluded"])
    result = [name for name in source_columns if name not in excluded]
    expected = contract["feature_contract"][dataset_id]["output_columns"]
    if len(result) != expected:
        raise MaterializationError("%s feature count mismatch" % dataset_id)
    return result


def label_values(dataset_id: str, row: Sequence[str], header_index: Mapping[str, int],
                 metadata: Mapping[str, Any], lookups: Mapping[str, Any]) -> List[str]:
    if dataset_id == "ton_iot":
        raw_label = row[header_index["label"]]
        raw_type = row[header_index["type"]]
        binary_map = {"0": "benign", "1": "attack"}
        if raw_label not in binary_map or raw_type not in lookups["ton_iot"]:
            raise MaterializationError("unexpected TON label/type")
        binary = binary_map[raw_label]
        canonical = lookups["ton_iot"][raw_type]
        if (binary == "benign") != (canonical == "benign"):
            raise MaterializationError("TON binary/family inconsistency")
        return [binary, canonical, "", raw_type]
    if dataset_id == "ciciot2023":
        subtype = metadata["source_subtype"]
        if subtype not in lookups["ciciot2023"]:
            raise MaterializationError("unexpected CIC category")
        binary = "benign" if subtype == "Benign_Final" else "attack"
        canonical = lookups["ciciot2023"][subtype]
        if (binary == "benign") != (canonical == "benign"):
            raise MaterializationError("CIC binary/family inconsistency")
        return [binary, canonical, "", subtype]
    family = metadata["source_family"]
    subtype = metadata["source_subtype"]
    pair = (family, subtype)
    if pair not in lookups["n_baiot"]:
        raise MaterializationError("unexpected N-BaIoT family/subtype")
    binary = "benign" if family == "benign" else "attack"
    canonical = lookups["n_baiot"][pair]
    if (binary == "benign") != (canonical == "benign"):
        raise MaterializationError("N-BaIoT binary/family inconsistency")
    return [binary, canonical, family, subtype]


def render_shard(contract: Mapping[str, Any], dataset_id: str,
                 source_item: Mapping[str, Any], source_path: Path,
                 exception_index: Mapping[Tuple[str, int], Mapping[str, Any]],
                 lookups: Mapping[str, Any], features_path: Path,
                 labels_path: Path, budget: Optional[ByteBudget]) -> RenderedShard:
    columns = source_item["columns"]
    output_columns = feature_columns(contract, dataset_id, columns)
    header_index = {name: index for index, name in enumerate(columns)}
    selected_indexes = [header_index[name] for name in output_columns]
    metadata = source_metadata(dataset_id, source_item["relative_path"])
    features_path.parent.mkdir(parents=True, exist_ok=True)
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    binary_counts: Counter = Counter()
    excluded: List[Dict[str, Any]] = []
    source_digest = hashlib.sha256()
    accepted = 0
    try:
        with source_path.open("rb") as source, \
                features_path.open("xb") as feature_handle, \
                labels_path.open("xb") as label_handle:
            feature_writer = csv.writer(
                BudgetTextSink(feature_handle, budget), delimiter=",", quotechar='"',
                quoting=csv.QUOTE_MINIMAL, doublequote=True, lineterminator="\n")
            label_writer = csv.writer(
                BudgetTextSink(label_handle, budget), delimiter=",", quotechar='"',
                quoting=csv.QUOTE_MINIMAL, doublequote=True, lineterminator="\n")
            feature_writer.writerow(output_columns)
            label_writer.writerow(contract["label_sidecar"]["columns"])
            header_raw = source.readline()
            source_digest.update(header_raw)
            if parse_physical_csv_line(header_raw, source_path, 1) != columns:
                raise MaterializationError("header changed during render")
            for physical_line, raw in enumerate(source, start=2):
                source_digest.update(raw)
                row = parse_physical_csv_line(raw, source_path, physical_line)
                if len(row) != source_item["column_count"]:
                    matched = match_exception(source_item["relative_path"],
                                              physical_line, raw, len(row),
                                              source_item, exception_index)
                    if matched is None:
                        raise MaterializationError("unregistered malformed render row")
                    excluded.append(matched)
                    continue
                if (source_item["relative_path"], physical_line) in exception_index:
                    raise MaterializationError("registered exception rendered as valid")
                labels = label_values(dataset_id, row, header_index, metadata, lookups)
                feature_writer.writerow([row[index] for index in selected_indexes])
                label_writer.writerow(labels)
                binary_counts[labels[0]] += 1
                accepted += 1
    except OSError as exc:
        raise MaterializationError("cannot render %s: %s" % (source_path, exc)) from exc
    if accepted != source_item["row_count"] - len(excluded):
        raise MaterializationError("accepted row count changed during render")
    return RenderedShard(
        dataset_id=dataset_id, relative_path=source_item["relative_path"],
        row_count=accepted, excluded_rows=excluded, binary_counts=binary_counts,
        features_sha256=sha256_path(features_path),
        features_bytes=features_path.stat().st_size,
        labels_sha256=sha256_path(labels_path),
        labels_bytes=labels_path.stat().st_size,
        source_sha256_replayed=source_digest.hexdigest())


def safe_cleanup_created_staging(staging: Path, output: Path,
                                 created_by_this_process: bool) -> None:
    if not created_by_this_process or not staging.exists():
        return
    resolved_staging = staging.resolve(strict=False)
    resolved_output = output.resolve(strict=False)
    safe = (
        resolved_staging != Path(resolved_staging.anchor)
        and resolved_output != Path(resolved_output.anchor)
        and resolved_staging.parent == resolved_output.parent
        and resolved_staging.name == ".%s.staging" % resolved_output.name
        and resolved_staging != resolved_output
    )
    if not safe:
        raise MaterializationError("refusing cleanup outside exact staging containment")
    shutil.rmtree(str(resolved_staging))


def manifest_bytes(root: Path) -> bytes:
    paths = []
    for path in root.rglob("*"):
        if path.is_file():
            relative = path.relative_to(root).as_posix()
            if relative != "MANIFEST_SHA256.txt":
                paths.append(relative)
    lines = ["%s  %s\n" % (sha256_path(root / relative), relative)
             for relative in utf8_sort(paths)]
    return "".join(lines).encode("utf-8")


def verify_root_manifest(root: Path) -> None:
    manifest = root / "MANIFEST_SHA256.txt"
    if not manifest.is_file():
        raise MaterializationError("root manifest missing")
    observed = manifest.read_bytes()
    expected = manifest_bytes(root)
    if observed != expected:
        raise MaterializationError("root manifest coverage/hash mismatch")
    if b"MANIFEST_SHA256.txt" in observed:
        raise MaterializationError("root manifest contains a self-entry")


def validate_expected_counts(contract: Mapping[str, Any], dataset_results: Mapping[str, Any]) -> None:
    expected = contract["expected_real_output"]
    total_shards = sum(item["shard_count"] for item in dataset_results.values())
    total_rows = sum(item["rows_materialized"] for item in dataset_results.values())
    total_excluded = sum(item["source_rows_excluded"] for item in dataset_results.values())
    if total_shards != expected["feature_shards"] or \
            total_shards != expected["label_shards"] or \
            total_rows != expected["materialized_rows"] or \
            total_excluded != expected["excluded_rows"]:
        raise MaterializationError("aggregate output count mismatch")
    for dataset_id, dataset_expected in expected["per_dataset"].items():
        observed = dataset_results[dataset_id]
        if observed["shard_count"] != dataset_expected["shards"] or \
                observed["feature_count"] != dataset_expected["features"] or \
                observed["rows_materialized"] != dataset_expected["rows"] or \
                observed["binary_counts"] != {
                    "benign": dataset_expected["benign"],
                    "attack": dataset_expected["attack"]}:
            raise MaterializationError("%s expected output mismatch" % dataset_id)


def _execute_authorized(contract_path: Path, source_roots: Mapping[str, Path],
                        free_bytes: Callable[[Path], int] = default_free_bytes,
                        fault_after_shards: Optional[int] = None,
                        replay: bool = True) -> Dict[str, Any]:
    """Execute after an external caller has validated authorization.

    Tests may call this function only with invented temporary fixtures. The CLI
    calls it only after validate_authorization has succeeded.
    """
    contract = load_json(contract_path)
    validate_contract_shape(contract)
    package_root = contract_package_root(contract_path)
    documents = validate_bound_metadata(contract, package_root)
    required_dataset_ids = contract["ordering"]["dataset_order"]
    if set(source_roots) != set(required_dataset_ids):
        raise MaterializationError("source root set mismatch")
    output, staging = validate_output_paths(contract, source_roots, free_bytes)
    scans = preflight_sources(contract, documents, source_roots)
    exception_index = expected_exception_index(documents["cic_quality_exceptions"])
    lookups = ontology_lookups(documents["label_ontology"])
    budget = ByteBudget(int(contract["storage"]["hard_output_cap_bytes"]))
    created_staging = False
    total_completed_shards = 0
    try:
        staging.mkdir()
        created_staging = True
        dataset_results: Dict[str, Dict[str, Any]] = {}
        inventory_hashes: Dict[str, str] = {}
        for dataset_id in required_dataset_ids:
            inventory = documents[dataset_id]
            inventory_binding = contract["input_binding"]["inventories"][dataset_id]
            inventory_hashes[dataset_id] = inventory_binding["sha256"]
            root = source_roots[dataset_id]
            items = data_source_items(dataset_id, inventory)
            scan_by_path = {item.relative_path: item for item in scans[dataset_id]}
            ledger_entries: List[Dict[str, Any]] = []
            binary_counts: Counter = Counter()
            rows_materialized = 0
            rows_excluded = 0
            features_total_bytes = 0
            labels_total_bytes = 0
            for ordinal, source_item in enumerate(items, start=1):
                relative_path = source_item["relative_path"]
                source_scan = scan_by_path[relative_path]
                shard_id = "%04d-%s" % (ordinal, source_item["sha256"][:16])
                features_rel = "datasets/%s/features/%s.csv" % (dataset_id, shard_id)
                labels_rel = "datasets/%s/labels/%s.csv" % (dataset_id, shard_id)
                rendered = render_shard(
                    contract, dataset_id, source_item, source_scan.source_path,
                    exception_index if dataset_id == "ciciot2023" else {},
                    lookups, staging / features_rel, staging / labels_rel, budget)
                if rendered.source_sha256_replayed != source_item["sha256"]:
                    raise MaterializationError("source changed after preflight")
                metadata = source_metadata(dataset_id, relative_path)
                ledger = {
                    "schema_version": 1,
                    "dataset_id": dataset_id,
                    "shard_ordinal": ordinal,
                    "shard_id": shard_id,
                    "source_file": relative_path,
                    "source_file_sha256": source_item["sha256"],
                    "source_file_bytes": source_item["bytes"],
                    "source_header_sha256": source_item["header_sha256"],
                    "source_rows_inventoried": source_item["row_count"],
                    "source_rows_excluded": len(rendered.excluded_rows),
                    "source_rows_accepted": rendered.row_count,
                    "excluded_rows": rendered.excluded_rows,
                    "device_id": metadata["device_id"],
                    "capture_id": metadata["capture_id"],
                    "features_file": features_rel,
                    "features_sha256": rendered.features_sha256,
                    "features_bytes": rendered.features_bytes,
                    "labels_file": labels_rel,
                    "labels_sha256": rendered.labels_sha256,
                    "labels_bytes": rendered.labels_bytes,
                }
                ledger_entries.append(ledger)
                binary_counts.update(rendered.binary_counts)
                rows_materialized += rendered.row_count
                rows_excluded += len(rendered.excluded_rows)
                features_total_bytes += rendered.features_bytes
                labels_total_bytes += rendered.labels_bytes
                total_completed_shards += 1
                if free_bytes(output.parent) < int(contract["storage"]["scratch_reserve_bytes"]):
                    raise MaterializationError("free space fell below scratch reserve")
                if fault_after_shards is not None and \
                        total_completed_shards >= fault_after_shards:
                    raise MaterializationError("synthetic injected failure")

            if replay:
                with tempfile.TemporaryDirectory(prefix=".replay-", dir=str(staging)) as temp_dir:
                    replay_root = Path(temp_dir)
                    for ordinal, source_item in enumerate(items, start=1):
                        shard_id = "%04d-%s" % (ordinal, source_item["sha256"][:16])
                        replayed = render_shard(
                            contract, dataset_id, source_item,
                            scan_by_path[source_item["relative_path"]].source_path,
                            exception_index if dataset_id == "ciciot2023" else {},
                            lookups, replay_root / (shard_id + ".features.csv"),
                            replay_root / (shard_id + ".labels.csv"), None)
                        ledger = ledger_entries[ordinal - 1]
                        if replayed.features_sha256 != ledger["features_sha256"] or \
                                replayed.labels_sha256 != ledger["labels_sha256"] or \
                                replayed.source_sha256_replayed != source_item["sha256"]:
                            raise MaterializationError("per-shard deterministic replay mismatch")

            ledger_rel = "datasets/%s/lineage/shards.jsonl" % dataset_id
            ledger_path = staging / ledger_rel
            write_canonical_jsonl(ledger_path, ledger_entries, budget)
            dataset_feature_columns = feature_columns(
                contract, dataset_id, items[0]["columns"])
            manifest = {
                "schema_version": 1,
                "contract_id": contract["contract_id"],
                "dataset_id": dataset_id,
                "shard_count": len(items),
                "source_files_inventoried": inventory["file_count"],
                "source_rows_inventoried": inventory["total_rows"],
                "source_rows_excluded": rows_excluded,
                "rows_materialized": rows_materialized,
                "feature_count": len(dataset_feature_columns),
                "feature_columns": dataset_feature_columns,
                "label_columns": contract["label_sidecar"]["columns"],
                "features_total_bytes": features_total_bytes,
                "labels_total_bytes": labels_total_bytes,
                "ledger_file": ledger_rel,
                "ledger_sha256": sha256_path(ledger_path),
                "ledger_bytes": ledger_path.stat().st_size,
            }
            manifest_rel = "datasets/%s/manifest.json" % dataset_id
            write_canonical_json(staging / manifest_rel, manifest, budget)
            dataset_results[dataset_id] = dict(manifest)
            dataset_results[dataset_id]["binary_counts"] = dict(binary_counts)

        validate_expected_counts(contract, dataset_results)
        run_identity = {
            "schema_version": 1,
            "contract_id": contract["contract_id"],
            "freeze_id": "FEATURE-POLICY-20260905-V1-FROZEN",
            "feature_policy_sha256": contract["input_binding"]["feature_policy"]["sha256"],
            "label_ontology_sha256": contract["input_binding"]["label_ontology"]["sha256"],
            "request_zip_sha256": contract["baseline_request"]["request_zip_sha256"],
            "inventory_sha256": inventory_hashes,
        }
        write_canonical_json(staging / "run_identity.json", run_identity, budget)
        manifest_data = manifest_bytes(staging)
        budget.reserve(len(manifest_data))
        with (staging / "MANIFEST_SHA256.txt").open("xb") as handle:
            handle.write(manifest_data)
        verify_root_manifest(staging)
        # Revalidate every bound small input immediately before publication, not
        # just inventories. This closes a time-of-check/time-of-use window for
        # policy, ontology, quality-exception, census, and request metadata.
        validate_bound_metadata(contract, package_root)
        output.parent.stat()
        os.replace(str(staging), str(output))
        created_staging = False
        return {
            "contract_id": contract["contract_id"],
            "output_root": str(output),
            "output_bytes": budget.written,
            "dataset_results": dataset_results,
            "authorization_granted": True,
            "splitting_run": False,
            "training_run": False,
        }
    except Exception:
        safe_cleanup_created_staging(staging, output, created_staging)
        raise


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--show-contract", action="store_true")
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--authorization-record", type=Path)
    parser.add_argument("--request-zip", type=Path)
    parser.add_argument("--executor-evidence-zip", type=Path)
    parser.add_argument("--decisions", type=Path)
    parser.add_argument("--ton-root", type=Path)
    parser.add_argument("--cic-root", type=Path)
    parser.add_argument("--nb-root", type=Path)
    args = parser.parse_args(argv)
    try:
        contract = load_json(args.contract)
        validate_contract_shape(contract)
        if args.show_contract:
            print("contract_id = %s" % contract["contract_id"])
            print("authorization_granted = false")
            print("real_csvs_opened = false")
            return 0
        if not args.execute:
            raise MaterializationError("--execute is required; no source was accessed")
        guard_args = [args.authorization_record, args.request_zip,
                      args.executor_evidence_zip, args.decisions]
        if any(value is None for value in guard_args):
            raise MaterializationError(
                "complete authorization evidence is required before source access")
        validate_authorization(contract, args.authorization_record, args.request_zip,
                               args.executor_evidence_zip, args.decisions)
        roots = {"ton_iot": args.ton_root, "ciciot2023": args.cic_root,
                 "n_baiot": args.nb_root}
        if any(value is None for value in roots.values()):
            raise MaterializationError("all source roots are required after authorization")
        result = _execute_authorized(args.contract, roots)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except MaterializationError as exc:
        print("REFUSED: %s" % exc, file=sys.stderr)
        print("materialization_run = false", file=sys.stderr)
        print("splitting_run = false", file=sys.stderr)
        print("training_run = false", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
