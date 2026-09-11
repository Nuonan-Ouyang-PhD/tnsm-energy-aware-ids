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
| Reviewer R0 provenance/source audit | PASS |
| Reviewer R1 fixed-band confidence cascade | 40/40 valid physical runs |
| Reviewer R2 frozen variable-load factorial | 60/60 valid physical runs |
| Reviewer R3 controller-only power | Not executed; predeclared state-set ambiguity recorded |
| Reviewer R4 TinyDT/reference diagnostics | R4A complete; R4B not executed because no stable reference load was available |
| Merged submission manuscript | 8-page freshly compiled main PDF; source/PDF timestamp check passed |

The repository reports evidence and factual summaries. It does not infer superiority,
equivalence, or statistical significance from these files alone.

## Repository map

- `config/` and `docs/`: active frozen protocol and decision history.
- `src/tnsm_exp/`: acquisition, inventory, preflight, and validation tooling.
- `experiments/classification_static_v1/`: classification, cache, Pi parity, and static replay code/logs.
- `experiments/static_physical_v1/`: static physical-campaign controller and measurement code.
- `experiments/adaptive_scheduler_v1/`: scheduler implementation, configuration, cost registry, analysis, and packaging scripts.
- `experiments/reviewer_revision_v1/`: exact frozen reviewer-revision runtime source, protocol, configuration, and validation/packaging scripts.
- `releases/article-data-20260907-v1/`: the previously published article-data archive and browsable summaries.
- `releases/adaptive-scheduler-20260907-v1/`: evidence-locked original adaptive-study archive.
- `releases/p0-p1-strengthening-20260908-v1/`: P0/P1 final archive, registries, validators, and factual summaries.
- `releases/reviewer-revision-20260909-v1/`: complete reviewer-revision evidence archive plus browsable registries, factual summaries, stop/failure records, and validators.
- `releases/materialization-20260906-v2/`: materialization request, executor review chain, rebind, failure preservation, and successful run evidence.
- `releases/feature-protocol-freeze-20260905-v1/`: final feature-protocol freeze evidence.
- `releases/submission-complete-20260911-v1/`: the latest submission bundle, extracted LaTeX source, PDFs, dataset links, and reproduction notes.

## Datasets and downloads

The experiments use three dataset-native pipelines:

- **TON-IoT** (UNSW Canberra) is the primary dynamic Raspberry Pi/KM003C study and uses 32 native features. Download from the [official UNSW dataset page](https://research.unsw.edu.au/projects/toniot-datasets).
- **CICIoT2023** (Canadian Institute for Cybersecurity, University of New Brunswick) is used for supplementary classification/replay analysis with 39 native features. Download from the [official CICIoT2023 page](https://www.unb.ca/cic/datasets/iotdataset-2023.html).
- **N-BaIoT** (UCI Machine Learning Repository, Dataset 442) is used for supplementary classification/replay analysis with 115 native features. Download from the [official UCI record](https://archive.ics.uci.edu/dataset/442/detection+of+iot+botnet+attacks+n+baiot).

The repository intentionally does not commit raw datasets, generated materializations,
or large physical traces. Place downloaded files only in the ignored paths documented
by the relevant request/inventory files, preserve the original filenames, and run the
read-only preflight before any derived work.

## Reproduce the software and paper artifacts

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
make test
```

For the frozen dataset checks and deterministic pipelines:

```bash
make snapshot
make preflight
PYTHONPATH=src python3 experiments/classification_static_v1/classification_campaign.py --help
PYTHONPATH=src python3 experiments/classification_static_v1/static_replay.py --help
PYTHONPATH=src python3 -m unittest discover -s experiments/adaptive_scheduler_v1/scheduler -v
```

Read each stage plan and `experiments/reviewer_revision_v1/protocol/00_READ_FIRST.md`
before running a campaign. The default checks never start physical experiments.
The latest manuscript/source bundle is documented in
`releases/submission-complete-20260911-v1/README.md`; its refreshed archive
SHA-256 is
`419b834d9e523123075a049491ef16092dcdf73b7301e78d25888b1b47fe88fd`.

## Reconstructing large archives

Large archives are split into GitHub-compatible parts. Reassemble them in lexical order:

```bash
cat releases/adaptive-scheduler-20260907-v1/TNSM_ADAPTIVE_SCHEDULER_20260907_V1.zip.part-* \
  > TNSM_ADAPTIVE_SCHEDULER_20260907_V1.zip

cat releases/p0-p1-strengthening-20260908-v1/TNSM_P0_P1_STRENGTHENING_20260908_V1.zip.part-* \
  > TNSM_P0_P1_STRENGTHENING_20260908_V1.zip

cat releases/reviewer-revision-20260909-v1/TNSM_REVIEWER_REVISION_EVIDENCE_20260909_V1.zip.part-* \
  > TNSM_REVIEWER_REVISION_EVIDENCE_20260909_V1.zip
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
- R1 and R2 are post-hoc physical robustness experiments over the already frozen test pool, not new unseen-test generalization evidence.
- R3 and R4B stop records are part of the evidence: no missing protocol choice or unavailable reference load was improvised after observing results.

## Basic checks

```bash
make test
```

The full final validator report is available at
`releases/p0-p1-strengthening-20260908-v1/browsable/analysis/FINAL_VALIDATOR_REPORT.json`.
