#!/usr/bin/env python3
"""Recompute accepted-cache-only derived summaries without running experiments.

This program reads immutable classification/replay artifacts, verifies every used
workspace copy against the accepted article ZIP and its root manifest, and then
derives two diagnostic tables.  It never imports or invokes the training,
materialization, or static-replay entry points.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import zipfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
from scipy.stats import t
from sklearn.metrics import (
    accuracy_score,
    average_precision_score,
    balanced_accuracy_score,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ARTICLE = ROOT / "TNSM_ARTICLE_DATA_20260907_V1.zip"
ARTICLE_ID = "TNSM_ARTICLE_DATA_20260907_V1"
ARTICLE_PREFIX = ARTICLE_ID + "/"
EXPECTED_ARTICLE_SHA256 = "c135da2db921dc442b4fbea7bd2596aaef8f1eda2f553945d400168d77375c74"
EXPECTED_ROOT_MANIFEST_SHA256 = "5492855ddd90ee4eebc52924318f7d0f9cc43a10009732aef0e8aef7570cc945"
KNOWN_ACCEPTED_ROOT_MANIFEST_OMISSIONS = {
    "raw/materialization/MANIFEST_SHA256.txt",
    "raw/materialization/materialization_run_v2/MANIFEST_SHA256.txt",
}
DATASETS = ("ton_iot", "ciciot2023", "n_baiot")
MODELS = ("TinyDT", "LightLR", "MedRF", "HeavyMLP")
SPLITS = ("train", "validation", "test")
THRESHOLD = 0.5
TRACE_SEEDS = 10
DF = TRACE_SEEDS - 1
T_CRITICAL = float(t.ppf(0.975, DF))
UNCERTAINTY_SCOPE = (
    "workload resampling only, conditional on one model seed and fixed split; "
    "not hardware or training uncertainty"
)

GENERATED = (
    "encoded_overlap_sensitivity.csv",
    "static_replay_aggregates_t95_recomputed.csv",
    "SOURCE_HASHES.csv",
    "VALIDATION.json",
)
CONTENT_FILES = set(GENERATED) | {"AUDIT.md", "recompute_derived_summary.py"}
MANIFEST_NAME = "MANIFEST_SHA256.txt"


def sha256_stream(stream: Any) -> str:
    digest = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b""):
        digest.update(block)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return sha256_stream(stream)


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def csv_bytes(rows: Iterable[dict[str, Any]], fields: list[str]) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def json_bytes(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def parse_root_manifest(raw: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line_number, line in enumerate(raw.decode("utf-8").splitlines(), 1):
        parts = line.split("  ", 1)
        if len(parts) != 2 or len(parts[0]) != 64:
            raise AssertionError(f"malformed root manifest line {line_number}")
        digest, relative = parts
        int(digest, 16)
        if relative in result:
            raise AssertionError(f"duplicate root manifest path: {relative}")
        result[relative] = digest
    return result


class SourceBinder:
    """Bind each derivation input to both the accepted ZIP and root manifest."""

    def __init__(self, archive: zipfile.ZipFile, manifest: dict[str, str]) -> None:
        self.archive = archive
        self.manifest = manifest
        self.rows: list[dict[str, Any]] = []
        self._seen: set[str] = set()

    def _append(
        self,
        *,
        source_kind: str,
        logical_path: str,
        article_member: str,
        workspace_relative_path: str,
        digest: str,
        byte_count: int,
        binding: str,
        use: str,
    ) -> None:
        key = f"{source_kind}:{logical_path}:{workspace_relative_path}"
        if key in self._seen:
            return
        self._seen.add(key)
        self.rows.append(
            {
                "source_kind": source_kind,
                "logical_path": logical_path,
                "article_member": article_member,
                "workspace_relative_path": workspace_relative_path,
                "sha256": digest,
                "bytes": byte_count,
                "binding": binding,
                "use": use,
            }
        )

    def add_archive_identity(self) -> None:
        digest = sha256_file(ARTICLE)
        assert digest == EXPECTED_ARTICLE_SHA256, "accepted article archive hash mismatch"
        self._append(
            source_kind="accepted_archive",
            logical_path=ARTICLE.name,
            article_member="",
            workspace_relative_path=ARTICLE.name,
            digest=digest,
            byte_count=ARTICLE.stat().st_size,
            binding="actual file equals task-authorized SHA-256",
            use="immutable accepted baseline",
        )

    def add_root_manifest(self, raw: bytes) -> None:
        digest = sha256_bytes(raw)
        assert digest == EXPECTED_ROOT_MANIFEST_SHA256, "root manifest hash mismatch"
        member = ARTICLE_PREFIX + MANIFEST_NAME
        self._append(
            source_kind="archive_root_manifest",
            logical_path=MANIFEST_NAME,
            article_member=member,
            workspace_relative_path="",
            digest=digest,
            byte_count=len(raw),
            binding="actual ZIP member equals independently recorded SHA-256",
            use="member coverage and per-input digest authority",
        )

    def archive_bytes(self, logical_path: str, use: str) -> bytes:
        expected = self.manifest[logical_path]
        member = ARTICLE_PREFIX + logical_path
        raw = self.archive.read(member)
        digest = sha256_bytes(raw)
        assert digest == expected, f"archive member hash mismatch: {logical_path}"
        self._append(
            source_kind="archive_member",
            logical_path=logical_path,
            article_member=member,
            workspace_relative_path="",
            digest=digest,
            byte_count=len(raw),
            binding="actual ZIP member equals accepted root-manifest SHA-256",
            use=use,
        )
        return raw

    def archive_bytes_not_listed_in_root_manifest(self, logical_path: str, use: str) -> bytes:
        """Record a known nested-manifest omission, still bound by the accepted ZIP hash."""
        assert logical_path not in self.manifest
        assert logical_path in KNOWN_ACCEPTED_ROOT_MANIFEST_OMISSIONS
        member = ARTICLE_PREFIX + logical_path
        raw = self.archive.read(member)
        digest = sha256_bytes(raw)
        self._append(
            source_kind="archive_member_bound_by_accepted_archive",
            logical_path=logical_path,
            article_member=member,
            workspace_relative_path="",
            digest=digest,
            byte_count=len(raw),
            binding="actual member SHA-256 plus immutable accepted whole-archive SHA-256; omitted by old root manifest",
            use=use,
        )
        return raw

    def bind_workspace_copy(self, logical_path: str, workspace_relative: str, use: str) -> Path:
        expected = self.manifest[logical_path]
        member = ARTICLE_PREFIX + logical_path
        info = self.archive.getinfo(member)
        with self.archive.open(member) as stream:
            archive_digest = sha256_stream(stream)
        assert archive_digest == expected, f"archive member hash mismatch: {logical_path}"
        path = ROOT / workspace_relative
        local_digest = sha256_file(path)
        assert local_digest == expected, f"workspace copy drift: {workspace_relative}"
        assert path.stat().st_size == info.file_size, f"workspace copy size drift: {workspace_relative}"
        self._append(
            source_kind="archive_member_and_workspace_copy",
            logical_path=logical_path,
            article_member=member,
            workspace_relative_path=workspace_relative,
            digest=expected,
            byte_count=info.file_size,
            binding="workspace bytes = ZIP member bytes = accepted root-manifest SHA-256",
            use=use,
        )
        return path


def metric_values(labels: np.ndarray, probabilities: np.ndarray) -> dict[str, Any]:
    prediction = probabilities >= THRESHOLD
    precision, recall, f1, _ = precision_recall_fscore_support(
        labels, prediction, average="binary", zero_division=0
    )
    matrix = confusion_matrix(labels, prediction, labels=[0, 1])
    return {
        "rows": int(len(labels)),
        "accuracy": float(accuracy_score(labels, prediction)),
        "balanced_accuracy": float(balanced_accuracy_score(labels, prediction)),
        "precision": float(precision),
        "recall": float(recall),
        "f1": float(f1),
        "roc_auc": float(roc_auc_score(labels, probabilities)),
        "average_precision": float(average_precision_score(labels, probabilities)),
        "tn": int(matrix[0, 0]),
        "fp": int(matrix[0, 1]),
        "fn": int(matrix[1, 0]),
        "tp": int(matrix[1, 1]),
    }


def row_bytes_view(array: np.ndarray) -> np.ndarray:
    assert array.ndim == 2 and array.flags.c_contiguous
    dtype = np.dtype((np.void, array.dtype.itemsize * array.shape[1]))
    return array.view(dtype).reshape(-1)


def membership(rows: np.ndarray, sorted_unique_reference: np.ndarray) -> np.ndarray:
    return np.isin(rows, sorted_unique_reference, assume_unique=False)


def check_raw_identity_isolation(pools: dict[str, dict[str, np.ndarray]]) -> None:
    for left, right in (("train", "validation"), ("train", "test"), ("validation", "test")):
        left_ids = np.ascontiguousarray(pools[left]["ids"]).view(
            np.dtype((np.void, pools[left]["ids"].dtype.itemsize * pools[left]["ids"].shape[1]))
        ).reshape(-1)
        right_ids = np.ascontiguousarray(pools[right]["ids"]).view(
            np.dtype((np.void, pools[right]["ids"].dtype.itemsize * pools[right]["ids"].shape[1]))
        ).reshape(-1)
        assert np.intersect1d(left_ids, right_ids).size == 0, f"row ID overlap: {left}/{right}"
        assert (
            np.intersect1d(pools[left]["fingerprints"], pools[right]["fingerprints"]).size == 0
        ), f"raw feature fingerprint overlap: {left}/{right}"


def load_pool(path: Path) -> dict[str, np.ndarray]:
    with np.load(path, allow_pickle=False) as pool:
        return {key: np.array(pool[key], copy=True) for key in ("y", "ids", "fingerprints")}


def add_metric_columns(row: dict[str, Any], prefix: str, values: dict[str, Any]) -> None:
    for metric in (
        "rows",
        "accuracy",
        "balanced_accuracy",
        "precision",
        "recall",
        "f1",
        "roc_auc",
        "average_precision",
        "tn",
        "fp",
        "fn",
        "tp",
    ):
        row[f"{prefix}_{metric}"] = values[metric]


def compute_overlap_table(
    binder: SourceBinder, classification_summary: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    validation: dict[str, Any] = {}

    for dataset in DATASETS:
        archive_base = f"raw/software/results/{dataset}"
        workspace_base = f"tnsm_experiments_v1/results/{dataset}"
        split_path = binder.bind_workspace_copy(
            f"{archive_base}/split_manifest.json",
            f"{workspace_base}/split_manifest.json",
            "fixed split identity and accepted row counts",
        )
        split_manifest = json.loads(split_path.read_bytes())

        x_paths: dict[str, Path] = {}
        pool_paths: dict[str, Path] = {}
        for split in SPLITS:
            x_paths[split] = binder.bind_workspace_copy(
                f"{archive_base}/{split}_X.npy",
                f"{workspace_base}/{split}_X.npy",
                "accepted train-fitted encoded inputs for exact-byte overlap diagnosis",
            )
            pool_paths[split] = binder.bind_workspace_copy(
                f"{archive_base}/{split}_pool.npz",
                f"{workspace_base}/{split}_pool.npz",
                "accepted labels, row IDs, and pre-encoding feature fingerprints",
            )
        prediction_path = binder.bind_workspace_copy(
            f"{archive_base}/test_predictions.npz",
            f"{workspace_base}/test_predictions.npz",
            "accepted cached test scores; no model inference performed",
        )

        arrays = {split: np.load(x_paths[split], mmap_mode="r", allow_pickle=False) for split in SPLITS}
        pools = {split: load_pool(pool_paths[split]) for split in SPLITS}
        for split in SPLITS:
            array = arrays[split]
            assert array.dtype == np.float32 and array.ndim == 2 and array.flags.c_contiguous
            assert len(array) == len(pools[split]["y"])
            assert np.isfinite(array).all(), f"nonfinite encoded value: {dataset}/{split}"
            expected_counts = split_manifest["sample_counts"][split]
            assert len(array) == expected_counts["rows"]
            assert int(pools[split]["y"].sum()) == expected_counts["attack"]
        check_raw_identity_isolation(pools)

        encoded = {split: row_bytes_view(arrays[split]) for split in SPLITS}
        unique = {split: np.unique(encoded[split]) for split in SPLITS}
        prior_unique = np.union1d(unique["train"], unique["validation"])

        validation_match_train = membership(encoded["validation"], unique["train"])
        test_match_train = membership(encoded["test"], unique["train"])
        test_match_validation = membership(encoded["test"], unique["validation"])
        test_match_prior = membership(encoded["test"], prior_unique)
        novel_mask = ~test_match_prior
        assert novel_mask.any() and np.unique(pools["test"]["y"][novel_mask]).size == 2

        overlapping_unique = np.intersect1d(unique["test"], prior_unique)
        conflicts = 0
        for value in overlapping_unique:
            labels: set[int] = set()
            for split in SPLITS:
                labels.update(int(x) for x in pools[split]["y"][encoded[split] == value])
            conflicts += int(len(labels) > 1)

        with np.load(prediction_path, allow_pickle=False) as cached:
            probabilities = np.array(cached["probabilities"], copy=True)
            labels = np.array(cached["labels"], copy=True)
            models = tuple(str(x) for x in cached["models"])
            assert models == MODELS
            assert np.array_equal(labels, pools["test"]["y"])
            assert np.array_equal(cached["ids"], pools["test"]["ids"])
            assert np.array_equal(cached["fingerprints"], pools["test"]["fingerprints"])
            assert probabilities.dtype == np.float32 and probabilities.shape == (len(labels), len(MODELS))

        base_counts = {
            "dataset": dataset,
            "encoding_dtype": "float32",
            "equality_rule": "exact full-row byte equality after accepted train-only preprocessing",
            "score_source": "accepted float32 test_predictions.npz cache",
            "fixed_threshold": THRESHOLD,
            "analysis_role": "post hoc diagnostic; main test result retained",
            "train_rows": len(arrays["train"]),
            "validation_rows": len(arrays["validation"]),
            "test_rows": len(arrays["test"]),
            "train_unique_encoded_rows": len(unique["train"]),
            "validation_unique_encoded_rows": len(unique["validation"]),
            "test_unique_encoded_rows": len(unique["test"]),
            "validation_rows_matching_train": int(validation_match_train.sum()),
            "validation_unique_vectors_matching_train": int(
                np.intersect1d(unique["validation"], unique["train"]).size
            ),
            "test_rows_matching_train": int(test_match_train.sum()),
            "test_unique_vectors_matching_train": int(
                np.intersect1d(unique["test"], unique["train"]).size
            ),
            "test_rows_matching_validation": int(test_match_validation.sum()),
            "test_unique_vectors_matching_validation": int(
                np.intersect1d(unique["test"], unique["validation"]).size
            ),
            "test_rows_matching_train_or_validation": int(test_match_prior.sum()),
            "test_unique_vectors_matching_train_or_validation": int(overlapping_unique.size),
            "overlapping_test_benign": int(np.count_nonzero(pools["test"]["y"][test_match_prior] == 0)),
            "overlapping_test_attack": int(np.count_nonzero(pools["test"]["y"][test_match_prior] == 1)),
            "overlapping_unique_vectors_with_cross_label_conflict": conflicts,
            "posthoc_novel_test_rows": int(novel_mask.sum()),
            "posthoc_novel_benign": int(np.count_nonzero(pools["test"]["y"][novel_mask] == 0)),
            "posthoc_novel_attack": int(np.count_nonzero(pools["test"]["y"][novel_mask] == 1)),
        }

        for model_index, model in enumerate(MODELS):
            full = metric_values(labels, probabilities[:, model_index])
            novel = metric_values(labels[novel_mask], probabilities[novel_mask, model_index])
            published = classification_summary[dataset][model]["test"]
            assert full["rows"] == published["rows"]
            assert [[full["tn"], full["fp"]], [full["fn"], full["tp"]]] == published[
                "confusion_matrix"
            ]
            for metric in ("accuracy", "balanced_accuracy", "precision", "recall", "f1"):
                assert abs(full[metric] - published[metric]) < 1e-12, (
                    dataset,
                    model,
                    metric,
                    "cached threshold metric differs from accepted main result",
                )
            row = dict(base_counts)
            row["model"] = model
            row["published_main_test_f1"] = published["f1"]
            row["published_main_test_roc_auc"] = published["roc_auc"]
            row["published_main_test_average_precision"] = published["average_precision"]
            add_metric_columns(row, "cached_full", full)
            add_metric_columns(row, "posthoc_novel", novel)
            for metric in (
                "accuracy",
                "balanced_accuracy",
                "precision",
                "recall",
                "f1",
                "roc_auc",
                "average_precision",
            ):
                row[f"delta_novel_minus_cached_full_{metric}"] = novel[metric] - full[metric]
            rows.append(row)

        validation[dataset] = {
            "encoded_dimensions": int(arrays["train"].shape[1]),
            "raw_row_ids_disjoint": True,
            "preencoding_feature_fingerprints_disjoint": True,
            "cached_threshold_metrics_match_accepted_main": True,
            "encoded_unique_rows": {split: int(len(unique[split])) for split in SPLITS},
            "validation_rows_matching_train": int(validation_match_train.sum()),
            "test_rows_matching_train": int(test_match_train.sum()),
            "test_rows_matching_validation": int(test_match_validation.sum()),
            "test_rows_matching_train_or_validation": int(test_match_prior.sum()),
            "test_unique_vectors_matching_train_or_validation": int(overlapping_unique.size),
            "encoded_overlap_cross_label_conflicts": int(conflicts),
            "posthoc_novel_test_rows": int(novel_mask.sum()),
        }

        del arrays, pools, encoded, unique, prior_unique, probabilities, labels

    return rows, validation


def recompute_static_aggregates(
    metrics_raw: bytes, old_aggregates_raw: bytes
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    metric_rows = list(csv.DictReader(io.StringIO(metrics_raw.decode("utf-8"))))
    old_rows = list(csv.DictReader(io.StringIO(old_aggregates_raw.decode("utf-8"))))
    assert len(metric_rows) == 200 and len(old_rows) == 20
    groups: dict[tuple[str, str, str], dict[str, list[float]]] = defaultdict(
        lambda: {"f1": [], "balanced_accuracy": [], "roc_auc": []}
    )
    seeds: dict[tuple[str, str, str], set[int]] = defaultdict(set)
    for row in metric_rows:
        key = (row["dataset"], row["scenario"], row["model"])
        seeds[key].add(int(row["seed"]))
        for metric in ("f1", "balanced_accuracy", "roc_auc"):
            groups[key][metric].append(float(row[metric]))

    output: list[dict[str, Any]] = []
    changed_intervals = 0
    for old in old_rows:
        key = (old["dataset"], old["scenario"], old["model"])
        assert key in groups and len(seeds[key]) == TRACE_SEEDS
        row: dict[str, Any] = {
            "dataset": key[0],
            "scenario": key[1],
            "model": key[2],
            "trace_seeds": TRACE_SEEDS,
        }
        for metric in ("f1", "balanced_accuracy", "roc_auc"):
            values = groups[key][metric]
            assert len(values) == TRACE_SEEDS
            mean = statistics.fmean(values)
            sd = statistics.stdev(values)
            half = T_CRITICAL * sd / math.sqrt(TRACE_SEEDS)
            row[f"{metric}_mean"] = mean
            row[f"{metric}_sd"] = sd
            row[f"{metric}_ci95_low"] = mean - half
            row[f"{metric}_ci95_high"] = mean + half
            assert abs(mean - float(old[f"{metric}_mean"])) < 2e-15
            assert abs(sd - float(old[f"{metric}_sd"])) < 2e-15
            if sd > 0:
                assert row[f"{metric}_ci95_low"] != float(old[f"{metric}_ci95_low"])
                changed_intervals += 1
        row["degrees_of_freedom"] = DF
        row["t_critical_0_975"] = T_CRITICAL
        row["ci_method"] = "two-sided Student-t 95% CI: mean +/- t(0.975,9)*sample_sd/sqrt(10)"
        row["uncertainty_scope"] = UNCERTAINTY_SCOPE
        output.append(row)
    assert set(groups) == {(r["dataset"], r["scenario"], r["model"]) for r in old_rows}
    return output, {
        "input_metric_rows": len(metric_rows),
        "aggregate_groups": len(output),
        "trace_seeds_per_group": TRACE_SEEDS,
        "degrees_of_freedom": DF,
        "t_critical_0_975": T_CRITICAL,
        "mean_and_sample_sd_match_original_aggregates": True,
        "recomputed_nonzero_sd_interval_fields": changed_intervals,
        "uncertainty_scope": UNCERTAINTY_SCOPE,
    }


def field_order(rows: list[dict[str, Any]]) -> list[str]:
    assert rows
    fields = list(rows[0])
    assert all(list(row) == fields for row in rows)
    return fields


def generate() -> tuple[dict[str, bytes], dict[str, Any]]:
    assert abs(T_CRITICAL - 2.2621571628540993) < 1e-15
    assert ARTICLE.is_file()
    with zipfile.ZipFile(ARTICLE) as archive:
        assert archive.testzip() is None
        manifest_raw = archive.read(ARTICLE_PREFIX + MANIFEST_NAME)
        manifest = parse_root_manifest(manifest_raw)
        zip_content = {
            info.filename[len(ARTICLE_PREFIX) :]
            for info in archive.infolist()
            if not info.is_dir()
            and info.filename.startswith(ARTICLE_PREFIX)
            and info.filename != ARTICLE_PREFIX + MANIFEST_NAME
        }
        assert not (set(manifest) - zip_content), "accepted root manifest lists absent content"
        accepted_manifest_omissions = zip_content - set(manifest)
        assert accepted_manifest_omissions == KNOWN_ACCEPTED_ROOT_MANIFEST_OMISSIONS, (
            "accepted root-manifest gap changed",
            sorted(accepted_manifest_omissions),
        )
        nested_manifests_covered = sorted(
            path for path in manifest if Path(path).name == MANIFEST_NAME
        )

        binder = SourceBinder(archive, manifest)
        binder.add_archive_identity()
        binder.add_root_manifest(manifest_raw)
        for omitted in sorted(KNOWN_ACCEPTED_ROOT_MANIFEST_OMISSIONS):
            binder.archive_bytes_not_listed_in_root_manifest(
                omitted,
                "explicitly register old root-manifest omission so the derived provenance does not hide it",
            )

        # Accepted method provenance.  Reading these bytes does not import or run them.
        for logical, workspace, use in (
            (
                "raw/software/audit_results.py",
                "tnsm_experiments_v1/audit_results.py",
                "accepted Student-t replay method and conditional-uncertainty wording",
            ),
            (
                "raw/software/classification_campaign.py",
                "tnsm_experiments_v1/classification_campaign.py",
                "accepted train-only encoding and fixed-threshold metric definitions",
            ),
            (
                "raw/software/static_replay.py",
                "tnsm_experiments_v1/static_replay.py",
                "accepted static replay provenance; entry point is not executed",
            ),
            (
                "raw/software/execution/results_audit.json",
                "tnsm_experiments_v1/execution/results_audit.json",
                "accepted audit result and replay interval interpretation",
            ),
        ):
            binder.bind_workspace_copy(logical, workspace, use)

        classification_path = binder.bind_workspace_copy(
            "raw/software/results/classification_summary.json",
            "tnsm_experiments_v1/results/classification_summary.json",
            "accepted published main test metrics retained unchanged",
        )
        classification_summary = json.loads(classification_path.read_bytes())

        replay_metrics_raw = binder.archive_bytes(
            "summary/static_replay_metrics.csv",
            "accepted 200 cached static replay evaluations",
        )
        old_aggregates_raw = binder.archive_bytes(
            "summary/static_replay_aggregates.csv",
            "old aggregate means/sample SDs and normal-critical intervals being corrected",
        )
        static_rows, static_validation = recompute_static_aggregates(
            replay_metrics_raw, old_aggregates_raw
        )
        accepted_audit = json.loads(
            (ROOT / "tnsm_experiments_v1/execution/results_audit.json").read_bytes()
        )
        accepted_f1 = {
            (row["dataset"], row["scenario"], row["model"]): row
            for row in accepted_audit["static_replay_f1_aggregates"]
        }
        assert len(accepted_f1) == len(static_rows) == 20
        for row in static_rows:
            prior = accepted_f1[(row["dataset"], row["scenario"], row["model"])]
            for actual, expected in (
                (row["f1_mean"], prior["f1_mean"]),
                (row["f1_sd"], prior["f1_sd"]),
                (row["f1_ci95_low"], prior["f1_mean_t95_interval"][0]),
                (row["f1_ci95_high"], prior["f1_mean_t95_interval"][1]),
            ):
                assert abs(actual - expected) < 5e-15
            assert prior["interpretation"] == UNCERTAINTY_SCOPE
        static_validation["accepted_audit_f1_student_t_rows_match"] = True
        overlap_rows, overlap_validation = compute_overlap_table(binder, classification_summary)

        source_fields = [
            "source_kind",
            "logical_path",
            "article_member",
            "workspace_relative_path",
            "sha256",
            "bytes",
            "binding",
            "use",
        ]
        source_rows = sorted(
            binder.rows,
            key=lambda row: (
                row["source_kind"].encode("utf-8"),
                row["logical_path"].encode("utf-8"),
                row["workspace_relative_path"].encode("utf-8"),
            ),
        )

        outputs = {
            "encoded_overlap_sensitivity.csv": csv_bytes(overlap_rows, field_order(overlap_rows)),
            "static_replay_aggregates_t95_recomputed.csv": csv_bytes(
                static_rows, field_order(static_rows)
            ),
            "SOURCE_HASHES.csv": csv_bytes(source_rows, source_fields),
        }
        validation = {
            "status": "PASS",
            "derivation_date": "2026-09-07",
            "accepted_baseline": {
                "filename": ARTICLE.name,
                "sha256": EXPECTED_ARTICLE_SHA256,
                "root_manifest_sha256": EXPECTED_ROOT_MANIFEST_SHA256,
                "root_manifest_entries": len(manifest),
                "root_manifest_exactly_covers_all_zip_content_except_itself": False,
                "root_manifest_omissions_registered_in_source_hashes": sorted(
                    accepted_manifest_omissions
                ),
                "nested_manifests_covered_by_old_root": nested_manifests_covered,
            },
            "preintegration_exact_name_search": {
                "roots": ["workspace", "Downloads", ".codex/attachments"],
                "files_examined": 57519,
                "zip_archives_examined": 139,
                "zip_errors": 0,
                "exact_named_artifacts_found": 0,
                "exact_requested_standalone_recomputation_code_found": False,
                "reusable_method_provenance_found": "accepted raw/software/audit_results.py Student-t implementation",
            },
            "static_replay": static_validation,
            "encoded_overlap_posthoc": overlap_validation,
            "scientific_boundaries": {
                "classification_training_executed": False,
                "materialization_executed": False,
                "static_replay_executed": False,
                "model_inference_executed": False,
                "accepted_splits_changed": False,
                "threshold_changed": False,
                "fixed_threshold": THRESHOLD,
                "main_results_replaced": False,
                "encoded_overlap_is_posthoc_diagnostic": True,
            },
            "source_bindings": {
                "records": len(source_rows),
                "all_used_workspace_copies_match_accepted_zip_and_root_manifest": True,
                "source_registry_sha256": sha256_bytes(outputs["SOURCE_HASHES.csv"]),
            },
            "derived_manifest_contract": {
                "covers_every_derived_content_file": True,
                "excludes_only_itself": True,
                "content_files": sorted(CONTENT_FILES),
                "higher_level_delivery_must_cover_this_nested_manifest": True,
            },
            "generated_outputs": {
                name: {"bytes": len(raw), "sha256": sha256_bytes(raw)}
                for name, raw in sorted(outputs.items())
            },
            "generator_sha256": sha256_file(HERE / "recompute_derived_summary.py"),
            "audit_sha256": sha256_file(HERE / "AUDIT.md"),
        }
        outputs["VALIDATION.json"] = json_bytes(validation)
        return outputs, validation


def manifest_bytes() -> bytes:
    actual = {path.name for path in HERE.iterdir() if path.is_file() and path.name != MANIFEST_NAME}
    assert actual == CONTENT_FILES, f"unexpected or missing derived-summary files: {sorted(actual ^ CONTENT_FILES)}"
    lines = []
    for name in sorted(actual, key=lambda value: value.encode("utf-8")):
        lines.append(f"{sha256_file(HERE / name)}  {name}\n")
    return "".join(lines).encode("utf-8")


def write_outputs(outputs: dict[str, bytes]) -> None:
    for name, raw in outputs.items():
        (HERE / name).write_bytes(raw)
    (HERE / MANIFEST_NAME).write_bytes(manifest_bytes())


def check_outputs(outputs: dict[str, bytes]) -> None:
    for name, expected in outputs.items():
        actual = (HERE / name).read_bytes()
        assert actual == expected, f"derived output drift: {name}"
    expected_manifest = manifest_bytes()
    assert (HERE / MANIFEST_NAME).read_bytes() == expected_manifest, "derived manifest drift"


def main() -> None:
    parser = argparse.ArgumentParser()
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument("--write", action="store_true", help="write deterministic derived outputs")
    action.add_argument("--check", action="store_true", help="recompute in memory and require byte identity")
    args = parser.parse_args()
    outputs, validation = generate()
    if args.write:
        write_outputs(outputs)
    else:
        check_outputs(outputs)
    print(
        json.dumps(
            {
                "status": validation["status"],
                "mode": "write" if args.write else "check",
                "static_groups": validation["static_replay"]["aggregate_groups"],
                "overlap_rows": len(DATASETS) * len(MODELS),
                "source_bindings": validation["source_bindings"]["records"],
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
