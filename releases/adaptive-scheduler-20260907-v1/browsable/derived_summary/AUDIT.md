# Derived static-summary audit

Date: 2026-09-07

## Status and immutable baseline

This directory is a pure derivation from the accepted `TNSM_ARTICLE_DATA_20260907_V1.zip` baseline (SHA-256 `c135da2db921dc442b4fbea7bd2596aaef8f1eda2f553945d400168d77375c74`). It does not replace or modify the baseline, classifier models, splits, prediction caches, replay traces, telemetry, or interrupted-run records.

Before integration, an exact-name search examined 57,519 visible files and the member names of 139 ZIP archives across the workspace, `Downloads`, and `.codex/attachments`. No existing `encoded_overlap_sensitivity.csv` or `static_replay_aggregates_t95_recomputed.csv` was found, and no dedicated encoded-overlap recomputation program was found. The accepted `raw/software/audit_results.py` was reusable method provenance: it already applies Student-t to ten replay seeds and states the conditional uncertainty scope. The two requested CSVs and the reproducible generator in this directory were therefore derived from accepted cached artifacts only.

`SOURCE_HASHES.csv` binds every input used here. Each used workspace copy was checked byte-for-byte by SHA-256 against both the corresponding accepted ZIP member and the ZIP root manifest. The accepted archive hash and root-manifest hash are recorded separately. Audit of the old accepted root manifest found that it omits two nested manifests: `raw/materialization/MANIFEST_SHA256.txt` and `raw/materialization/materialization_run_v2/MANIFEST_SHA256.txt`. Their actual hashes are now registered explicitly in `SOURCE_HASHES.csv` and remain transitively bound by the accepted whole-archive hash. This records and corrects the provenance gap without rewriting the immutable V1 archive or falsely claiming its old manifest was complete.

## Student-t replay intervals

`static_replay_aggregates_t95_recomputed.csv` retains the accepted 200 cached static evaluations, their 20 dataset/scenario/model groups, and the original group means and sample standard deviations. For each metric it recomputes the two-sided interval as

```text
mean ± t(0.975, df=9) × sample_sd / sqrt(10)
t(0.975, 9) = 2.2621571628540993
```

The interval describes workload-resampling variation conditional on one fixed classifier-training seed and one fixed split. It is not a confidence interval over retraining, model selection, hardware, or physical energy. No static trace was regenerated or replayed.

## Encoded-input overlap sensitivity

`encoded_overlap_sensitivity.csv` compares accepted `float32` encoded rows by exact full-row bytes after the accepted train-only preprocessing. For the test sensitivity, "prior" means the union of train and validation encoded vectors. Metrics for the post hoc novel-vector subset use only the accepted `float32` test prediction cache and the unchanged threshold `0.5`; no model was loaded for inference.

The accepted pre-encoding feature fingerprints and row IDs remain disjoint across splits. Encoded equality is a different, lossy-representation diagnostic:

| Dataset | Validation rows matching train | Test rows matching train∪validation | Distinct overlapping test vectors | Post hoc novel test rows |
|---|---:|---:|---:|---:|
| ton_iot | 0 | 0 | 0 | 22,490 |
| ciciot2023 | 27 | 24 | 24 | 71,121 |
| n_baiot | 21,832 | 14,449 | 7 | 68,906 |

No overlapping encoded vector has conflicting labels in the accepted selected pools. In N-BaIoT, many rows collapse onto seven repeated encoded vectors; that is reported as a diagnostic property, not used to change the experiment. Across the four cached models, the post hoc novel-minus-full F1 changes are approximately zero for TON-IoT, between `-0.0000043` and `-0.0000024` for CICIoT2023, and between `-0.000534` and `-0.000064` for N-BaIoT. Exact values and all requested metrics are in the CSV.

This analysis is explicitly post hoc. It does not authorize re-splitting, threshold tuning, retraining, model selection, exclusion of accepted test rows, or replacement of the main test results. Cached `float32` ranking metrics are labeled as such because score quantization can make them differ slightly from the original full-precision ROC-AUC or average precision; the accepted published main ranking metrics are retained in separate columns.

## Execution boundary and reproducibility

The generator reads `.npy`, `.npz`, JSON, and CSV caches and calculates summaries in memory. It does not import or invoke classification training, materialization, static replay, adaptive scheduling, or hardware interfaces. `VALIDATION.json` records the checks and boundaries. Run with the accepted project environment:

```text
tnsm_experiments_v1/.venv/bin/python adaptive_scheduler_v1/derived_summary/recompute_derived_summary.py --check
```

`MANIFEST_SHA256.txt` covers every file in this directory except itself. If this directory is later placed inside a larger delivery, the delivery's root manifest must include this nested `MANIFEST_SHA256.txt` as a normal content file while excluding only the delivery root manifest itself.
