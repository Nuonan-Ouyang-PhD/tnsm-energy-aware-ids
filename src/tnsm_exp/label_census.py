"""Streaming label/type census for the TON-IoT train_test_network CSV.

Reads only the `label` and `type` columns, never materializes row copies,
and records raw observed values verbatim alongside proposed normalized
values. No silent lowercase/strip/rename: every normalization is recorded
as a proposal in the output manifest.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path
from typing import Any

from .dataset_registry import open_csv_text, require_clean_worktree
from .util import compact_utc_now, git_commit, sha256_file, utc_now, write_json

LABEL_COLUMN = "label"
TYPE_COLUMN = "type"
BENIGN_TYPE_VALUES = {"normal"}
KNOWN_BINARY_LABELS = {"0", "1"}


def _whitespace_profile(value: str) -> dict[str, bool]:
    """Describe whitespace/case properties of a raw value without altering it."""
    return {
        "has_leading_or_trailing_whitespace": value != value.strip(),
        "is_empty_after_strip": value.strip() == "",
        "lowercase_variant_differs": value != value.lower(),
        "stripped_variant_differs": value != value.strip(),
    }


def census_labels(
    repo_root: Path,
    dataset_id: str,
    input_path: Path,
    expected_sha256: str | None = None,
    expected_total_rows: int | None = None,
    output_path: Path | None = None,
) -> tuple[Path, dict[str, Any]]:
    """Stream the label/type columns of a single CSV and write a census manifest."""
    input_path = input_path.resolve()
    require_clean_worktree(repo_root)

    if not input_path.is_file():
        raise FileNotFoundError(input_path)

    source_sha256 = sha256_file(input_path)
    if expected_sha256 is not None and source_sha256 != expected_sha256:
        raise ValueError(
            f"Source CSV SHA-256 mismatch: expected {expected_sha256}, got {source_sha256}"
        )

    label_counts: Counter[str] = Counter()
    type_counts: Counter[str] = Counter()
    cross_counts: Counter[tuple[str, str]] = Counter()
    missing_counts: dict[str, int] = {
        "label_empty_string": 0,
        "type_empty_string": 0,
        "label_whitespace_only": 0,
        "type_whitespace_only": 0,
        "row_field_count_mismatch": 0,
    }
    anomalies: list[dict[str, Any]] = []
    total_rows = 0

    with open_csv_text(input_path) as handle:
        reader = csv.reader(handle)
        try:
            header = next(reader)
        except StopIteration as exc:
            raise ValueError(f"CSV has no header: {input_path}") from exc
        try:
            label_index = header.index(LABEL_COLUMN)
            type_index = header.index(TYPE_COLUMN)
        except ValueError as exc:
            raise ValueError(
                f"CSV header lacks required columns {LABEL_COLUMN!r}/{TYPE_COLUMN!r}: {input_path}"
            ) from exc
        column_count = len(header)

        for row in reader:
            if not row:
                continue
            total_rows += 1
            if len(row) != column_count:
                missing_counts["row_field_count_mismatch"] += 1
                continue
            raw_label = row[label_index]
            raw_type = row[type_index]
            label_counts[raw_label] += 1
            type_counts[raw_type] += 1
            cross_counts[(raw_label, raw_type)] += 1
            if raw_label == "":
                missing_counts["label_empty_string"] += 1
            elif raw_label.strip() == "":
                missing_counts["label_whitespace_only"] += 1
            if raw_type == "":
                missing_counts["type_empty_string"] += 1
            elif raw_type.strip() == "":
                missing_counts["type_whitespace_only"] += 1
            if raw_label not in KNOWN_BINARY_LABELS:
                anomalies.append(
                    {
                        "kind": "non_binary_label_value",
                        "raw_label": raw_label,
                        "raw_type": raw_type,
                        "row_number_1_based": total_rows,
                    }
                )
            is_label_zero = raw_label == "0"
            is_benign_type = raw_type.strip().lower() in BENIGN_TYPE_VALUES
            is_label_one = raw_label == "1"
            if (is_label_zero and not is_benign_type) or (
                is_label_one and is_benign_type and raw_type != ""
            ):
                anomalies.append(
                    {
                        "kind": "label_type_potential_contradiction",
                        "raw_label": raw_label,
                        "raw_type": raw_type,
                        "row_number_1_based": total_rows,
                    }
                )

    if expected_total_rows is not None and total_rows != expected_total_rows:
        raise ValueError(
            f"Row count mismatch: expected {expected_total_rows}, read {total_rows}"
        )

    # Normalization candidates: raw value -> proposed normalized value.
    # Only recorded as proposals; nothing is applied here.
    normalization_candidates: dict[str, dict[str, str]] = {
        "label": {},
        "type": {},
    }
    for raw in label_counts:
        proposed = raw.strip()
        if proposed != raw:
            normalization_candidates["label"][raw] = proposed
    for raw in type_counts:
        proposed = raw.strip().lower()
        if proposed != raw:
            normalization_candidates["type"][raw] = proposed

    label_value_profiles = {
        raw: _whitespace_profile(raw) for raw in sorted(label_counts)
    }
    type_value_profiles = {
        raw: _whitespace_profile(raw) for raw in sorted(type_counts)
    }

    result: dict[str, Any] = {
        "schema_version": 1,
        "kind": "label_census",
        "dataset_id": dataset_id,
        "source_csv": input_path.name,
        "source_csv_sha256": source_sha256,
        "source_commit": git_commit(repo_root),
        "created_at_utc": utc_now(),
        "paper_eligible": False,
        "columns_read": [LABEL_COLUMN, TYPE_COLUMN],
        "total_rows": total_rows,
        "label_counts": dict(sorted(label_counts.items())),
        "type_counts": dict(sorted(type_counts.items())),
        "label_type_cross_counts": {
            f"{label}||{type_value}": count
            for (label, type_value), count in sorted(cross_counts.items())
        },
        "missing_counts": missing_counts,
        "label_value_profiles": label_value_profiles,
        "type_value_profiles": type_value_profiles,
        "anomalies": anomalies,
        "normalization_candidates": normalization_candidates,
        "normalization_status": "proposed",
        "notes": [
            "Raw observed values are recorded verbatim; no lowercase/strip/rename was applied.",
            "All normalization mappings remain proposals until the label ontology freeze.",
        ],
    }

    if output_path is None:
        output_path = (
            repo_root
            / "artifacts"
            / "datasets"
            / "label_census"
            / f"{dataset_id}_{compact_utc_now()}.json"
        )
    if output_path.exists():
        raise FileExistsError(f"Refusing to overwrite census evidence: {output_path}")
    write_json(output_path, result)
    return output_path, result
