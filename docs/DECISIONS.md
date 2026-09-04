---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '3f565afc-23da-4199-abc8-018b7517a10f'
  PropagateID: '3f565afc-23da-4199-abc8-018b7517a10f'
  ReservedCode1: '15aa8c55-a051-43c2-9f46-4ad8065c4a4e'
  ReservedCode2: '15aa8c55-a051-43c2-9f46-4ad8065c4a4e'
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
13. N-BaIoT is frozen as `N-BAIOT-20260904-V1-FROZEN` after independent
    verification by the author. Frozen evidence: evidence ZIP
    `n_baiot_evidence.zip` (SHA-256 `6cd97c52100b3ced8e2ebf182868fa7016152
    cb7aa0595e1c27dbb4b5bf50750`, 9,746 bytes, exactly the two latest
    manifests), acquisition JSON SHA-256 `a99de209873c43f2ae9cf538fbe610f4
    484b45d0ae452f24bf814dd12704799c`, inventory JSON SHA-256
    `9ffdf7e9245470fc4f066b8fb6d8ebae03e0194e7698e5fde87b13a7f2fe30da`,
    official ZIP hash `64929678b081d8e579a8d7c488cf11cc588403f282d5fb065b41
    56edbd55de9b`, protocol source commit `1638f6985134d802b6c1c8faa30ec33a
    12f82ea1`. Verified: 90 CSVs = 89 data files + 1 zero-row structure
    example; 7,062,606 rows; 115 columns; 0 malformed rows; one identical
    header across all 90 files; no duplicate paths or hashes; 9 benign + 45
    Gafgyt + 35 Mirai; the Ennio/Samsung no-Mirai structure preserved. With
    this freeze the acquisition stage of all three datasets (TON-IoT,
    CICIoT2023, N-BaIoT) is complete. Feature-mapping design reads only the
    inventory manifests (no large data copies) given limited disk space.
14. Label ontology and feature direction: `binary_label` (benign/attack)
    is the only mandatory cross-dataset unified label. `canonical_family`
    is a conservative standardized family layer where absent families are
    recorded as `not_available` (a coverage statement, never a negative
    class; no forcing into an `other` bucket). `source_subtype` preserves
    official labels verbatim and is never a cross-dataset task. Gafgyt maps
    to `canonical_family = bashlite` with combo/junk/scan/tcp/udp kept as
    source subtypes; Gafgyt tcp/udp are not re-labelled DDoS and Gafgyt
    scan is not merged into Recon (family and behavior are different
    axes). Feature direction: dataset-native feature sets are primary
    (TON-IoT max 42 candidates after excluding label/type, CICIoT2023 39,
    N-BaIoT 115), a strictly audited semantic core is secondary with no
    assumed target size; pairwise cores are permitted and an honestly
    reported empty three-way core is acceptable. TON-IoT leakage
    exclusions: label, type, src_ip, dst_ip, dns_query, ssl_subject,
    ssl_issuer, http_uri, http_user_agent, weird_addl are permanently
    excluded; src_port/dst_port only as predefined port classes; the ten
    listed categorical fields are native-only with train-split-fitted
    encoders; IP/device/file/capture identifiers may be used for
    group-aware splits but never as model features. CICIoT2023 verified
    counts: 45,678,509 attack + 1,098,191 benign raw rows; after
    excluding the three registered truncated lines, 45,678,506 attack +
    1,098,191 benign; after excluding the three registered truncated
    lines, 45,678,506 attack + 1,098,191 benign. Two ratios are recorded
    separately and must not be conflated: binary attack:benign ≈
    41.594:1; largest/smallest source class ≈ 5,751.2:1.
    The root-level zero-row `demonstrate_structure.csv` never enters
    training. All label/feature mappings currently carry status
    `proposed`; freeze requires the official field-document review and the
    TON-IoT `type` value inventory. Protocol documents:
    docs/LABEL_ONTOLOGY.md, docs/FEATURE_MAPPING_PROTOCOL.md,
    config/label_ontology.json, config/feature_policy.json.

15. Field semantics review frozen as
     `FIELD-SEMANTICS-REVIEW-20260904-V1-FROZEN` after independent
     verification by the author. Frozen evidence: evidence ZIP
     `FIELD_SEMANTICS_REVIEW_EVIDENCE_V3.zip` (SHA-256 `f2ede3e41f7477
     d9bd3e916a57dacbc5a38d698a124ccd18b823f768dcb7f006`, 2,168,957
     bytes), source commit `8181c8a`. Review outcomes: three-way
     semantic core is EMPTY (no concept passes seven gates in all three
     datasets); pairwise core limited to TON-IoT↔CICIoT2023
     (protocol_indicators = derived/proposed, packet_count = unresolved/
     proposed); N-BaIoT structurally incompatible with the other two
     (damped-window stream statistics vs per-connection logs vs
     whole-flow aggregates). N-BaIoT MI_dir_* resolved as derived
     evidence: Source MAC-IP aggregation by elimination from Meidan et
     al. 2018 group widths (arXiv:1805.03409v1; published as IEEE
     Pervasive Computing vol. 17 no. 3 pp. 12-22, DOI
     10.1109/MPRV.2018.03367731). Mapping status split into two
     dimensions: `semantic_disposition` (exact/derived/unresolved/
     rejected) and `decision_status` (proposed/frozen). Open points:
     CICIoT2023 IAT aggregate undocumented, Variance direction ambiguous,
     README feature table vs frozen 39-column header mismatch (header
     authoritative). `feature_policy.status` remains `proposed`:
     the frozen item is the field-semantics review fact record, not the
     cross-dataset mapping itself.

     > AI生成

> AI生成