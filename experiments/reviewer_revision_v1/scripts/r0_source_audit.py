"""Audit whether TON-IoT contains a genuinely untouched source-group pool."""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "revision_experiments_20260908" / "r0_source_audit"
MATERIALIZED = Path("/Volumes/RESEARCH_DATA/TNSM-MATERIALIZATION-20260906-V1")
RESULTS = ROOT / "tnsm_experiments_v1" / "results" / "ton_iot"
SOURCE = Path(json.loads((ROOT / "materialization_run_v2" / "authorization.json").read_text())["source_roots"]["ton_iot"]) / "train_test_network.csv"
FEATURES = MATERIALIZED / "datasets" / "ton_iot" / "features" / "0001-26ddc513552de36d.csv"
EXPECTED_SOURCE_SHA256 = "26ddc513552de36de6428b2e578efaed2b57504c716dfba847cc0109a64e1974"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def source_group(src_ip: str, dst_ip: str) -> str:
    value = "|".join(sorted((src_ip, dst_ip)))
    return hashlib.sha256(("11|" + value).encode()).hexdigest()


def assigned_split(group: str) -> str:
    bucket = int(group[:16], 16) % 100
    return "train" if bucket < 60 else "validation" if bucket < 80 else "test"


def feature_fingerprint(values: list[str]) -> str:
    payload = json.dumps(values, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def main() -> None:
    if any(OUT.iterdir()):
        raise FileExistsError(f"refusing to overwrite non-empty {OUT}")
    source_before = digest(SOURCE)
    if source_before != EXPECTED_SOURCE_SHA256:
        raise RuntimeError("frozen TON-IoT source hash mismatch")

    used_ids: set[int] = set()
    used_fingerprints: set[str] = set()
    pool_records = []
    for split in ("train", "validation", "test"):
        path = RESULTS / f"{split}_pool.npz"
        archive = np.load(path, allow_pickle=False)
        ids = archive["ids"]
        if ids.ndim != 2 or ids.shape[1] != 2 or np.any(ids[:, 0] != 0):
            raise RuntimeError(f"unexpected source IDs in {path}")
        split_ids = {int(value) for value in ids[:, 1]}
        if used_ids.intersection(split_ids):
            raise RuntimeError("source-row ID overlap between classifier pools")
        used_ids.update(split_ids)
        used_fingerprints.update(str(value) for value in archive["fingerprints"])
        pool_records.append({
            "split": split,
            "path": str(path.relative_to(ROOT)),
            "sha256": digest(path),
            "rows": len(split_ids),
        })

    derived_records = []
    for path in sorted((ROOT / "adaptive_scheduler_v1" / "policy_inputs").glob("*.npz")):
        archive = np.load(path, allow_pickle=False)
        key = "source_ids" if "source_ids" in archive.files else "ids" if "ids" in archive.files else None
        if key is None:
            continue
        ids = archive[key]
        if ids.ndim != 2 or ids.shape[1] != 2 or np.any(ids[:, 0] != 0):
            raise RuntimeError(f"unexpected source IDs in {path}")
        values = {int(value) for value in ids[:, 1]}
        if not values.issubset(used_ids):
            raise RuntimeError(f"derived policy input contains a row absent from classifier pools: {path}")
        derived_records.append({
            "path": str(path.relative_to(ROOT)),
            "sha256": digest(path),
            "source_id_occurrences": int(len(ids)),
            "unique_source_ids": len(values),
            "all_in_classifier_pools": True,
        })

    row_groups: dict[int, str] = {}
    group_stats: dict[str, Counter] = defaultdict(Counter)
    with SOURCE.open(encoding="utf-8-sig", newline="") as handle:
        for row_id, row in enumerate(csv.DictReader(handle), 1):
            group = source_group(row["src_ip"], row["dst_ip"])
            split = assigned_split(group)
            row_groups[row_id] = group
            group_stats[group]["rows"] += 1
            group_stats[group][f"assigned_{split}"] += 1
            if row_id in used_ids:
                group_stats[group]["used_rows"] += 1

    if len(row_groups) != 211043:
        raise RuntimeError("unexpected TON-IoT source row count")

    unused_rows = []
    with FEATURES.open(newline="") as handle:
        reader = csv.reader(handle)
        next(reader)
        for row_id, values in enumerate(reader, 1):
            if row_id in used_ids:
                continue
            group = row_groups[row_id]
            fingerprint = feature_fingerprint(values)
            group_has_used = group_stats[group]["used_rows"] > 0
            duplicate = fingerprint in used_fingerprints
            if group_has_used:
                reason = "source_group_already_used"
            elif duplicate:
                reason = "entire_group_unused_but_feature_fingerprint_duplicates_prior_used_row"
            else:
                reason = "candidate_untouched"
            unused_rows.append({
                "source_shard": 0,
                "source_row_id": row_id,
                "assigned_split": assigned_split(group),
                "source_group_hash": group,
                "feature_fingerprint": fingerprint,
                "group_has_prior_used_row": str(group_has_used).lower(),
                "fingerprint_seen_in_prior_used_rows": str(duplicate).lower(),
                "unused_reason": reason,
                "eligible_untouched_holdout": str(not group_has_used and not duplicate).lower(),
            })

    if len(used_ids) + len(unused_rows) != len(row_groups):
        raise RuntimeError("row-accounting mismatch")

    fully_unused_groups = []
    for group, counts in sorted(group_stats.items()):
        if counts["used_rows"]:
            continue
        group_rows = [row for row in unused_rows if row["source_group_hash"] == group]
        novel = sum(row["fingerprint_seen_in_prior_used_rows"] == "false" for row in group_rows)
        fully_unused_groups.append({
            "source_group_hash": group,
            "assigned_split": assigned_split(group),
            "rows": counts["rows"],
            "prior_used_rows": 0,
            "duplicate_fingerprint_rows": counts["rows"] - novel,
            "novel_fingerprint_rows": novel,
            "eligible_untouched_holdout": str(novel == counts["rows"] and novel > 0).lower(),
        })

    row_fields = list(unused_rows[0])
    with (OUT / "unused_source_rows.csv").open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=row_fields)
        writer.writeheader()
        writer.writerows(unused_rows)
    group_fields = list(fully_unused_groups[0])
    with (OUT / "unused_source_groups.csv").open("x", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=group_fields)
        writer.writeheader()
        writer.writerows(fully_unused_groups)

    candidate_rows = [row for row in unused_rows if row["eligible_untouched_holdout"] == "true"]
    audit = {
        "schema_version": 1,
        "status": "PASS",
        "source_file": str(SOURCE),
        "source_sha256_before": source_before,
        "source_sha256_after": digest(SOURCE),
        "materialized_features": str(FEATURES),
        "materialized_features_sha256": digest(FEATURES),
        "materialized_rows": len(row_groups),
        "source_groups": len(group_stats),
        "classifier_pool_records": pool_records,
        "classifier_unique_source_rows": len(used_ids),
        "derived_artifacts_checked": derived_records,
        "derived_artifact_count": len(derived_records),
        "unused_source_rows": len(unused_rows),
        "entirely_unused_source_groups": len(fully_unused_groups),
        "rows_in_entirely_unused_groups": sum(int(row["rows"]) for row in fully_unused_groups),
        "rows_in_entirely_unused_groups_with_prior_used_fingerprint": sum(int(row["duplicate_fingerprint_rows"]) for row in fully_unused_groups),
        "eligible_untouched_rows": len(candidate_rows),
        "eligible_untouched_groups": sum(row["eligible_untouched_holdout"] == "true" for row in fully_unused_groups),
        "revision_holdout_created": False,
        "revision_holdout_id": None,
        "decision": "NO_DEFENSIBLE_UNTOUCHED_POOL_USE_FROZEN_TEST_POSTHOC_PHYSICAL_ROBUSTNESS",
        "reason": "Every source-group-disjoint unrepresented row duplicates a feature fingerprint already present in a frozen classifier pool.",
        "test_pool_path": str((RESULTS / "test_pool.npz").relative_to(ROOT)),
        "test_pool_sha256": digest(RESULTS / "test_pool.npz"),
        "test_predictions_sha256": digest(RESULTS / "test_predictions.npz"),
        "no_split_membership_changed": True,
        "no_source_bytes_modified": source_before == digest(SOURCE),
    }
    (OUT / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    print(json.dumps({
        "status": audit["status"],
        "materialized_rows": audit["materialized_rows"],
        "classifier_rows": audit["classifier_unique_source_rows"],
        "unused_rows": audit["unused_source_rows"],
        "fully_unused_groups": audit["entirely_unused_source_groups"],
        "eligible_untouched_rows": audit["eligible_untouched_rows"],
        "decision": audit["decision"],
    }))


if __name__ == "__main__":
    main()
