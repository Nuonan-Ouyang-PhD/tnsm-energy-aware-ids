---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: 'e6d25675-e443-4a74-9b86-799d988b28e6'
  PropagateID: 'e6d25675-e443-4a74-9b86-799d988b28e6'
  ReservedCode1: 'e9218b3c-9312-4565-ab42-fd514a16932b'
  ReservedCode2: 'e9218b3c-9312-4565-ab42-fd514a16932b'
---

# Experiment decisions

1. All old tables, plots, and validation CSVs are historical drafting material,
   not formal evidence, because their raw logs, code, and provenance are absent.
2. Raspberry Pi 4 Model B 8 GB (`pi4b8g`) is the primary evaluation device.
3. The Pi 3B+, Pi 4B 4 GB, and Pi 5 are optional sequential portability checks;
   they are not required to run simultaneously with the primary device.
4. One external logging power meter is sufficient because devices are measured
   sequentially. Internal Pi telemetry is diagnostic, not a replacement for
   input-power measurement.
5. The M4 Mac mini is used for data preparation, model training, orchestration,
   aggregation, and plotting. It is not the claimed lightweight deployment target.
6. Pi 5 is excluded from the present stage while HORIZON00 is running.
7. Smoke results are always marked `paper_eligible=false`.
8. TON-IoT ground-truth CSVs are excluded. `train_test_network.csv` already
   carries the `label` and `type` label columns, and the 18 GroundTruth files
   (about 990 MB) correspond to the full Processed/Raw dataset that this
   experiment does not download. Per-row joins across versions would risk
   mixing dataset provenance, so the selected-subset status is
   `ground_truth: not_applicable_to_selected_subset`. If the full Processed
   Network data is ever adopted, the 23 processed CSVs and 18 ground-truth CSVs
   must be acquired, registered, and validated together as a new protocol
   version; they must never be mixed with the present subset.
9. The first TON-IoT acquisition and inventory manifests
   (`ton_iot_20260903T075757Z.json`, `ton_iot_20260903T075904Z.json`) were
   generated with the earlier, broader `selected_scope` wording ("processed
   and train/test network-traffic material") inherited from the stage-setup
   commit, which described more material than was actually acquired. The
   acquired bytes themselves are correct: `train_test_network.csv` plus the
   four official Network Features-Description / Statistics documents. The
   config and acquisition document now state the exact scope, and both
   manifests were regenerated against the corrected commit. The superseded
   manifests remain in the repository, unchanged, as append-only diagnostic
   records; only the regenerated manifests belong to the frozen evidence.
10. CICIoT2023 is acquired as the standard per-category directory release
    (`CSV/CSV.zip`, 309 CSV files in 34 category directories, 39 feature
    columns, no label column). Labels are derived deterministically from the
    directory and filename (`<Category>/<Capture>.pcap.csv`), which preserves
    the official capture boundaries for group-aware splits. The `MERGED_CSV`
    release is excluded: it is the same data merged, shuffled, and split with
    an attached `Label` column, but shuffling destroys the capture-group
    structure needed for leakage control, and switching releases to obtain a
    label column would silently hide quality issues in the directory release.
    Three files in the directory release (`DoS-UDP_Flood7.pcap.csv`,
    `DoS-UDP_Flood8.pcap.csv`, `DoS-UDP_Flood9.pcap.csv`) each end with one
    truncated final line (no trailing newline, 33/35/4 observed columns
    instead of 39). The raw CSVs remain unchanged; the three lines are
    registered in the quality-exception manifest
    (`artifacts/datasets/quality_exceptions/ciciot2023_*.json`) with their
    physical line numbers, byte lengths, and line hashes, and will be excluded
    deterministically by those registered positions during preprocessing. The
    three malformed rows constitute 6.413e-6% of the 46,776,700 inventoried
    rows. After deterministic exclusion, 46,776,697 structurally valid rows
    remain before subsequent preprocessing.
11. N-BaIoT is acquired as the official UCI ZIP (all nine device
    directories, CC BY 4.0, DOI 10.24432/C5RC8J). The inventory covers 90
    CSVs: 89 data files (9 benign + 45 Gafgyt/BASHLITE + 35 Mirai) plus one
    header-only `demonstrate_structure.csv` (1,776 bytes, zero data rows)
    shipped by the authors purely to document the 115-column layout. The
    zero-row demo file is retained in the inventory as shipped; it
    contributes no rows. Ennio_Doorbell and Samsung_SNH_1011_N_Webcam have
    no Mirai archive in the official release (7 of 9 devices carry both
    botnet families). Attack captures ship as RAR archives inside the ZIP:
    the official ZIP stays unchanged in `datasets/incoming/n_baiot/`, a copy
    is extracted to `datasets/extracted/n_baiot/`, the RARs are retained
    unchanged in the extracted device directories, and their CSV contents
    are unpacked into `<device>/<archive>_extracted/` copies. Because the
    first N-BaIoT manifests were generated against a commit that did not
    yet contain this RAR protocol text, all evidence commands now refuse a
    dirty worktree so manifests can only point at commits that actually
    contain the protocol being followed (see DECISIONS.md #12 for the
    gate); the first manifests remain as superseded diagnostic records.
12. The evidence commands (`dataset-register`, `dataset-inventory`,
    `dataset-quality-exceptions`) fail closed when the git worktree is
    dirty: uncommitted protocol text or code must never be referenced by a
    manifest `source_commit`, because the commit would not contain the
    protocol actually followed. Protocol changes are committed first and
    manifests are regenerated only after `git status` reports a clean
    worktree. Two narrow exemptions keep the gate usable without weakening
    it: untracked files under `artifacts/` (evidence manifests are the
    output of these very commands, so a fresh acquisition manifest must not
    block the immediately following inventory run) and untracked files under
    `.temp/` (agent scratch space, also gitignored). Staged, modified, or
    deleted tracked files, and untracked sources/docs/config anywhere else,
    always block.

> AI生成