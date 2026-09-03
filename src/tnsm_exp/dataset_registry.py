from __future__ import annotations

import csv
import gzip
import hashlib
import os
from pathlib import Path
from typing import Any, Iterator, TextIO

from .util import compact_utc_now, git_commit, read_json, sha256_file, utc_now, worktree_is_dirty, write_json


IGNORED_MAC_FILES = {".DS_Store"}


class DirtyWorktreeError(RuntimeError):
    """Raised when evidence manifests would reference a commit that does
    not contain the protocol actually being followed."""


def require_clean_worktree(repo_root: Path) -> None:
    if worktree_is_dirty(repo_root):
        raise DirtyWorktreeError(
            "Git worktree is dirty; commit the protocol/code changes first so "
            "manifest source_commit references a commit that contains them."
        )


def dataset_catalog(repo_root: Path) -> dict[str, Any]:
    return read_json(repo_root / "config" / "datasets.json")["datasets"]


def validate_dataset_id(repo_root: Path, dataset_id: str) -> dict[str, Any]:
    catalog = dataset_catalog(repo_root)
    if dataset_id not in catalog:
        raise ValueError(f"Unknown dataset_id {dataset_id!r}; choose one of {sorted(catalog)}")
    return catalog[dataset_id]


def iter_files(input_path: Path) -> tuple[list[Path], list[str]]:
    input_path = input_path.resolve()
    if not input_path.exists():
        raise FileNotFoundError(input_path)
    if input_path.is_symlink():
        raise ValueError(f"Symlink input is not allowed: {input_path}")
    if input_path.is_file():
        return [input_path], []

    files: list[Path] = []
    ignored: list[str] = []
    for current, directories, filenames in os.walk(input_path, followlinks=False):
        current_path = Path(current)
        for directory in list(directories):
            path = current_path / directory
            if path.is_symlink():
                raise ValueError(f"Symlink directory is not allowed: {path}")
        for filename in filenames:
            path = current_path / filename
            relative = path.relative_to(input_path).as_posix()
            if filename in IGNORED_MAC_FILES or filename.startswith("._"):
                ignored.append(relative)
                continue
            if path.is_symlink():
                raise ValueError(f"Symlink file is not allowed: {path}")
            if path.is_file():
                files.append(path)
    return sorted(files, key=lambda item: item.relative_to(input_path).as_posix()), sorted(ignored)


def relative_name(path: Path, input_path: Path) -> str:
    return path.name if input_path.is_file() else path.relative_to(input_path).as_posix()


def register_acquisition(
    repo_root: Path,
    dataset_id: str,
    input_path: Path,
    output_path: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    input_path = input_path.resolve()
    require_clean_worktree(repo_root)
    metadata = validate_dataset_id(repo_root, dataset_id)
    files, ignored = iter_files(input_path)
    if not files:
        raise ValueError(f"No dataset files found under {input_path}")
    records = []
    for path in files:
        size = path.stat().st_size
        if size == 0:
            raise ValueError(f"Empty dataset file is not allowed: {path}")
        records.append(
            {
                "relative_path": relative_name(path, input_path),
                "bytes": size,
                "sha256": sha256_file(path),
            }
        )
    result = {
        "schema_version": 1,
        "kind": "official_dataset_acquisition",
        "dataset_id": dataset_id,
        "display_name": metadata["display_name"],
        "created_at_utc": utc_now(),
        "paper_eligible": False,
        "source_commit": git_commit(repo_root),
        "official_page": metadata["official_page"],
        "access_method": metadata["access_method"],
        "selected_scope": metadata["selected_scope"],
        "license_note": metadata["license_note"],
        "input_name": input_path.name,
        "file_count": len(records),
        "total_bytes": sum(record["bytes"] for record in records),
        "ignored_non_dataset_files": ignored,
        "files": records,
    }
    if "official_doi" in metadata:
        result["official_doi"] = metadata["official_doi"]
    if output_path is None:
        output_path = (
            repo_root
            / "artifacts"
            / "datasets"
            / "acquisitions"
            / f"{dataset_id}_{compact_utc_now()}.json"
        )
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite acquisition evidence: {output_path}")
    write_json(output_path, result)
    return output_path, result


def open_csv_text(path: Path) -> TextIO:
    if path.name.lower().endswith(".csv.gz"):
        return gzip.open(path, mode="rt", encoding="utf-8-sig", newline="")
    return path.open(mode="r", encoding="utf-8-sig", newline="")


def csv_paths(input_path: Path) -> Iterator[Path]:
    files, _ = iter_files(input_path)
    for path in files:
        lower = path.name.lower()
        if lower.endswith(".csv") or lower.endswith(".csv.gz"):
            yield path


def inventory_csv_tree(
    repo_root: Path,
    dataset_id: str,
    input_path: Path,
    output_path: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    input_path = input_path.resolve()
    require_clean_worktree(repo_root)
    metadata = validate_dataset_id(repo_root, dataset_id)
    paths = list(csv_paths(input_path))
    if not paths:
        raise ValueError(f"No CSV or CSV.GZ files found under {input_path}")
    records = []
    for path in paths:
        with open_csv_text(path) as handle:
            reader = csv.reader(handle)
            try:
                header = next(reader)
            except StopIteration as exc:
                raise ValueError(f"CSV has no header: {path}") from exc
            if not header or any(not name.strip() for name in header):
                raise ValueError(f"CSV has an empty column name: {path}")
            if len(set(header)) != len(header):
                raise ValueError(f"CSV has duplicate column names: {path}")
            row_count = 0
            malformed_rows = 0
            for row in reader:
                if not row:
                    continue
                row_count += 1
                if len(row) != len(header):
                    malformed_rows += 1
        records.append(
            {
                "relative_path": relative_name(path, input_path),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
                "row_count": row_count,
                "column_count": len(header),
                "columns": header,
                "header_sha256": hashlib.sha256("\x1f".join(header).encode()).hexdigest(),
                "malformed_rows": malformed_rows,
            }
        )
    result = {
        "schema_version": 1,
        "kind": "dataset_csv_inventory",
        "dataset_id": dataset_id,
        "display_name": metadata["display_name"],
        "created_at_utc": utc_now(),
        "paper_eligible": False,
        "source_commit": git_commit(repo_root),
        "label_source": metadata["label_source"],
        "input_name": input_path.name,
        "file_count": len(records),
        "total_rows": sum(record["row_count"] for record in records),
        "total_bytes": sum(record["bytes"] for record in records),
        "all_rows_well_formed": all(record["malformed_rows"] == 0 for record in records),
        "files": records,
    }
    if output_path is None:
        output_path = (
            repo_root
            / "artifacts"
            / "datasets"
            / "inventories"
            / f"{dataset_id}_{compact_utc_now()}.json"
        )
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite inventory evidence: {output_path}")
    write_json(output_path, result)
    return output_path, result

