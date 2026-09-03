from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

from .dataset_registry import (
    csv_paths,
    open_csv_text,
    relative_name,
    require_clean_worktree,
    validate_dataset_id,
)
from .util import compact_utc_now, git_commit, sha256_file, utc_now, write_json


class UnsupportedQuoteUsage(RuntimeError):
    """Raised when a malformed file contains quoted fields so per-line
    locating cannot be done without full CSV re-parsing."""


def _locate_malformed_physical_lines(path: Path, expected_columns: int) -> list[dict[str, Any]]:
    """Locate malformed physical lines in a quote-free CSV file.

    Returns one record per malformed physical line with byte-level evidence.
    """
    raw = path.read_bytes()
    if b'"' in raw:
        raise UnsupportedQuoteUsage(
            f"File contains double-quoted fields; per-line locating is not "
            f"unambiguous for: {path}"
        )
    lines = raw.splitlines(keepends=True)
    found: list[dict[str, Any]] = []
    for index, line in enumerate(lines, start=1):
        stripped = line.rstrip(b"\r\n")
        if stripped == b"":
            continue  # empty physical line: csv.reader yields [] and skips it
        observed = stripped.count(b",") + 1
        if observed != expected_columns:
            found.append(
                {
                    "physical_line": index,
                    "observed_column_count_line_scan": observed,
                    "raw_line_bytes": len(line),
                    "raw_line_sha256": hashlib.sha256(line).hexdigest(),
                    "ends_with_newline": line.endswith(b"\n"),
                    "is_last_line": index == len(lines),
                    "first_40_bytes_hex": line[:40].hex(),
                }
            )
    return found


def register_quality_exceptions(
    repo_root: Path,
    dataset_id: str,
    input_path: Path,
    output_path: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Scan a dataset tree and register every malformed CSV row with
    deterministic positions, byte lengths, and line hashes.

    Raw files are never modified. The registered positions are the basis for
    deterministic exclusion during preprocessing.
    """
    input_path = input_path.resolve()
    require_clean_worktree(repo_root)
    metadata = validate_dataset_id(repo_root, dataset_id)
    exceptions: list[dict[str, Any]] = []
    files_scanned = 0

    for path in csv_paths(input_path):
        files_scanned += 1
        with open_csv_text(path) as handle:
            reader = csv.reader(handle)
            header = next(reader)
            expected_columns = len(header)
            malformed_rows = 0
            logical_rows = 0
            for row in reader:
                if not row:
                    continue
                logical_rows += 1
                if len(row) != expected_columns:
                    malformed_rows += 1
        if malformed_rows == 0:
            continue
        located = _locate_malformed_physical_lines(path, expected_columns)
        if len(located) != malformed_rows:
            raise ValueError(
                f"Line-scan located {len(located)} malformed lines but the CSV "
                f"parser found {malformed_rows} malformed rows; the file may "
                f"contain quoted multi-line fields: {path}"
            )
        for record in located:
            record.update(
                {
                    "relative_path": relative_name(path, input_path),
                    "expected_column_count": expected_columns,
                    "logical_row_count_in_file": logical_rows,
                    "file_bytes": path.stat().st_size,
                    "file_sha256": sha256_file(path),
                }
            )
            exceptions.append(record)

    exceptions.sort(key=lambda item: item["relative_path"])
    result = {
        "schema_version": 1,
        "kind": "dataset_quality_exceptions",
        "dataset_id": dataset_id,
        "display_name": metadata["display_name"],
        "created_at_utc": utc_now(),
        "paper_eligible": False,
        "source_commit": git_commit(repo_root),
        "input_name": input_path.name,
        "files_scanned": files_scanned,
        "exception_count": len(exceptions),
        "policy": (
            "Malformed raw lines are kept unchanged in the official dataset "
            "files; they are excluded deterministically by their registered "
            "relative_path and physical_line during preprocessing."
        ),
        "exceptions": exceptions,
    }
    if output_path is None:
        output_path = (
            repo_root
            / "artifacts"
            / "datasets"
            / "quality_exceptions"
            / f"{dataset_id}_{compact_utc_now()}.json"
        )
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite quality-exception evidence: {output_path}")
    write_json(output_path, result)
    return output_path, result
