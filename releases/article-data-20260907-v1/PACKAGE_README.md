# TNSM article data delivery V1

Created: 2026-09-07 (Australia/Melbourne)

This delivery contains all experiment data completed at packaging time:

- Materialization evidence and the published data-tree identity (54,050,346 rows; 399 shard pairs).
- Classifier results for 3 datasets x 4 models, including split manifests, fitted artifacts, held-out predictions and replay traces.
- Raspberry Pi parity/timing evidence for 12 model-dataset combinations.
- Fifteen valid 30-minute whole-device static power profiles, including every raw 1 Hz meter record and Pi telemetry record.
- Two interrupted physical attempts retained under `raw/physical`; they are excluded from result summaries.

The 17 GB materialized tree is not duplicated into this folder. Its canonical location is:

`/Volumes/RESEARCH_DATA/TNSM-MATERIALIZATION-20260906-V1`

Its root manifest SHA-256 is `d79caa7ed64d1e37c0599b12bbc0af925a1c469090dfab8f104dcd6ffb9dbd1e`.

## Critical article boundary

Adaptive CFSM, Tabular-Q, DQN, offline-oracle comparisons and the planned 40 x 500-second paired physical campaign have not been run. Do not report any adaptive-policy or paired-energy number as an experimental result.

Static power is measured at the Pi USB input using a POWER-Z KM003C at 1 Hz. It is an uncalibrated load-side USB measurement under a user-accepted supply that read approximately 5.4 V. It is not wall-AC energy.

Use `summary/TNSM_article_results.xlsx` for manuscript tables, the CSV files for direct analysis, and `raw/` for exact machine-readable evidence. `MANIFEST_SHA256.txt` covers every delivered file except itself.
