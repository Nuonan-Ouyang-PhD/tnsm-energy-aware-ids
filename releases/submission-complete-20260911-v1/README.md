# TNSM submission-complete package (2026-09-11)

This release is the refreshed merged submission bundle based on the verified
eight-page manuscript baseline. The main PDF was freshly compiled from the
included LaTeX source after restoring the DeadlineGuard, DQN block-diagnostic,
cascade-window, and Tabular-Q support analyses.

SHA-256 of the refreshed archive:

```text
419b834d9e523123075a049491ef16092dcdf73b7301e78d25888b1b47fe88fd
```

The archive contains the refreshed 8-page manuscript PDF, 26-page supplement,
response to reviewers, cover letter, complete LaTeX source tree, offline
threshold diagnostics, and the final validation report. It does not contain the
raw datasets or the large physical-evidence archives.

## Datasets used

The paper uses three dataset-native pipelines:

1. **TON-IoT** (UNSW Canberra): the primary dynamic Raspberry Pi/KM003C study
   and the main 32-feature pipeline.
2. **CICIoT2023** (Canadian Institute for Cybersecurity, University of New
   Brunswick): supplementary dataset-native classification/replay pipeline with
   39 native features.
3. **N-BaIoT** (UCI Machine Learning Repository, Dataset 442): supplementary
   dataset-native classification/replay pipeline with 115 native features.

Download from the official custodians:

- TON-IoT: <https://research.unsw.edu.au/projects/toniot-datasets>
- CICIoT2023: <https://www.unb.ca/cic/datasets/iotdataset-2023.html>
- N-BaIoT: <https://archive.ics.uci.edu/dataset/442/detection+of+iot+botnet+attacks+n+baiot>

The custodians may require registration or acceptance of their terms. Cite the
dataset papers requested on those pages. Do not rename files after download if
you intend to reproduce the frozen inventories.

## Reproduction workflow

From the repository root:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e .
make test
```

The basic checks compile the package and run the repository unit tests. The
reproducible evidence workflow is staged so that raw data and large archives
remain outside Git:

```bash
# 1. Place downloaded data only in the ignored paths documented by the request.
make snapshot
make preflight

# 2. Run deterministic classification/static checks (read the stage plan first).
PYTHONPATH=src python3 experiments/classification_static_v1/classification_campaign.py --help
PYTHONPATH=src python3 experiments/classification_static_v1/static_replay.py --help

# 3. Run scheduler software tests and inspect the frozen protocol.
PYTHONPATH=src python3 -m unittest discover -s experiments/adaptive_scheduler_v1/scheduler -v
sed -n '1,220p' experiments/reviewer_revision_v1/README.md
sed -n '1,220p' experiments/reviewer_revision_v1/protocol/00_READ_FIRST.md
```

The physical campaigns are evidence-locked and are **not** started by the
default checks. Their raw ledgers, device identity records, and power traces are
available through the release archives under `releases/`; reconstruct split
archives in lexical part order, verify the release `ARCHIVE_SHA256.txt`, and
then verify the archive's `MANIFEST_SHA256.txt`.

## Scope and boundaries

- Dynamic power claims apply to TON-IoT on the recorded Raspberry Pi 4B 8 GB
  and inline POWER-Z KM003C setup only.
- CICIoT2023 and N-BaIoT are classification/replay evidence, not cross-dataset
  dynamic-power measurements.
- Frozen splits, classifier thresholds, workloads, seeds, reward/state matrices,
  and the original 40-run physical campaign remain unchanged.
- Invalid/interrupted attempts remain preserved and are excluded only through
  their registries.

The PDFs in this release are for reading and submission. For byte-level
reproduction, use the source tree and the corresponding evidence archive rather
than retyping values from the PDFs.

## Fresh-build integrity

The latest `.tex` source modification predates the delivered manuscript PDF.
The main PDF contains the restored `0.7967` non-degeneracy threshold, the
`43.714 J` DeadlineGuard comparison, `512/5,000` deadline count, `314/324`
support map, `66.76%` cascade-window statistic, all-detector threshold table,
CFSM occupancy, and the explicitly non-measured DQN timing sensitivity bound.
The archive contains 84 files, passes ZIP CRC, and includes the source manifest
at `Source_Files/MANIFEST_SHA256.txt` plus the validation report at
`Source_Files/FINAL_VALIDATION_REPORT.json`.
