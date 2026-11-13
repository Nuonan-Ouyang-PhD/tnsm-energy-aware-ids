# TNSM Energy-Aware IDS: Auditable Experiment Repository

This repository contains the frozen protocol, deterministic materialization workflow,
classification/static baselines, Raspberry Pi power measurements, the evidence-locked
40-run adaptive scheduling study, and the P0/P1 strengthening analyses.

## Current evidence and manuscript status

The November 2026 corrected follow-up is the main current comparison:
[evidence and read-only reanalysis](releases/supplemental-followup-20261113/README.md).
It contains 60 accepted runs in ten paired blocks, with two invalid attempts
retained. Blocks 1 and 5 were recovered across periods. These are **author-validated**
artifacts; full independent byte-level and raw-log acceptance is **not complete**.
The independent review has so far reported execution-environment limitations;
it must not be replaced by our own PASS counts.

The working manuscript is now [manuscript_working/](manuscript_working/README.md),
pending scientific consistency and publication checks. The previous
`releases/submission/` bundle is historical, not the current submission-ready result.
No new measurement is planned or enabled by the read-only reanalysis entry point.

In the corrected follow-up, Q/DQN realize LightLR; DeadlineGuard realizes MedRF.
Neither policy switching nor an RL energy advantage over matched Static-LightLR
is established. Cascade has an implementation-specific energy/detection trade-off.
See the [scientific corrections](docs/SCIENTIFIC_CORRECTIONS_20261114.md) before
interpreting historical variable-load, ablation or reward-audit claims.

## Start here

- [Current corrected evidence and safe reanalysis](releases/supplemental-followup-20261113/README.md)
- [Current manuscript and response working tree](manuscript_working/README.md)
- [Historical submission ZIP](releases/submission/TNSM_Submission_Final.zip)
- [Historical main paper](releases/submission/package/Manuscript.pdf) · [Historical supplement](releases/submission/package/Supplementary_Material.pdf) · [Historical reviewer response](releases/submission/package/Response_to_Reviewers.pdf)
- [Historical LaTeX and build instructions](releases/submission/README.md)
- [Current reward audit](experiments/adaptive_scheduler_v1/reward_audit_validation/README.md)

The links above retain the previous submission for provenance. Dated evidence
directories record distinct experimental stages and must not be pooled.

## Quick verification

Python 3.11 or newer is required. These commands verify supplied artifacts and run
unit tests; they do not train policies or launch physical campaigns.

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[audit]'
make check-submission
make audit
make test
```

For the additional scheduler infrastructure tests (including DQN), install its
separate dependencies:

```bash
python -m pip install -e '.[scheduler]'
make test-scheduler
```

Artifact verification reproduces derived calculations from frozen inputs; it does
not recreate the original physical measurements. Raw-data retraining and physical
campaign execution require their own stage inputs and protocols.

## Historical author-reported state (not independent acceptance)

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
| Previous submission manuscript | Historical bundle; scientific interpretation superseded in part by corrected follow-up |

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
- `releases/submission/`: previous submission ZIP, historical source/PDFs and checksums; not the corrected current manuscript.

## Datasets and downloads

The experiments use three dataset-native pipelines:

- **TON-IoT** (UNSW Canberra) is the primary dynamic Raspberry Pi/KM003C study and uses 32 native features. Download from the [official UNSW dataset page](https://research.unsw.edu.au/projects/toniot-datasets).
- **CICIoT2023** (Canadian Institute for Cybersecurity, University of New Brunswick) is used for supplementary classification/replay analysis with 39 native features. Download from the [official CICIoT2023 page](https://www.unb.ca/cic/datasets/iotdataset-2023.html).
- **N-BaIoT** (UCI Machine Learning Repository, Dataset 442) is used for supplementary classification/replay analysis with 115 native features. Download from the [official UCI record](https://archive.ics.uci.edu/dataset/442/detection+of+iot+botnet+attacks+n+baiot).

The repository intentionally does not commit raw datasets, generated materializations,
or large physical traces. Place downloaded files only in the ignored paths documented
by the relevant request/inventory files, preserve the original filenames, and run the
read-only preflight before any derived work.

## Dataset and campaign tools

After acquiring the raw datasets and following the stage documentation:

```bash
make snapshot
make preflight
PYTHONPATH=src python3 experiments/classification_static_v1/classification_campaign.py --help
PYTHONPATH=src python3 experiments/classification_static_v1/static_replay.py --help
```

Read each stage plan and `experiments/reviewer_revision_v1/protocol/00_READ_FIRST.md`
before running a campaign. The default checks never start physical experiments.
The previous manuscript/source bundle is documented in
`releases/submission/README.md`; its archive SHA-256 is
`b13688a26a6f98577b1f2ca14726ebcf092e82f769c86879cad59f77548f1c0a`.

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

- The physical power measurements apply to the recorded Raspberry Pi 4B and POWER-Z KM003C (HW 2.4, FW 2.0.6) setup.
- TON-IoT power measurements are not claimed as measured costs for CICIoT2023 or N-BaIoT.
- Invalid and interrupted attempts remain preserved and are excluded according to their registries.
- Test traces are descriptive after policy freeze and were not used for training or checkpoint selection.
- The compact software-policy traces have no action-attributable post-action temperature. Their fixed 35 C fallback makes the executed thermal reward component zero; it is not evidence of thermal-aware adaptation.
- The current adapter represents missing post-action temperature as null and flags the unavailable measurement. Historical frozen runtime copies retain the originally executed bytes.
- The retrospective reward audit opens only configuration, the manifest, and five validation traces. TinyDT beats LightLR in 7/2,500 validation windows; pairwise exclusions for MedRF and HeavyMLP do not prove global LightLR optimality or pre-test audit execution. Current outputs are in `reward_audit_validation/`. The superseded audit that also read aggregate test diagnostics was removed from the active tree; its bytes remain available in [Git history](https://github.com/Nuonan-Ouyang-PhD/tnsm-energy-aware-ids/tree/c69f8cea3b267d4226f89693c535804536e836a8/experiments/adaptive_scheduler_v1/reward_audit_v1).
- Dataset splits, classifier thresholds, workloads, seeds, reward/state matrices, and gamma/alpha matrices remain frozen.
- R1 and R2 are post-hoc physical robustness experiments over the already frozen test pool, not new unseen-test generalization evidence.
- R3 and R4B stop records are part of the evidence: no missing protocol choice or unavailable reference load was improvised after observing results.

The full final validator report is available at
`releases/p0-p1-strengthening-20260908-v1/browsable/analysis/FINAL_VALIDATOR_REPORT.json`.
