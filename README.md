# TNSM Energy-Aware IDS: Auditable Experiment Repository

This repository contains the frozen protocol, deterministic materialization workflow,
classification/static baselines, Raspberry Pi power measurements, the evidence-locked
40-run adaptive scheduling study, and the P0/P1 strengthening analyses.

## Current verified state

| Stage | Status |
| --- | --- |
| Label ontology and feature protocol | Frozen |
| Materialization | Complete and validated |
| 12 classification models and prediction cache | Complete |
| Raspberry Pi parity and timing | Complete |
| 15-segment static physical-power study | Complete |
| Original adaptive physical study | 40/40 valid runs; evidence locked |
| P0 exact executed-source recovery | Complete, 6/6 source hashes matched |
| P1A Static-LightLR matched physical control | 40 valid runs in 10 paired blocks |
| P1B isolated scheduler overhead | Corrected replacement 240/240 valid; original 240 retained as invalid history |
| P1C multi-seed frozen-policy evaluation | 20/20 complete; no retraining |
| P1D reward/state sensitivity | 85/85 valid |
| P1E gamma/alpha sensitivity | 35/35 valid |

The repository reports evidence and factual summaries. It does not infer superiority,
equivalence, or statistical significance from these files alone.

## Repository map

- `config/` and `docs/`: active frozen protocol and decision history.
- `src/tnsm_exp/`: acquisition, inventory, preflight, and validation tooling.
- `experiments/classification_static_v1/`: classification, cache, Pi parity, and static replay code/logs.
- `experiments/static_physical_v1/`: static physical-campaign controller and measurement code.
- `experiments/adaptive_scheduler_v1/`: scheduler implementation, configuration, cost registry, analysis, and packaging scripts.
- `releases/article-data-20260907-v1/`: the previously published article-data archive and browsable summaries.
- `releases/adaptive-scheduler-20260907-v1/`: evidence-locked original adaptive-study archive.
- `releases/p0-p1-strengthening-20260908-v1/`: P0/P1 final archive, registries, validators, and factual summaries.
- `releases/materialization-20260906-v2/`: materialization request, executor review chain, rebind, failure preservation, and successful run evidence.
- `releases/feature-protocol-freeze-20260905-v1/`: final feature-protocol freeze evidence.

## Reconstructing large archives

Large archives are split into GitHub-compatible parts. Reassemble them in lexical order:

```bash
cat releases/adaptive-scheduler-20260907-v1/TNSM_ADAPTIVE_SCHEDULER_20260907_V1.zip.part-* \
  > TNSM_ADAPTIVE_SCHEDULER_20260907_V1.zip

cat releases/p0-p1-strengthening-20260908-v1/TNSM_P0_P1_STRENGTHENING_20260908_V1.zip.part-* \
  > TNSM_P0_P1_STRENGTHENING_20260908_V1.zip
```

Verify the reconstructed files against each release directory's
`ARCHIVE_SHA256.txt`, then use the archive's root `MANIFEST_SHA256.txt` for
content-level verification.

## Evidence boundaries

- The physical power measurements apply to the recorded Raspberry Pi 4B and KM003C setup.
- TON-IoT power measurements are not claimed as measured costs for CICIoT2023 or N-BaIoT.
- Invalid and interrupted attempts remain preserved and are excluded according to their registries.
- Test traces are descriptive after policy freeze and were not used for training or checkpoint selection.
- Dataset splits, classifier thresholds, workloads, seeds, reward/state matrices, and gamma/alpha matrices remain frozen.

## Basic checks

```bash
make test
```

The full final validator report is available at
`releases/p0-p1-strengthening-20260908-v1/browsable/analysis/FINAL_VALIDATOR_REPORT.json`.
