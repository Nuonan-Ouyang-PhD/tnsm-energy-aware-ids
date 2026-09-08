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
import ctypes
import csv
import errno
import hashlib
import io
import json
import os
import shutil
import stat
import sys
import zipfile
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


def load_json_bytes(data: bytes, label: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=_no_duplicate_pairs)
    except (UnicodeError, json.JSONDecodeError, DuplicateKeyError) as exc:
        raise MaterializationError("cannot load JSON %s: %s" % (label, exc)) from exc


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


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_regular_nofollow(path: Path) -> bytes:
    """Read one regular file without following a final-component symlink."""
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(str(path), flags)
    except OSError as exc:
        raise MaterializationError("cannot securely open runtime file %s: %s" %
                                   (path, exc)) from exc
    try:
        observed = os.fstat(descriptor)
        if not stat.S_ISREG(observed.st_mode):
            raise MaterializationError("runtime path is not a regular file: %s" % path)
        chunks: List[bytes] = []
        while True:
            block = os.read(descriptor, 1024 * 1024)
            if not block:
                break
            chunks.append(block)
        return b"".join(chunks)
    finally:
        os.close(descriptor)


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


@dataclass(frozen=True)
class ApprovedRuntime:
    contract: Mapping[str, Any]
    contract_bytes: bytes
    package_root: Path
    contract_path: Path
    executor_path: Path
    evidence_zip_sha256: str
    local_file_hashes: Mapping[str, str]


@dataclass
class StagingLease:
    parent_path: Path
    parent_fd: int
    parent_device: int
    parent_inode: int
    staging_path: Path
    staging_device: int
    staging_inode: int

    def close(self) -> None:
        if self.parent_fd >= 0:
            os.close(self.parent_fd)
            self.parent_fd = -1


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


class DigestBinarySink:
    """Count and hash bytes, optionally forwarding them to a real file."""

    def __init__(self, handle: Optional[Any]) -> None:
        self.handle = handle
        self.digest = hashlib.sha256()
        self.bytes_written = 0

    def write(self, data: bytes) -> int:
        self.digest.update(data)
        self.bytes_written += len(data)
        if self.handle is not None:
            self.handle.write(data)
        return len(data)

    def hexdigest(self) -> str:
        return self.digest.hexdigest()


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
    absolute = Path(os.path.abspath(str(contract_path)))
    if absolute.parent.name != "contract":
        raise MaterializationError("contract must be inside a contract directory")
    return absolute.parents[1]


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
            "one physical line is one CSV record; normal records are LF-terminated" or \
            not source_csv["quoted_multiline_fields"].startswith("forbidden") or \
            source_csv["header_terminal_newline"] != "required without exception" or \
            not source_csv["only_terminal_newline_exception"].startswith(
                "exactly the three frozen CIC malformed final physical lines"):
        raise MaterializationError("source CSV physical-record contract changed")
    runtime = contract["runtime_evidence_binding"]
    if runtime["contract_local_path"] not in runtime["required_local_files"] or \
            runtime["executor_local_path"] not in runtime["required_local_files"] or \
            runtime["local_dependencies"] != \
            "none; executor imports only the Python standard library":
        raise MaterializationError("runtime evidence binding changed")


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


def _manifest_entries(data: bytes) -> Dict[str, str]:
    if not data or not data.endswith(b"\n"):
        raise MaterializationError("evidence MANIFEST must be nonempty and LF-terminated")
    result: Dict[str, str] = {}
    for raw_line in data.splitlines(keepends=True):
        if not raw_line.endswith(b"\n") or raw_line.endswith(b"\r\n"):
            raise MaterializationError("evidence MANIFEST has non-LF line ending")
        body = raw_line[:-1]
        digest, separator, encoded_path = body.partition(b"  ")
        try:
            relative = encoded_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise MaterializationError("evidence MANIFEST path is not UTF-8") from exc
        pure = PurePosixPath(relative)
        if len(digest) != 64 or any(byte not in b"0123456789abcdef" for byte in digest) or \
                separator != b"  " or not relative or pure.is_absolute() or \
                ".." in pure.parts or "\\" in relative or relative == "MANIFEST_SHA256.txt":
            raise MaterializationError("invalid evidence MANIFEST entry: %r" % relative)
        if relative in result:
            raise MaterializationError("duplicate evidence MANIFEST path: %s" % relative)
        result[relative] = digest.decode("ascii")
    if list(result) != utf8_sort(result):
        raise MaterializationError("evidence MANIFEST paths are not UTF-8 bytewise sorted")
    return result


def _runtime_local_files(contract: Mapping[str, Any]) -> Set[str]:
    files = {
        contract["runtime_evidence_binding"]["contract_local_path"],
        contract["runtime_evidence_binding"]["executor_local_path"],
        contract["input_binding"]["feature_policy"]["file"],
        contract["input_binding"]["label_ontology"]["file"],
        contract["input_binding"]["ton_label_census"]["file"],
        contract["input_binding"]["cic_quality_exceptions"]["file"],
        contract["baseline_request"]["request_json"],
    }
    files.update(binding["file"] for binding in
                 contract["input_binding"]["inventories"].values())
    return files


def validate_runtime_archive(initial_contract: Mapping[str, Any],
                             contract_path: Path, evidence_bytes: bytes,
                             evidence_hash: str,
                             authorization: Mapping[str, Any]) -> ApprovedRuntime:
    """Bind the running contract, code, and inputs to the approved ZIP bytes."""
    binding = initial_contract["runtime_evidence_binding"]
    archive_root = binding["archive_root"]
    if authorization.get("evidence_archive_root") != archive_root:
        raise MaterializationError("authorization evidence archive-root mismatch")
    try:
        archive = zipfile.ZipFile(io.BytesIO(evidence_bytes))
    except (OSError, zipfile.BadZipFile) as exc:
        raise MaterializationError("approved executor evidence is not a valid ZIP") from exc
    with archive:
        infos = archive.infolist()
        names = [item.filename for item in infos]
        if len(names) != len(set(names)):
            raise MaterializationError("approved executor evidence ZIP has duplicate members")
        total_uncompressed = 0
        regular_relative: Set[str] = set()
        by_name: Dict[str, zipfile.ZipInfo] = {}
        prefix = archive_root + "/"
        for item in infos:
            name = item.filename
            pure = PurePosixPath(name)
            if pure.is_absolute() or ".." in pure.parts or "\\" in name or \
                    not name.startswith(prefix):
                raise MaterializationError("unsafe or unexpected evidence ZIP member: %s" % name)
            if item.flag_bits & 0x1:
                raise MaterializationError("encrypted evidence ZIP member: %s" % name)
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode):
                raise MaterializationError("symlink evidence ZIP member: %s" % name)
            if not item.is_dir() and mode and not stat.S_ISREG(mode):
                raise MaterializationError("non-regular evidence ZIP member: %s" % name)
            if item.file_size > int(binding["maximum_member_uncompressed_bytes"]):
                raise MaterializationError("oversized evidence ZIP member: %s" % name)
            total_uncompressed += item.file_size
            if total_uncompressed > int(binding["maximum_archive_uncompressed_bytes"]):
                raise MaterializationError("evidence ZIP uncompressed size limit exceeded")
            by_name[name] = item
            if not item.is_dir():
                regular_relative.add(name[len(prefix):])

        manifest_relative = binding["manifest"]
        manifest_name = prefix + manifest_relative
        if manifest_name not in by_name:
            raise MaterializationError("approved evidence MANIFEST missing")
        try:
            manifest_bytes_value = archive.read(manifest_name)
        except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
            raise MaterializationError("cannot read approved evidence MANIFEST") from exc
        manifest_hash = sha256_bytes(manifest_bytes_value)
        if authorization.get("evidence_manifest_sha256") != manifest_hash:
            raise MaterializationError("authorization evidence MANIFEST hash mismatch")
        entries = _manifest_entries(manifest_bytes_value)
        if set(entries) != regular_relative - {manifest_relative}:
            raise MaterializationError("evidence MANIFEST coverage mismatch")

        archive_data: Dict[str, bytes] = {}
        for relative, expected_hash in entries.items():
            try:
                data = archive.read(prefix + relative)
            except (OSError, RuntimeError, zipfile.BadZipFile) as exc:
                raise MaterializationError(
                    "cannot read or CRC-check evidence member: %s" % relative) from exc
            if sha256_bytes(data) != expected_hash:
                raise MaterializationError("evidence MANIFEST hash mismatch: %s" % relative)
            archive_data[relative] = data

    contract_relative = binding["contract_local_path"]
    if contract_relative not in archive_data:
        raise MaterializationError("approved contract member missing")
    approved_contract_bytes = archive_data[contract_relative]
    approved_contract = load_json_bytes(approved_contract_bytes, "approved contract member")
    validate_contract_shape(approved_contract)
    if approved_contract != initial_contract:
        raise MaterializationError("local parsed contract differs from approved contract")

    approved_binding = approved_contract["runtime_evidence_binding"]
    required = set(approved_binding["required_local_files"])
    if required != _runtime_local_files(approved_contract):
        raise MaterializationError("runtime file list is incomplete or has extras")
    package_root = contract_package_root(contract_path)
    expected_contract_path = package_root / contract_relative
    actual_contract_path = Path(os.path.abspath(str(contract_path)))
    if actual_contract_path != expected_contract_path:
        raise MaterializationError("actual --contract path does not match runtime binding")
    executor_relative = approved_binding["executor_local_path"]
    expected_executor_path = package_root / executor_relative
    actual_executor_path = Path(os.path.abspath(__file__))
    if actual_executor_path != expected_executor_path:
        raise MaterializationError("actual executor path does not match runtime binding")

    local_hashes: Dict[str, str] = {}
    for relative in utf8_sort(required):
        if relative not in archive_data:
            raise MaterializationError("required runtime member missing: %s" % relative)
        local_data = read_regular_nofollow(package_root / PurePosixPath(relative))
        if local_data != archive_data[relative]:
            raise MaterializationError(
                "local runtime file differs from approved evidence: %s" % relative)
        local_hashes[relative] = sha256_bytes(local_data)

    contract_hash = local_hashes[contract_relative]
    executor_hash = local_hashes[executor_relative]
    if authorization.get("contract_sha256") != contract_hash:
        raise MaterializationError("authorization contract SHA-256 mismatch")
    if authorization.get("executor_sha256") != executor_hash:
        raise MaterializationError("authorization executor SHA-256 mismatch")
    return ApprovedRuntime(
        contract=approved_contract, contract_bytes=approved_contract_bytes,
        package_root=package_root, contract_path=actual_contract_path,
        executor_path=actual_executor_path, evidence_zip_sha256=evidence_hash,
        local_file_hashes=local_hashes)


def validate_runtime_files_unchanged(runtime: ApprovedRuntime) -> None:
    for relative, expected_hash in runtime.local_file_hashes.items():
        observed = sha256_bytes(read_regular_nofollow(
            runtime.package_root / PurePosixPath(relative)))
        if observed != expected_hash:
            raise MaterializationError("runtime file changed after authorization: %s" % relative)


def validate_authorization(contract: Mapping[str, Any], contract_path: Path,
                           authorization_path: Path, request_zip: Path,
                           evidence_zip: Path, decisions_path: Path) -> ApprovedRuntime:
    """Validate all external authorization evidence before source access."""
    authorization = load_json_bytes(
        read_regular_nofollow(authorization_path), "authorization record")
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
    request_bytes = read_regular_nofollow(request_zip)
    if sha256_bytes(request_bytes) != contract["baseline_request"]["request_zip_sha256"]:
        raise MaterializationError("accepted request ZIP is missing or changed")
    evidence_bytes = read_regular_nofollow(evidence_zip)
    evidence_hash = sha256_bytes(evidence_bytes)
    if authorization.get("executor_evidence_zip_sha256") != evidence_hash:
        raise MaterializationError("executor evidence ZIP binding mismatch")
    runtime = validate_runtime_archive(contract, contract_path, evidence_bytes,
                                       evidence_hash, authorization)
    try:
        decisions = read_regular_nofollow(decisions_path).decode("utf-8")
    except UnicodeError as exc:
        raise MaterializationError("cannot read DECISIONS.md: %s" % exc) from exc
    required_text = [
        authorization.get("authorization_id"),
        contract["contract_id"],
        contract["baseline_request"]["request_zip_sha256"],
        evidence_hash,
        authorization.get("evidence_archive_root"),
        authorization.get("evidence_manifest_sha256"),
        authorization.get("contract_sha256"),
        authorization.get("executor_sha256"),
        contract["output_binding"]["root"],
    ]
    if any(not isinstance(item, str) or not item or item not in decisions
           for item in required_text):
        raise MaterializationError("DECISIONS.md does not contain every authorization binding")
    return runtime


def validate_output_paths(contract: Mapping[str, Any], source_roots: Mapping[str, Path],
                          free_bytes: Callable[[Path], int]) -> Tuple[Path, Path]:
    output = Path(os.path.abspath(contract["output_binding"]["root"]))
    staging = Path(os.path.abspath(contract["output_binding"]["staging_root"]))
    if output == staging or output.parent != staging.parent or \
            staging.name != ".%s.staging" % output.name:
        raise MaterializationError("unsafe output/staging relationship")
    if output == Path(output.anchor) or staging == Path(staging.anchor):
        raise MaterializationError("filesystem root cannot be an output or staging path")
    if os.path.lexists(output):
        raise MaterializationError("final output already exists; overwrite forbidden")
    if os.path.lexists(staging):
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
    if exception_manifest.get("exception_count") != 3 or \
            len(exception_manifest.get("exceptions", [])) != 3:
        raise MaterializationError("exactly three CIC quality exceptions are required")
    result: Dict[Tuple[str, int], Dict[str, Any]] = {}
    for item in exception_manifest["exceptions"]:
        if item.get("ends_with_newline") is not False:
            raise MaterializationError(
                "every frozen CIC quality exception must be a non-LF final line")
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
        item["ends_with_newline"] is False,
        raw.endswith(b"\n") is False,
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
            if not header_raw.endswith(b"\n"):
                raise MaterializationError(
                    "source header is not LF-terminated: %s" % relative_path)
            if hash_raw_line(header_raw) != source_item["header_sha256"]:
                raise MaterializationError("source header SHA-256 mismatch: %s" %
                                           relative_path)
            header = parse_physical_csv_line(header_raw, path, 1)
            if header != source_item["columns"]:
                raise MaterializationError("source header mismatch: %s" % relative_path)
            for physical_line, raw in enumerate(handle, start=2):
                digest.update(raw)
                row_count += 1
                row = parse_physical_csv_line(raw, path, physical_line)
                matched: Optional[Dict[str, Any]] = None
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
                if not raw.endswith(b"\n") and matched is None:
                    raise MaterializationError(
                        "unregistered non-LF terminal record: %s line %d" %
                        (relative_path, physical_line))
    except OSError as exc:
        raise MaterializationError("cannot scan source %s: %s" % (path, exc)) from exc
    if row_count != source_item["row_count"]:
        raise MaterializationError("source row count mismatch: %s" % relative_path)
    if len(excluded) != source_item["malformed_rows"]:
        raise MaterializationError("source malformed-row count mismatch: %s" %
                                   relative_path)
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


def all_inventory_items(inventory: Mapping[str, Any]) -> List[Mapping[str, Any]]:
    return sorted(inventory["files"],
                  key=lambda item: item["relative_path"].encode("utf-8"))


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
        all_items = all_inventory_items(inventory)
        if inventory["file_count"] != len(all_items) or \
                inventory["total_rows"] != sum(item["row_count"] for item in all_items) or \
                inventory["total_bytes"] != sum(item["bytes"] for item in all_items):
            raise MaterializationError("%s inventory summary mismatch" % dataset_id)
        validate_source_set(dataset_id, root, inventory)
        scans: List[SourceScan] = []
        for item in all_items:
            index = exception_index if dataset_id == "ciciot2023" else {}
            scan = scan_source_file(root, item, index)
            scans.append(scan)
            for excluded in scan.excluded_rows:
                seen_exceptions.add((scan.relative_path, excluded["physical_line"]))
        if dataset_id == "n_baiot":
            structure_items = [item for item in all_items
                               if item["relative_path"] == "demonstrate_structure.csv"]
            structure_scans = [item for item in scans
                               if item.relative_path == "demonstrate_structure.csv"]
            if len(structure_items) != 1 or len(structure_scans) != 1 or \
                    structure_items[0]["row_count"] != 0 or \
                    structure_items[0]["malformed_rows"] != 0 or \
                    structure_scans[0].row_count != 0 or \
                    structure_scans[0].excluded_rows:
                raise MaterializationError(
                    "N-BaIoT demonstrate_structure.csv must be the one frozen zero-row file")
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


def _serialize_shard(contract: Mapping[str, Any], dataset_id: str,
                     source_item: Mapping[str, Any], source_path: Path,
                     exception_index: Mapping[Tuple[str, int], Mapping[str, Any]],
                     lookups: Mapping[str, Any], feature_sink: DigestBinarySink,
                     label_sink: DigestBinarySink,
                     budget: Optional[ByteBudget]) -> RenderedShard:
    columns = source_item["columns"]
    output_columns = feature_columns(contract, dataset_id, columns)
    header_index = {name: index for index, name in enumerate(columns)}
    selected_indexes = [header_index[name] for name in output_columns]
    metadata = source_metadata(dataset_id, source_item["relative_path"])
    binary_counts: Counter = Counter()
    excluded: List[Dict[str, Any]] = []
    source_digest = hashlib.sha256()
    accepted = 0
    try:
        with source_path.open("rb") as source:
            feature_writer = csv.writer(
                BudgetTextSink(feature_sink, budget), delimiter=",", quotechar='"',
                quoting=csv.QUOTE_MINIMAL, doublequote=True, lineterminator="\n")
            label_writer = csv.writer(
                BudgetTextSink(label_sink, budget), delimiter=",", quotechar='"',
                quoting=csv.QUOTE_MINIMAL, doublequote=True, lineterminator="\n")
            feature_writer.writerow(output_columns)
            label_writer.writerow(contract["label_sidecar"]["columns"])
            header_raw = source.readline()
            source_digest.update(header_raw)
            if not header_raw.endswith(b"\n") or \
                    hash_raw_line(header_raw) != source_item["header_sha256"]:
                raise MaterializationError("header newline/hash changed during render")
            if parse_physical_csv_line(header_raw, source_path, 1) != columns:
                raise MaterializationError("header changed during render")
            for physical_line, raw in enumerate(source, start=2):
                source_digest.update(raw)
                row = parse_physical_csv_line(raw, source_path, physical_line)
                matched: Optional[Dict[str, Any]] = None
                if len(row) != source_item["column_count"]:
                    matched = match_exception(source_item["relative_path"],
                                              physical_line, raw, len(row),
                                              source_item, exception_index)
                    if matched is None:
                        raise MaterializationError("unregistered malformed render row")
                    excluded.append(matched)
                elif (source_item["relative_path"], physical_line) in exception_index:
                    raise MaterializationError("registered exception rendered as valid")
                if not raw.endswith(b"\n") and matched is None:
                    raise MaterializationError("unregistered non-LF terminal render row")
                if matched is not None:
                    continue
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
        features_sha256=feature_sink.hexdigest(),
        features_bytes=feature_sink.bytes_written,
        labels_sha256=label_sink.hexdigest(),
        labels_bytes=label_sink.bytes_written,
        source_sha256_replayed=source_digest.hexdigest())


def render_shard(contract: Mapping[str, Any], dataset_id: str,
                 source_item: Mapping[str, Any], source_path: Path,
                 exception_index: Mapping[Tuple[str, int], Mapping[str, Any]],
                 lookups: Mapping[str, Any], features_path: Path,
                 labels_path: Path, budget: Optional[ByteBudget]) -> RenderedShard:
    features_path.parent.mkdir(parents=True, exist_ok=True)
    labels_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with features_path.open("xb") as feature_handle, \
                labels_path.open("xb") as label_handle:
            return _serialize_shard(
                contract, dataset_id, source_item, source_path, exception_index,
                lookups, DigestBinarySink(feature_handle),
                DigestBinarySink(label_handle), budget)
    except OSError as exc:
        raise MaterializationError("cannot write shard for %s: %s" %
                                   (source_path, exc)) from exc


def replay_shard(contract: Mapping[str, Any], dataset_id: str,
                 source_item: Mapping[str, Any], source_path: Path,
                 exception_index: Mapping[Tuple[str, int], Mapping[str, Any]],
                 lookups: Mapping[str, Any]) -> RenderedShard:
    """Replay serialization into hash-only sinks; no replay bytes touch disk."""
    return _serialize_shard(
        contract, dataset_id, source_item, source_path, exception_index, lookups,
        DigestBinarySink(None), DigestBinarySink(None), None)


def _identity_tuple(value: os.stat_result) -> Tuple[int, int]:
    return value.st_dev, value.st_ino


def create_staging_lease(output: Path, staging: Path) -> StagingLease:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | \
        getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
    try:
        parent_fd = os.open(str(output.parent), flags)
    except OSError as exc:
        raise MaterializationError("cannot securely open output parent: %s" % exc) from exc
    try:
        parent_stat = os.fstat(parent_fd)
        os.mkdir(staging.name, mode=0o700, dir_fd=parent_fd)
        staging_stat = os.stat(staging.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(staging_stat.st_mode):
            raise MaterializationError("new staging entry is not a directory")
        return StagingLease(
            parent_path=output.parent, parent_fd=parent_fd,
            parent_device=parent_stat.st_dev, parent_inode=parent_stat.st_ino,
            staging_path=staging, staging_device=staging_stat.st_dev,
            staging_inode=staging_stat.st_ino)
    except Exception:
        os.close(parent_fd)
        raise


def validate_staging_lease(lease: StagingLease) -> None:
    try:
        parent_by_path = os.stat(lease.parent_path, follow_symlinks=False)
        parent_by_fd = os.fstat(lease.parent_fd)
        staging_by_name = os.stat(
            lease.staging_path.name, dir_fd=lease.parent_fd, follow_symlinks=False)
    except OSError as exc:
        raise MaterializationError(
            "staging ownership cannot be verified; preserved without cleanup: %s" % exc) from exc
    expected_parent = (lease.parent_device, lease.parent_inode)
    if _identity_tuple(parent_by_path) != expected_parent or \
            _identity_tuple(parent_by_fd) != expected_parent:
        raise MaterializationError(
            "output parent identity changed; staging preserved without cleanup")
    observed_staging = _identity_tuple(staging_by_name)
    expected_staging = (lease.staging_device, lease.staging_inode)
    if observed_staging != expected_staging or not stat.S_ISDIR(staging_by_name.st_mode):
        raise MaterializationError(
            "foreign staging identity preserved: expected=%r observed=%r" %
            (expected_staging, observed_staging))


def describe_preserved_staging(lease: Optional[StagingLease]) -> str:
    if lease is None:
        return "no staging directory was created"
    try:
        validate_staging_lease(lease)
        return ("owned staging preserved for audit: path=%s device=%d inode=%d" %
                (lease.staging_path, lease.staging_device, lease.staging_inode))
    except MaterializationError as exc:
        return str(exc)


def atomic_publish_noreplace(lease: StagingLease, output: Path) -> None:
    """Atomically publish without replacing any existing destination entry."""
    validate_staging_lease(lease)
    if sys.platform != "darwin":
        raise MaterializationError(
            "atomic no-clobber publish unsupported on this platform; no fallback")
    libc = ctypes.CDLL(None, use_errno=True)
    try:
        renameatx = libc.renameatx_np
    except AttributeError as exc:
        raise MaterializationError(
            "renameatx_np unavailable; atomic no-clobber publish refused") from exc
    renameatx.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int,
                          ctypes.c_char_p, ctypes.c_uint]
    renameatx.restype = ctypes.c_int
    result = renameatx(
        lease.parent_fd, os.fsencode(lease.staging_path.name),
        lease.parent_fd, os.fsencode(output.name), 0x00000004)
    if result != 0:
        observed_errno = ctypes.get_errno()
        if observed_errno in (errno.EEXIST, errno.ENOTEMPTY):
            raise MaterializationError(
                "final output appeared before publication; no-clobber preserved it")
        raise MaterializationError(
            "atomic no-clobber publish failed closed: %s" %
            os.strerror(observed_errno))
    published = os.stat(output.name, dir_fd=lease.parent_fd, follow_symlinks=False)
    if _identity_tuple(published) != (lease.staging_device, lease.staging_inode):
        raise MaterializationError("published directory identity mismatch")


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


def require_scratch_reserve(contract: Mapping[str, Any], output: Path,
                            free_bytes: Callable[[Path], int], phase: str) -> None:
    observed = free_bytes(output.parent)
    required = int(contract["storage"]["scratch_reserve_bytes"])
    if observed < required:
        raise MaterializationError(
            "free space fell below scratch reserve during %s: observed=%d required=%d" %
            (phase, observed, required))


def _execute_authorized(contract_path: Path, source_roots: Mapping[str, Path],
                        free_bytes: Callable[[Path], int] = default_free_bytes,
                        fault_after_shards: Optional[int] = None,
                        replay: bool = True,
                        approved_runtime: Optional[ApprovedRuntime] = None) -> Dict[str, Any]:
    """Execute after an external caller has validated authorization.

    Tests may call this function only with invented temporary fixtures. The CLI
    calls it only after validate_authorization has succeeded.
    """
    contract = approved_runtime.contract if approved_runtime is not None \
        else load_json(contract_path)
    validate_contract_shape(contract)
    package_root = approved_runtime.package_root if approved_runtime is not None \
        else contract_package_root(contract_path)
    if approved_runtime is not None:
        validate_runtime_files_unchanged(approved_runtime)
    documents = validate_bound_metadata(contract, package_root)
    required_dataset_ids = contract["ordering"]["dataset_order"]
    if set(source_roots) != set(required_dataset_ids):
        raise MaterializationError("source root set mismatch")
    output, staging = validate_output_paths(contract, source_roots, free_bytes)
    scans = preflight_sources(contract, documents, source_roots)
    exception_index = expected_exception_index(documents["cic_quality_exceptions"])
    lookups = ontology_lookups(documents["label_ontology"])
    budget = ByteBudget(int(contract["storage"]["hard_output_cap_bytes"]))
    lease: Optional[StagingLease] = None
    total_completed_shards = 0
    try:
        lease = create_staging_lease(output, staging)
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
            rendered_shards: List[RenderedShard] = []
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
                rendered_shards.append(rendered)
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
                require_scratch_reserve(
                    contract, output, free_bytes, "completed feature/label shard pair")
                if fault_after_shards is not None and \
                        total_completed_shards >= fault_after_shards:
                    raise MaterializationError("synthetic injected failure")

            if replay:
                for ordinal, source_item in enumerate(items, start=1):
                    replayed = replay_shard(
                        contract, dataset_id, source_item,
                        scan_by_path[source_item["relative_path"]].source_path,
                        exception_index if dataset_id == "ciciot2023" else {},
                        lookups)
                    ledger = ledger_entries[ordinal - 1]
                    first_pass = rendered_shards[ordinal - 1]
                    if replayed.features_sha256 != ledger["features_sha256"] or \
                            replayed.features_bytes != ledger["features_bytes"] or \
                            replayed.labels_sha256 != ledger["labels_sha256"] or \
                            replayed.labels_bytes != ledger["labels_bytes"] or \
                            replayed.source_sha256_replayed != source_item["sha256"] or \
                            replayed.row_count != ledger["source_rows_accepted"] or \
                            replayed.excluded_rows != ledger["excluded_rows"] or \
                            replayed.binary_counts != first_pass.binary_counts:
                        raise MaterializationError("per-shard deterministic replay mismatch")
                    require_scratch_reserve(
                        contract, output, free_bytes, "hash-only replay shard")

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
            require_scratch_reserve(
                contract, output, free_bytes, "dataset ledger and manifest")
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
        require_scratch_reserve(contract, output, free_bytes, "run identity")
        manifest_data = manifest_bytes(staging)
        budget.reserve(len(manifest_data))
        with (staging / "MANIFEST_SHA256.txt").open("xb") as handle:
            handle.write(manifest_data)
        verify_root_manifest(staging)
        require_scratch_reserve(contract, output, free_bytes, "root manifest")
        # Revalidate every bound small input immediately before publication, not
        # just inventories. This closes a time-of-check/time-of-use window for
        # policy, ontology, quality-exception, census, and request metadata.
        validate_bound_metadata(contract, package_root)
        if approved_runtime is not None:
            validate_runtime_files_unchanged(approved_runtime)
        require_scratch_reserve(contract, output, free_bytes, "pre-publication")
        if lease is None:
            raise MaterializationError("staging lease missing before publication")
        atomic_publish_noreplace(lease, output)
        return {
            "contract_id": contract["contract_id"],
            "output_root": str(output),
            "output_bytes": budget.written,
            "dataset_results": dataset_results,
            "authorization_granted": True,
            "splitting_run": False,
            "training_run": False,
        }
    except Exception as exc:
        retention = describe_preserved_staging(lease)
        raise MaterializationError("%s; %s" % (exc, retention)) from exc
    finally:
        if lease is not None:
            lease.close()


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
        approved_runtime = validate_authorization(
            contract, args.contract, args.authorization_record, args.request_zip,
            args.executor_evidence_zip, args.decisions)
        roots = {"ton_iot": args.ton_root, "ciciot2023": args.cic_root,
                 "n_baiot": args.nb_root}
        if any(value is None for value in roots.values()):
            raise MaterializationError("all source roots are required after authorization")
        result = _execute_authorized(
            args.contract, roots, approved_runtime=approved_runtime)
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
