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

16. TON-IoT type mapping frozen as
    `TON-IOT-TYPE-MAPPING-20260904-V1-FROZEN` after independent
    verification by the author. Frozen evidence: evidence ZIP
    `TON_IOT_TYPE_MAPPING_EVIDENCE_V3.zip` (SHA-256 `f774457585db719
    bc223a89cc965aabef7019bec1f0f6209a0ce160e3a4eecc4`, 16,677 bytes),
    source commit `b95e7bc`. All 10 ton_iot_type_mapping entries carry
    `decision_status: frozen`: normal→benign (exact, coverage
    invariant, not counted among the 9 attack classes); backdoor, ddos,
    dos, injection, password, ransomware, mitm → same-named families
    (exact); scanning→recon and xss→web_attack (derived, source_type
    and family being different axes). No mapping, semantic_disposition,
    evidence, or rationale was changed at freeze time; the freeze marks
    verified facts only. The pre-existing fixed decision
    gafgyt→bashlite (exact, Meidan et al. 2018 evidence) remains
    frozen and is not affected. The ontology root `status` and the
    `canonical_family.decision_status` root remain `proposed` until
    the CICIoT2023 and N-BaIoT mapping stages are separately frozen.
    Next stage: CICIoT2023 33 attack subtypes + Benign_Final →
    canonical_family mapping, following the same field schema,
    proposed-first workflow, and user verification before freeze.

17. CICIoT2023 type-mapping v1 user verification (four adjudications)
    and v2 revision. The v1 evidence ZIP
    `CICIOT2023_TYPE_MAPPING_EVIDENCE_V1.zip` (SHA-256 `4486874688c3
    cda548f9f0bca59e59fc7e2a3549c3f3487e9b31fd2695029906`, 20,638
    bytes, source commit `a56bbc8`) was independently verified by the
    author: ZIP hash match, CRC pass, 34 directories closed against
    the frozen inventory, per-class counts match 309 files /
    46,776,700 rows, all 34 entries proposed, in-package tests 49/49
    PASS. TON-IoT freeze (#16) separately confirmed valid. Four
    adjudications on the v1 decision points: (1) spoofing family
    ACCEPTED (UNB places ARP/DNS spoofing under Spoofing);
    (2) MITM-ArpSpoofing→spoofing ACCEPTED as exact (official
    category axis; consequence: the TON-IoT mitm family has no
    CICIoT2023 member and the deferred cross-dataset MITM comparison
    is not established); (3) DictionaryBruteForce→password REJECTED —
    it would force the official Brute Force category into the
    TON-IoT password family without cross-dataset equivalence
    evidence; (4) Backdoor_Malware→web_attack ACCEPTED as exact (UNB
    places Backdoor malware under Web-based). v2 revision applied
    accordingly: new brute_force family (candidate_families 13 → 14);
    DictionaryBruteForce→brute_force, exact; the CICIoT2023 mapping
    becomes 34 exact / 0 derived. Explicitly recorded: TON-IoT
    password is NOT equated with CICIoT2023 brute_force — no
    sufficient evidence to establish a cross-dataset comparison
    between these two families; the comparison-candidate phrase in
    the frozen TON-IoT password rationale (#16, predates this
    decision) is superseded here and recorded as NOT established.
    The frozen TON-IoT entries themselves are NOT modified.
    Official-source inconsistency recorded: the UNB page
    (https://www.unb.ca/cic/datasets/iotdataset-2023.html, snapshot
    `references/dataset_docs/ciciot2023/unb_iotdataset_page_2026-09-04.html`,
    SHA-256 `99ae08c233d26aaa1c6cc5baa9eb6860587077cc2bc1097c63457bface422852`)
    states 33 attacks but its own category detail lists enumerate
    only 32 (the DDoS list omits DDoS-ICMP_Fragmentation); the frozen
    dataset directories and README.pdf both contain that category,
    so the formal enumeration baseline is the frozen inventory
    directories plus README.pdf, not the UNB page detail lists. The
    seven README.pdf page-2 classification panels are archived under
    `references/dataset_docs/ciciot2023/readme_p2_panels/` with
    SHA-256 in `registry.json`, so the classification evidence is
    independently re-checkable. The v2 mapping remains entirely
    decision_status=proposed; data materialization, splitting, and
    training remain forbidden until the v2 freeze.


    v2 evidence-package revision (Rev 1), per user verification of the
    v2 package: (1) the injected watermark metadata blocks and
    trailing machine-generated marker lines were stripped from
    DECISIONS.md and LABEL_ONTOLOGY.md (they were
    workspace-injection artifacts, not content); (2) the README Brute
    Force item is a single attack name "Dictionary Brute Force"
    (rendered across three lines by the PDF page layout), not two
    attack names -
    the earlier "Dictionary and Brute Force" split wording was
    corrected in label_ontology.json, LABEL_ONTOLOGY.md and
    registry.json (the DictionaryBruteForce -> brute_force exact
    mapping itself is unchanged); (3) the MITM-ArpSpoofing rationale
    no longer describes the mitm family alternative as open - it was
    considered and rejected under this decision #17; (4) registry.json
    now carries the SHA-256 of each of the seven README.pdf page-2
    panel PNGs, and guard tests lock the new wording and hashes. The
    v2 mapping remains entirely decision_status=proposed; no freeze
    action is taken in this revision.


18. CICIoT2023 type mapping FROZEN as
    CICIOT2023-TYPE-MAPPING-20260904-V1-FROZEN. Freeze basis: the v2
    evidence package went through user verification in three rounds
    (v2 → Rev 1 → Rev 2). Rev 1 (commit `1e26a56`) fixed four
    package-level issues (injected watermark artifacts stripped;
    Dictionary Brute Force single-attack-name wording; mitm
    alternative closed as considered and rejected under #17; seven
    panel SHA-256 entries added to registry.json). Rev 2 (commit
    `93e8350`) corrected the line-count wording to "rendered across
    three lines by the PDF page layout" (verified against the panel
    PNG; the attack name renders as Dictionary / Brute / Force on
    three lines). The Rev 2 evidence ZIP
    `CICIOT2023_TYPE_MAPPING_EVIDENCE_V2R2.zip` (SHA-256 `f8529ea2
    c721057ce205b862ff37bb3a4cbcb1c8d5524d30cc0b28f93f3d447b`,
    4,454,486 bytes, 25 entries, source commit `93e8350`) passed the
    user's independent verification: MANIFEST 16/16, in-package tests
    56/56 (33+23), old wording zero hits, new wording exactly 5,
    injected-watermark markers zero, 34 proposed / 0 frozen before
    freeze, TON-IoT
    10 frozen untouched, #18 not yet existing. On explicit user
    authorization, all 34 CICIoT2023 mapping entries now carry
    decision_status=frozen: 34 exact / 0 derived (12 ddos, 6
    web_attack incl. Backdoor_Malware, 5 recon, 4 dos, 3 mirai, 2
    spoofing, 1 brute_force, 1 benign). The freeze changed only
    decision_status values and the description freeze metadata; no
    mapping, official_category, semantic_disposition, evidence, or
    rationale was altered. Cross-dataset constraints carried forward:
    TON-IoT password is NOT equated with CICIoT2023 brute_force
    (#17); the TON-IoT mitm family has no CICIoT2023 member (MITM-
    ArpSpoofing → spoofing, rejected alternative recorded); family
    presence in N-BaIoT (mirai) remains presence-only until its own
    freeze. The TON-IoT frozen entries are NOT modified. Because the
    N-BaIoT mapping is not yet frozen, the ontology root status and
    canonical_family.decision_status both remain `proposed`. Data
    materialization, splitting, and training remain forbidden until
    the ontology-level freeze is complete. Next stage: N-BaIoT type
    mapping proposal (mirai_attacks_extracted/ and
    gafgyt_attacks_extracted/ subtypes), then the root-level
    ontology freeze decision.


19. N-BaIoT family/subtype mapping proposed as
    N-BAIOT-TYPE-MAPPING-20260904-V1-PROPOSED. Basis: Meidan et al. 2018
    (references/dataset_docs/n_baiot/meidan2018_arxiv_v1_2026-09-04.pdf,
    SHA-256 1fa5bc4d4d2a12c2e93b18c4d876bd83ab7f456797934fcc71c92db754811964)
    pages 4-5 "Attacks executed" enumeration plus the frozen inventory
    n_baiot_20260903T224404Z.json (label_source: Directory and filename; 89
    data files = 9 benign + 45 gafgyt + 35 mirai, 7,062,606 rows; the
    root-level demonstrate_structure.csv is zero-row and receives no label).
    All 11 (source_family, source_subtype) entries carry
    decision_status=proposed, 11 exact / 0 derived: benign_traffic ->
    benign (9 files / 555,932 rows); gafgyt combo/junk/scan/tcp/udp ->
    bashlite (5 subtypes x 9 files); mirai ack/scan/syn/udp/udpplain ->
    mirai (5 subtypes x 7 files). The proposal extends the frozen
    gafgyt->bashlite fixed_decision to the 5 gafgyt subtypes; the
    fixed_decision itself is NOT modified. Mirai entry rationales record
    the CICIoT2023 frozen Mirai category (3 subtypes) as presence-only;
    any cross-dataset mirai family comparison remains conditional on the
    N-BaIoT mapping freeze and a subtype-coverage audit. Device coverage
    disclosure: gafgyt files span 9 devices, mirai files span 7 devices
    (Ennio_Doorbell and Samsung_SNH_1011_N_Webcam have no mirai files).
    The TON-IoT and CICIoT2023 frozen entries are NOT modified. The
    ontology root status and canonical_family.decision_status both remain
    proposed. Nothing is frozen in this record: user verification of the
    v1 proposal evidence package is pending. Data materialization,
    splitting, and training remain forbidden until the N-BaIoT mapping
    freeze and the root-level ontology freeze decision.


    v1 Rev 1, per user verification of the v1 evidence package
    (N_BAIOT_TYPE_MAPPING_EVIDENCE_V1.zip, SHA-256 951b62458350493f
    d01042d9a518a759a09dd8fddb628912180408fc04c7a9e3): the 11 mappings
    passed substantive verification (ZIP hash/size/CRC/permissions,
    in-package tests 85/85, per-entry file and row counts recomputed
    against the frozen inventory, Meidan et al. 2018 pp.4-5 support for
    all ten attack subtypes, Table 3 support for the 7-device Mirai
    coverage, ontology JSON identical to the CICIoT2023 frozen baseline
    apart from the two intended additions, TON-IoT/CICIoT2023/fixed
    decisions untouched, root still proposed, registry 3 source + 7
    panel hashes all matching, published-surface watermark markers
    zero, #20 not existing, materialization/split/training ban intact).
    One documentation-consistency defect was found and is fixed in this
    revision: the `source_subtype` definition section of
    LABEL_ONTOLOGY.md previously cited the family directories as
    `mirai_attacks`/`gafgyt_attacks`, whereas the frozen inventory and
    the mapping keys use `mirai_attacks_extracted`/
    `gafgyt_attacks_extracted`; that section claims the directory names
    are carried verbatim, so the names are corrected to the actual
    directory names and a guard test now locks the definition. Two
    delivery-summary counting corrections are recorded (not package
    defects): MANIFEST verifies 18/18 (19 ordinary files include the
    MANIFEST itself, which by design does not hash itself), and the
    registry carries 3 source entries + 7 panels, not 4 + 7. For the
    future #20 freeze record: Meidan et al. 2018 Table 3 itself shows
    Ennio_Doorbell and Samsung_SNH_1011_N_Webcam without Mirai, so the
    freeze record should state that the paper's general text is
    made concrete by Table 3 and the frozen directories as Mirai 7/9
    devices, rather than registering an unconditional
    paper-vs-data-tree contradiction. No mapping, semantic_disposition,
    evidence, or rationale is changed in this revision; the 11 entries
    remain decision_status=proposed.

20. N-BaIoT family/subtype mapping FROZEN as
    N-BAIOT-TYPE-MAPPING-20260905-V1-FROZEN. Freeze basis: the v1
    evidence package went through user verification in two rounds
    (v1 -> Rev 1). Rev 1 (commit `33b076c`) fixed the `source_subtype`
    definition section directory names (mirai_attacks_extracted /
    gafgyt_attacks_extracted) and added 3 guard tests; counting facts
    (MANIFEST 18/18, registry 3 source entries + 7 panels) and the
    Table 3 wording guidance were recorded in #19 Rev 1. The Rev 1
    evidence ZIP `N_BAIOT_TYPE_MAPPING_EVIDENCE_V1R1.zip` (SHA-256
    `480e15c672d5673f0d4eb82cf9f4da34cf53be9e516737f9981354459b632501`,
    2,531,489 bytes, 31 entries, source commit `33b076c`) passed the
    user's independent verification: ZIP hash/size/CRC/permissions
    (19 files 644 + 12 dirs 755), MANIFEST 18/18 (19 ordinary files
    include the MANIFEST itself, which does not hash itself), in-package
    tests 88/88 (32+23+33), V1 -> V1R1 diff exactly 3 content files,
    ontology JSON byte-identical to the CICIoT2023 freeze baseline apart
    from the two intended additions, registry 3 source + 7 panels
    matching, root still proposed, #20 not existing, materialization/
    split/training ban intact. On explicit user authorization, all 11
    N-BaIoT mapping entries now carry decision_status=frozen: 11 exact /
    0 derived (benign_traffic -> benign, 9 files / 555,932 rows; gafgyt
    combo/junk/scan/tcp/udp -> bashlite, 9 files each; mirai
    ack/scan/syn/udp/udpplain -> mirai, 7 files each; 7,062,606 rows
    total). Mirai coverage is recorded as 7/9 devices: Meidan et al.
    2018 Table 3 and the frozen directory structure make the paper's
    general text concrete as Mirai 7/9 devices, not an unconditional
    paper-vs-data-tree contradiction (Table 3 shows Ennio_Doorbell and
    Samsung_SNH_1011_N_Webcam without Mirai). The freeze changed only
    decision_status values and the description freeze metadata; no
    mapping, semantic_disposition, evidence, or rationale was altered.
    The TON-IoT (10 frozen) and CICIoT2023 (34 frozen) entries and the
    frozen gafgyt->bashlite fixed_decision are NOT modified.
    binary_label.derivation entries and the ontology root status and
    canonical_family.decision_status all remain `proposed`. Data
    materialization, splitting, and training remain forbidden until the
    root-level ontology freeze is complete. Next stage: the root-level
    ontology freeze decision (separate authorization).

    Rev 1, per user re-verification of the FREEZE evidence package
    (N_BAIOT_TYPE_MAPPING_FREEZE_EVIDENCE.zip, SHA-256 bdfe11ade28b
    575be103e958ca00501c11f8bf79a87dd9180abfdb11aa607a12, 2,533,191
    bytes, 31 entries, source commit `a2682f8`; user-verified ZIP
    hash/size/CRC/permissions, MANIFEST 18/18, in-package tests 91/91,
    V1R1 -> FREEZE diff exactly 4 content files, 11/11 mappings
    zero-diff apart from decision_status): the freeze itself is
    confirmed valid and unchanged - all 11 frozen decision_status
    values, the mapping content, semantic dispositions, evidence, and
    rationales are untouched; the ontology root status and
    canonical_family.decision_status remain proposed; the
    materialization/splitting/training ban stays in force. The only
    change in this revision is documentation hygiene: section 5 of
    LABEL_ONTOLOGY.md still opened with the historical proposal-stage
    sentence "The family mapping table is NOT frozen yet.", which
    contradicted the frozen dataset-level tables declared in the same
    section (35 in-package tests had no guard on that sentence, so the
    91/91 pass could not catch it); the sentence is removed and
    replaced with an explicit statement that all three dataset-level
    family mapping tables are frozen while the ontology root status and
    canonical_family.decision_status remain proposed and require a
    separate root-level ontology freeze decision, and a guard test now
    locks the corrected wording. config/label_ontology.json is NOT
    changed in this revision.

21. ROOT-LEVEL ONTOLOGY FREEZE PROPOSED as
    LABEL-ONTOLOGY-ROOT-20260905-V1-PROPOSED. This record is a proposal
    for review only; no status is flipped in this record, and the
    authorization to prepare a proposal explicitly does NOT include
    flipping the ontology root status, canonical_family.decision_status,
    or binary_label.derivation entries. Input state (all machine-verified
    on the proposal commit): the three dataset-level family mapping
    tables are frozen - TON-IoT 10 entries
    (TON-IOT-TYPE-MAPPING-20260904-V1-FROZEN, #16), CICIoT2023 34
    entries (CICIOT2023-TYPE-MAPPING-20260904-V1-FROZEN, #18), N-BaIoT
    11 entries (N-BAIOT-TYPE-MAPPING-20260905-V1-FROZEN, #20, final
    clean evidence N_BAIOT_TYPE_MAPPING_FREEZE_EVIDENCE_V1R1.zip SHA-256
    `1912365fe8a20f478a367dc844f3067c6d7fac176e71a5e9505a21c38fae3d3c`,
    with `a2682f8` as the freeze commit and `b017f8f` as its
    documentation-consistency Rev 1); the gafgyt->bashlite
    fixed_decision is frozen; the three root-level freeze_conditions in
    config/label_ontology.json are all satisfied (TON-IoT type
    inventory, field/statistics review #15, TON-IoT label semantics
    re-verification). PROPOSED FREEZE SCOPE (what a future #22 freeze
    would flip, subject to separate explicit authorization): (a)
    ontology root `status` proposed -> frozen; (b)
    `canonical_family.decision_status` proposed -> frozen; (c) the
    three `binary_label.derivation.*.decision_status` entries proposed
    -> frozen (ton_iot from the label column 0/1, ciciot2023 from the
    category directory name, n_baiot from the file location - all
    exact, all deterministic, each carrying evidence_source). Items
    deliberately OUT OF SCOPE for the ontology root freeze:
    `config/feature_policy.json` (status remains `proposed`; its
    data_handling gates read "forbidden before protocol freeze", so the
    materialization/splitting/training ban is controlled by the
    FEATURE/label protocol freeze chain and is NOT lifted by an
    ontology root freeze alone); the source_subtype verbatim
    definitions (no decision_status axis; they are structural facts);
    grouping_metadata and verified_dataset_facts (facts from frozen
    inventories, not decisions). CONSEQUENCES IF LATER FROZEN: the
    label ontology would be complete and immutable at all levels; any
    change would require a new numbered decision superseding the frozen
    state; per the standing chain, data materialization, splitting, and
    training remain forbidden until the FEATURE protocol freeze
    (feature_policy) completes its own separate decision chain - the
    ontology root freeze alone does not authorize them. Nothing is
    frozen in this record: user review of this proposal is pending.

    Rev 1 (proposal-consistency lock, per user review of the proposal
    evidence package ROOT_ONTOLOGY_FREEZE_PROPOSAL_EVIDENCE_V1.zip,
    SHA-256
    `3da7642fb1a08d7aee987298af01e6bd7eb5b2dbf3b727d05c68c994b14c284a`,
    2,541,134 bytes, 21 files + 12 dirs, MANIFEST 20/20 OK, in-package
    tests 100/100; user independent recursive census of
    config/label_ontology.json: 61 status/decision_status fields =
    56 frozen + exactly 5 proposed). The proposal staging stands;
    nothing is frozen in this revision and config is NOT changed
    (both config files byte-identical to b017f8f/b59082a). This
    revision locks the #22 execution wording so that "exactly" is
    unambiguous: (1) the future #22 freeze is EXACTLY 5 status flips
    (the earlier conversation-level "six statuses" phrasing was an
    arithmetic slip; the package texts enumerate the correct five
    objects), the five proposal-time proposed paths recursively
    enumerated over the whole config: `status` (ontology root),
    `canonical_family.decision_status`,
    `binary_label.derivation.ton_iot.decision_status`,
    `binary_label.derivation.ciciot2023.decision_status`, and
    `binary_label.derivation.n_baiot.decision_status` (56 frozen +
    5 proposed = 61 total, no more, no less); (2) the #22 freeze is
    pre-authorized to update the `canonical_family.note` field from
    the proposal-stage sentence "Final family assignments are NOT
    frozen until the TON-IoT type inventory is complete and official
    documents are reviewed." to the frozen-state sentence "Final
    family assignments are frozen under
    LABEL-ONTOLOGY-ROOT-20260905-V1-FROZEN after completion of the
    required inventory and official-document reviews." - this is
    freeze-state metadata housekeeping only: no family assignment, no
    mapping entry, no rationale, no evidence changes; (3) the
    predetermined freeze id is LABEL-ONTOLOGY-ROOT-20260905-V1-FROZEN;
    (4) the #22 provenance must record at least: the proposal source
    commit `b59082a`, the proposal evidence SHA-256
    `3da7642fb1a08d7aee987298af01e6bd7eb5b2dbf3b727d05c68c994b14c284a`,
    the final N-BaIoT clean freeze evidence SHA-256
    `1912365fe8a20f478a367dc844f3067c6d7fac176e71a5e9505a21c38fae3d3c`,
    and the DECISIONS.md #22 record. A guard test now recursively
    enumerates every status/decision_status field and asserts the
    proposal-time proposed set is exactly those 5 paths. The
    materialization/splitting/training ban is NOT lifted by this
    revision nor by the #22 freeze alone; #22 execution still
    requires separate explicit user authorization.
22. ROOT-LEVEL ONTOLOGY FROZEN as
    LABEL-ONTOLOGY-ROOT-20260905-V1-FROZEN. On explicit user
    authorization following the user's verification of the #21 proposal
    chain (proposal V1 reviewed PASS, Rev 1 reviewed PASS and
    formally authorized to execute #22), the root-level ontology
    freeze is applied. EXACTLY 5 status/decision_status fields were flipped
    proposed -> frozen, matching the Rev 1 locked scope with no
    additional change: `status` (ontology root),
    `canonical_family.decision_status`,
    `binary_label.derivation.ton_iot.decision_status`,
    `binary_label.derivation.ciciot2023.decision_status`, and
    `binary_label.derivation.n_baiot.decision_status`. The
    `canonical_family.note` was updated from the proposal-stage
    sentence to the pre-authorized frozen-state sentence ("Final
    family
    assignments are frozen under
    LABEL-ONTOLOGY-ROOT-20260905-V1-FROZEN after completion of the
    required inventory and official-document reviews.") - freeze-state
    metadata housekeeping only. A machine structural diff of the frozen
    config against its pre-freeze state confirms no change beyond these
    six field edits: no family assignment, no mapping entry, no
    semantic_disposition, no evidence, no rationale, no
    fixed_decisions, no source_subtype/grouping_metadata/
    verified_dataset_facts changes. The three dataset-level tables and
    the gafgyt->bashlite fixed_decision remain frozen with their #16,
    #18, and #20 records unchanged as history. A recursive census of
    every status/decision_status field after the freeze reads 61 frozen
    + 0 proposed. `config/feature_policy.json` remains `proposed` and
    byte-identical to the proposal commit; its data_handling gates read
    "forbidden before protocol freeze", so data materialization,
    splitting, and training remain forbidden - the ban is NOT lifted by
    an ontology root freeze alone and requires the FEATURE/label
    protocol freeze chain to complete its own separate decision
    chain.

    Provenance: proposal source commit `b59082a`;
    proposal evidence SHA-256
    `3da7642fb1a08d7aee987298af01e6bd7eb5b2dbf3b727d05c68c994b14c284a`
    (ROOT_ONTOLOGY_FREEZE_PROPOSAL_EVIDENCE_V1.zip); final
    N-BaIoT clean freeze evidence SHA-256
    `1912365fe8a20f478a367dc844f3067c6d7fac176e71a5e9505a21c38fae3d3c`
    (N_BAIOT_TYPE_MAPPING_FREEZE_EVIDENCE_V1R1.zip, user-verified PASS);
    source commit of the pre-freeze state `3aa8932` (Rev 1
    proposal-consistency lock); frozen
    config/label_ontology.json SHA-256
    `8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab`
    (pre-freeze
    `86cc9a246346f26d414260f9adf56235fca5d6185918ce404a71bea9945db8ee`);
    this DECISIONS.md #22 record.


    Rev 1 (documentation-consistency fix, per user independent
    re-verification of ROOT_ONTOLOGY_FREEZE_EVIDENCE_V1.zip): the user
    confirmed the freeze configuration itself valid (ZIP SHA-256
    `13eb06bb5e8c4b0ae10b84239444ced965e2e13d4fd33ed0d83963614fbde74e`,
    MANIFEST 20/20 OK, in-package tests 110/110 OK, exactly 5 status
    flips + the pre-authorized note update, feature_policy.json
    byte-identical with all three data-handling bans verbatim), and
    identified two stale current-status passages in
    docs/LABEL_ONTOLOGY.md: (1) the canonical_family current-family
    list still read "Current proposed families (14)" and "both pending
    final freeze." - now "Current frozen families (14)" with the
    closing statement that both `spoofing` and `brute_force` are now
    frozen under LABEL-ONTOLOGY-ROOT-20260905-V1-FROZEN (DECISIONS.md
    #22); the 14 family names and their order are untouched; (2) the
    TON-IoT table intro read "The ontology root and
    `canonical_family.decision_status` remain `proposed` until the
    CICIoT2023 and N-BaIoT mappings are also frozen." without a time
    qualifier - now explicitly scoped to the TON-IoT mapping freeze
    time (DECISIONS.md #16) with the subsequent root-level freeze
    (DECISIONS.md #22) stated; the mapping table, rationale, and
    evidence are untouched. This revision changes documentation only:
    no config file, no status field, no mapping, no rationale, no
    evidence, and no ban was altered; config/label_ontology.json stays
    byte-identical to the frozen SHA-256
    `8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab`
    and config/feature_policy.json stays byte-identical to
    `2a903a4a0dd54e4307b7dce24599c39ce62b378b4cd8a95f8a633ffedb321b47`
    (status `proposed`, three "forbidden before protocol freeze" gates
    verbatim). Two guard tests (whitespace-normalized current-status
    wording checks) were added. The materialization/splitting/training
    ban is NOT lifted by this revision; the next stage
    (feature/label protocol freeze proposal) is NOT yet authorized.

23. FEATURE/LABEL PROTOCOL FREEZE PROPOSED as
    FEATURE-POLICY-20260905-V1-PROPOSED. This record is a proposal
    for review only; no status is flipped and no config byte changes
    in this record. The authorization to prepare a proposal explicitly
    does NOT include executing the #24 freeze, changing the live
    config/feature_policy.json, touching the frozen
    config/label_ontology.json, or lifting the
    materialization/splitting/training gates.

    Input state (machine-verified on the proposal commit): the
    label-ontology chain is complete and frozen at all levels (#16,
    #18, #20, #22 with Rev 1; label_ontology.json SHA-256
    `8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab`,
    recursive census 61 frozen + 0 proposed); config/feature_policy.json
    remains `proposed` (SHA-256
    `2a903a4a0dd54e4307b7dce24599c39ce62b378b4cd8a95f8a633ffedb321b47`,
    byte-identical since b017f8f); its data_handling gates read
    "forbidden before protocol freeze" for materialization, splitting,
    and training.

    AUDIT EXCEPTION (one-off, user-authorized 2026-09-05, recorded
    here): a read-only TON-IoT `proto` value census was executed as a
    #23 proposal pre-condition. Scope: read the frozen
    train_test_network.csv (inventory ton_iot_20260903T113048Z, source
    SHA-256
    `26ddc513552de36de6428b2e578efaed2b57504c716dfba847cc0109a64e1974`,
    re-verified before and after the run) and count the raw `proto`
    column values verbatim. No row export, no feature matrix, no
    encoder fitting, no split, no training. Result
    (artifacts/datasets/proto_census/ton_iot_proto_20260905T110840Z.json,
    SHA-256
    `89f06e9c3913e2d429be6021ff42f907727f36e69cebf5bc5639b9793e689830`):
    exactly 3 distinct raw values - tcp 168747, udp 42015, icmp 281;
    zero empty/whitespace/placeholder values, zero field-count
    mismatches; row reconciliation 211043 = 211043 against the frozen
    inventory; both config files verified unchanged during the run.
    This census is AUDIT EVIDENCE ONLY: the observed value set must
    NOT be used as an all-data encoder vocabulary; the standing rule
    (category encoders fitted on the training split only) is
    unchanged, and this census does NOT lift the data-handling gates.

    PROPOSED FREEZE SCOPE (what a future #24 freeze would change,
    subject to separate explicit authorization; frozen
    decision_status means "the review decision of this version is
    locked", NOT that the mapping is admitted):

    (a) Four structured status fields, proposed -> frozen:
        `status` (policy root);
        `semantic_core.candidate_examples[0].decision_status`
        (total_transferred_bytes);
        `semantic_core.candidate_examples[1].decision_status`
        (decayed_window_statistics);
        `semantic_core.review_outcome_2026_09_04.resolved_points[0].
        decision_status` (MI_dir resolution).

        Semantic dispositions stay AS-IS and are NOT flips:
        total_transferred_bytes keeps `unresolved` (not admitted to
        the harmonised core in this version; must not be used as an
        equivalence feature); decayed_window_statistics keeps
        `rejected` (the REJECTION is of the cross-dataset mapping,
        not a deletion of N-BaIoT native features); MI_dir keeps
        `derived` (the existing elimination-based interpretation is
        locked; it must not be re-described as a verbatim official
        definition, and it gains no cross-dataset comparability).

    (b) Evidence completion (additions, not status flips): each of
        the four records above gains an `evidence_source` array
        citing the specific official documents with path, SHA-256,
        and anchor (page/table/section), per the STRICT reading of
        freeze condition 3 ("each mapping's evidence_source cites the
        specific official document"). Internal FIELD_SEMANTICS_REVIEW
        .md may remain in the review chain but does not substitute
        for the official-source citation. For `unresolved` records
        the evidence documents WHAT was consulted and WHICH gate
        stays unconfirmed (no fabricated equivalence support); for
        `rejected` records the evidence documents the rejection
        reason and its applicability scope (this version's released
        CSVs, not a claim about all future versions); for `derived`
        records the evidence supports the derivation and its
        boundaries.

    (c) The two string-embedded candidate records
        (`protocol_indicators`, `packet_count` in
        review_outcome pairwise_cores) get NEW TARGET WORDING that
        separates the historical review state from this version's
        decision:
        - protocol_indicators: after the proto census and the
          seven-gate check, EXACTLY the subset {tcp, udp} is proposed
          for admission as pairwise ton_iot__ciciot2023 mappings
          (both official documents define them as transport-layer
          protocols; 0/1 unit; per-record aggregation; whole-record
          window; directionless; formula reproducible as one-hot of
          proto). icmp stays `unresolved`: TON-IoT officially defines
          proto as "Transport layer protocols of flow connections"
          (Network Features-Description.pdf p.1 row 6) while CICIoT2023
          officially defines ICMP as "the network layer protocol"
          (README.pdf p.1 feature table row 32); value-set coincidence
          does not prove semantic equivalence; not admitted this
          version. The remaining CICIoT2023 protocol columns
          (DHCP/ARP/IGMP/IPv/LLC and the application-layer set) have
          NO proposed TON-IoT counterpart; no correspondence is
          invented to fill the eight columns and no unknown value is
          interpreted as all-zero indicators.
        - packet_count: stays `unresolved` (connection vs flow
          aggregation object still unconfirmed); not admitted this
          version.
        If #24 later converts these into structured mapping records,
        the final status-path enumeration MUST be re-derived from the
        resulting config; the "four structured fields" list applies to
        the current schema only.

    (d) Data-handling gate target values (to take effect ONLY at
        #24, under its own separate authorization, and only after the
        #24 changes land): materialization/splitting/training each
        change from "forbidden before protocol freeze" to
        "permitted after protocol freeze (#24), subject to the
        label-ontology chain, the feature/label protocol freeze, and
        the standing experimental discipline (no split changes after
        formal experiments start; encoder fitting on the training
        split only; deterministic rotation and order-invariance
        gates)". Each gate change is individually authorized at #24;
        the proposal does not bundle them, and the gates stay
        forbidden until then.

    Items deliberately OUT OF SCOPE for #24:
    config/label_ontology.json (frozen, byte-identical); the frozen
    dataset-level mapping tables and fixed_decisions; the semantic
    dispositions (exact/derived/unresolved/rejected axis); the
    audit_gates, mapping_record_fields, and policy texts
    (direction/paper_positioning/empty-core honesty); the proto
    census artifacts (audit evidence, immutable);
    ton_iot_exclusions and primary_native_feature_sets (native sets
    are unchanged by the freeze - only status and evidence fields
    change).

    PROPOSED FREEZE ID: FEATURE-POLICY-20260905-V1-FROZEN (to be
    applied by #24 only on explicit user authorization after this
    proposal's evidence package passes user verification).

    Nothing is frozen in this record: user review of this proposal is
    pending. The materialization/splitting/training ban is NOT
    lifted, and #24 execution requires separate explicit
    authorization.

    Rev 1 (2026-09-05, zero-admission documentation revision), per
    user independent verification of the V1 evidence package
    FEATURE_PROTOCOL_FREEZE_PROPOSAL_EVIDENCE_V1.zip (SHA-256
    `0e66ffb8537e08d6cba28092a6da92f1d2ef924727baff862a898330c63f3fc1`,
    2,554,527 bytes, 40 zip entries = 26 files + 14 directories),
    delivered with the review package
    FEATURE_PROTOCOL_23_INDEPENDENT_REVIEW.zip (SHA-256
    `1fdee7efa3ab11dc528c04c8e303086d0d45b69a5e26b310fae4abb46da8af6b`):
    package integrity PASS (MANIFEST 25/25 files, in-package tests
    46/46 under the reviewer's independent Python 3.13.5), with three
    findings addressed by this revision. The V1 record above is
    retained as the historical staging record; where the V1 item-3
    admission wording conflicts with this revision, this revision
    supersedes it:

    (a) F23-01 - admission withdrawn to ZERO. The official
        CICIoT2023 README.pdf page 1 embeds TWO feature tables with
        conflicting protocol semantics: a 47-row indicator-style
        table (TCP/UDP rows 28-29 "Indicates if the transport layer
        protocol is TCP/UDP"; ICMP row 32 "Indicates if the network
        layer protocol is ICMP"; Tot sum row 35 "Summation of
        packets lengths in flow") and a 39-row window-aggregation
        table (TCP/UDP/ICMP rows 23-27 "Average no. of ... packets
        in the window"; Tot Sum row 30 "Total packet length within
        the aggregated packets (window)"; six byte-identical
        embedded copies). Both tables are archived under
        references/dataset_docs/ciciot2023/readme_p1_feature_table/
        (readme_p1_feature_table_47row.png SHA-256 `6327fa2b...037902`,
        readme_p1_window_table_39row.png SHA-256 `cc88ca2f...8a1ad`)
        and registered in registry.json as an official-source
        internal inconsistency; the page does not state which table
        describes the released 39-column CSV. Gates 3/4 are
        therefore unverifiable for the protocol columns and gate 7
        is unsatisfied this version; "per-record aggregation" /
        "whole-record window" is container wording and does not
        prove the aggregation object or the time window.
        protocol_indicators is DEMOTED to candidate retention and
        this version admits NOTHING into any cross-dataset core:
        the three-way core and every pairwise core are EMPTY
        (admitted_mapping_count = 0), dataset-native is the
        mainline, and the empty pairwise core is reported honestly.
        ICMP exclusion reasoning is corrected: the
        transport-vs-network-layer wording difference is NOT a
        sufficient exclusion proof (the same Zeek conn.log
        documentation describes proto as the transport layer while
        explicitly covering ICMP); the corrected disposition is
        "current evidence insufficient; not admitted this version".
        No ICMP sample (281 rows) and no native proto feature is
        deleted, and the TON-IoT census stays untouched. In the #24
        draft targets protocol_indicators carries
        semantic_disposition=unresolved (NOT derived - the V1
        admission claim is withdrawn, so "derived" no longer holds)
        with decision_status=proposed.

    (b) F23-02 - an independent ready-to-effect draft is added at
        artifacts/proposals/feature_policy_freeze_draft_v1r1.json
        (it touches neither live config): exactly 4 status flips
        (policy root `status`, both candidate_examples
        decision_status fields, the MI_dir resolved point) to
        `frozen` at #24; per-record evidence attribution for ALL
        SIX affected records (the 4 structured fields,
        protocol_indicators, packet_count); the complete target
        wording for the two string-embedded candidates;
        structured-vs-string decided NOW (the two candidates stay
        string-embedded this version, so #24 has no open design
        choice); the three data-handling gate targets each with one
        unique target value, authorization basis, and pre-condition;
        freeze ID FEATURE-POLICY-20260905-V1-FROZEN with
        provenance. Guard tests verify the draft's actual admission
        set (zero admissions, empty cores), not its note text.

    (c) F23-03 - audit tooling archived: the v1 census script is
        stored as scripts/audits/ton_iot_proto_census_v1.py
        (SHA-256
        `98cb29423e5ba5f1fa9880aea83604cff94760e8ada91bad347c5671cad496cc`)
        and the v2 source as
        scripts/audits/ton_iot_proto_census_v2.py (SHA-256
        `490495d9f569de2db541a059b412e6022fd30782e7f166dab72a48bcf210d787`).
        The user authorized ONE additional read-only verification
        pass over the SAME frozen CSV: new timestamped artifacts
        artifacts/datasets/proto_census/
        ton_iot_proto_v2_20260905T121644Z.json (SHA-256
        `dfffd40c42fea9608679257c3c4a6014e42bbb7029b6849c6e5a0a4cde9f44b7`)
        and .log (SHA-256
        `aa45633f063584af2d3e865191488e476d043074108c837a64129815b301fbfd`),
        with explicit before/after source hashes (both equal to the
        frozen inventory value `26ddc513...e1974`); no old artifact
        or log was modified, and nothing is back-filled into old
        logs. v2 reproduces v1 exactly: tcp 168747 / udp 42015 /
        icmp 281, rows 211043 = 211043, zero anomalies,
        counts_identical_to_v1 = true, exit_status OK.

    (d) Dual-axis wording fix (same-round documentation
        consistency): FEATURE_MAPPING_PROTOCOL.md now records
        semantic_disposition (exact / derived / unresolved /
        rejected) and decision_status (proposed / frozen) as TWO
        independent axes in the section 3 audit-record field list
        and the section 5 freeze condition; frozen locks the
        recorded disposition and NEVER converts unresolved/rejected
        into admitted mappings. No #15 historical review fact is
        changed. Section 6 gains a 6.1 Rev 1 staging addendum
        recording all of the above.

    Rev 1 scope: documentation and audit-evidence additions ONLY
    (DECISIONS.md, FEATURE_MAPPING_PROTOCOL.md, the draft JSON,
    registry.json page-1 table entries, the v2 census artifacts and
    archived scripts, guard-test updates). Both config files stay
    byte-identical (`2a903a4a...21b47` / `8a055e2e...6fab`);
    nothing is frozen; the materialization/splitting/training ban
    is NOT lifted; #24 execution still requires separate explicit
    user authorization.
    Rev 2 (2026-09-05, target-configuration revision closing F23-02),
    per user independent review of the V1R1 evidence package
    FEATURE_PROTOCOL_FREEZE_PROPOSAL_EVIDENCE_V1R1.zip (SHA-256
    `1c94c84f8f1b3d13aa09aab7674e5dba37a619aa7d8ae2d3a0ff06e5c7403de8`,
    3,226,214 bytes, 51 entries = 33 files + 18 directories; package
    integrity PASS, in-package tests 62/62, both live configs
    verified byte-identical; F23-01 and F23-03 CLOSED; F23-02
    remained open), delivered with the review package
    FEATURE_PROTOCOL_23_REV1_INDEPENDENT_REVIEW.zip (SHA-256
    `c81666ef904f099a03ef840960e7a3567268da9738eeb4681e5a777940641efd`).
    The V1 and Rev 1 records above remain the historical staging
    records; where they conflict with this revision, this revision
    supersedes them. F23-02 is closed in three parts matching the
    review's block categories:

    (a) Category A (binding-point determinism) - the deliverable is
        now a committed COMPLETE would-be-effective target
        configuration, not a change plan:
        artifacts/proposals/feature_policy_freeze_target_v1r2.json
        (SHA-256
        `e81a55c16f9439b0356295353e8b342de19d5c5606d868952592f913beda714b`),
        generated deterministically from the live baseline bytes
        (`2a903a4a...21b47`) by text-level replacements only, with
        the generator archived as
        scripts/audits/build_feature_policy_target_v1r2.py
        (SHA-256
        `19e0de8b5092772d6aec650c1f87a8b86d0dd6ad713e6dafcd76c76c49f2353d`).
        admission_set_this_version and freeze_metadata are bound
        verbatim as two new root keys of the target config; the
        accompanying specification artifacts/proposals/
        feature_policy_freeze_target_spec_v1r2.json (SHA-256
        `0fa8da404f78ed9b8258f3f4e35df64750ba86aa3f2bbe5cceeab0bb287af150`)
        declares the bindings (target_config_state.bindings,
        not_left_to_24 = true) and fixes the application
        preconditions and method (baseline re-verify -> byte
        install -> hash record -> verification green). Nothing is
        left for the applier to choose.

    (b) Category B (MI_dir consistency) - in the target config the
        MI_dir resolved point's evidence_source becomes an ARRAY:
        element [0] is the existing string BYTE-EQUAL (not merely a
        prefix); element [1] adds the Meidan Table 2 / 'Feature
        extraction' section anchor; element [2] adds the UCI page
        variable-information anchor; the resolution text is
        unchanged. The Rev 1 draft's internally inconsistent
        action / existing_value_kept / target_value trio is
        corrected in the Rev 2 specification: the array choice is
        confirmed, the keep-claim is scoped to element [0] exactly,
        and the spec target_value equals the committed target
        array.

    (c) Category C (guards over the applied result) - the archived
        verifier scripts/audits/verify_feature_policy_target_v1r2.py
        (SHA-256
        `53c0b9233b11131a983b30506766877849936efea25f1b0b0ffa0f2f0d5562ef`)
        applies the seven text-level operations to the baseline in
        memory, byte-compares the result against the committed
        target artifact, and runs 30 checks, all green: EXACTLY 4
        structured status flips (recursive census after
        application: 4 frozen, 0 proposed, nothing else);
        semantic_dispositions unchanged (unresolved / rejected /
        derived); MI_dir type str -> list with element [0]
        byte-equal; zero actual admissions (admitted_mapping_count
        = 0, every core EMPTY); the two protocol strings reworded
        (unresolved/proposed, no "derived" wording, no new
        structured status fields); gate objects with 6 standalone
        structured preconditions each (no authorization fallback);
        unique binding points; leaf-level added/changed/removed
        accounting with zero unexpected changes. Artifacts:
        artifacts/proposals/feature_policy_target_v1r2_diff.json
        (SHA-256
        `8d52dc0066a26b8007536ca65b28f45708a095014530b2286596701ec1c77e60`)
        and feature_policy_target_v1r2_verify.log (SHA-256
        `ef300f2a9d9ee5c47534c85f1e45b67514d14f7068248bc886f1cc5bf5f9cf84`).
        Guard tests now SIMULATE the application and assert the
        resulting configuration (Rev 2 test classes), and the Rev 1
        authorization-fallback assertion is removed.

    Non-blocking same-round fix: the FEATURE_MAPPING_PROTOCOL.md V1
    historical sentence truncated by the Rev 1 section 6.1
    insertion is restored ("...that requires #24 and its own
    authorization.").

    Rev 2 scope: proposal artifacts, archived scripts, guard tests,
    and documentation ONLY. Both live config files stay
    byte-identical (`2a903a4a...21b47` / `8a055e2e...6fab`); the
    target bytes are a PROPOSAL artifact and are NOT installed;
    nothing is frozen; the materialization/splitting/training ban
    is NOT lifted; #24 execution still requires separate explicit
    user authorization.

    Rev 3 (2026-09-06, post-install verification remediation; final
    part of F23-02), per user independent review of the V1R2
    evidence package FEATURE_PROTOCOL_FREEZE_PROPOSAL_EVIDENCE_V1R2.zip
    (SHA-256
    `6319b1be2fd65f73d81121f02687c127315e89653399d031a7673ae4a982b77c`,
    3,263,669 bytes, 57 entries = 39 files + 18 directories; package
    integrity PASS, in-package tests 79/79, deterministic replay
    byte-identical, both live configs verified byte-identical; the
    target configuration content, field bindings, MI_dir rules, zero
    admissions, and generator replay all PASSED), delivered with the
    review package FEATURE_PROTOCOL_23_REV2_INDEPENDENT_REVIEW.zip
    (SHA-256
    `b5b4bdeb9e57951f4090e9ab9d07956d820d02b9291723f319ed54dd0e1dd11e`).
    The review's single blocking finding: the Rev 2 specification's
    step 4 ("run verify_feature_policy_target_v1r2.py against the
    applied file") is not executable - that verifier hardcodes the
    live config/feature_policy.json as the OLD baseline and re-applies
    the baseline-to-target text replacements, so once the target
    bytes are installed it fails (independently reproduced in an
    isolated copy: "op op7_root_additions: anchor count 0 != 1").
    This is a verification-phase/input-path defect only; the target
    bytes, both live configs, the census artifacts, and all accepted
    semantic decisions are UNCHANGED.

    Rev 3 fix (exactly the authorized scope - verifier/procedure/
    tests and consequent hash references; the target JSON is NOT
    regenerated):

    (a) New post-install verification entry point
        scripts/audits/verify_installed_feature_policy_v1r3.py
        (SHA-256 recorded in the V1R3 evidence package). It keeps
        three strictly distinct inputs per the review: --baseline
        (a PRESERVED snapshot of the old 2a903a4a... file), --target
        (the immutable committed artifact e81a55c1...714b, byte-
        compared, never rebuilt), and --applied (the ACTUAL installed
        file), plus --label-ontology (8a055e2e...) and --spec. It
        never re-applies baseline-to-target replacements; it
        byte-compares the installed file against the pinned target,
        then inspects the applied state (4 frozen flips, ontology 61
        frozen, dispositions unchanged, MI_dir array with element [0]
        byte-equal, zero admissions, spec bindings verbatim, gate
        objects fail-closed with 6 preconditions and separate
        authorization). 32 checks; exit 0 = installed bytes/state
        verified and NOT execution authorization; run is read-only
        (all inputs re-read and compared unchanged at exit).

    (b) The specification's target_config_state.application field
        now prescribes the two-phase procedure: PRE-INSTALL (live
        config still hashes to 2a903a4a...): re-verify baseline
        hashes, then run the Rev 2 pre-install verifier (30 checks)
        - which must never be invoked after installation; INSTALL:
        install the target bytes verbatim and re-hash (must equal
        e81a55c1...714b); POST-INSTALL: run the new entry point
        against the actual installed file. Only the application
        string changed in the spec (one JSON line; git diff
        verified); the spec SHA therefore moves to
        `5746dde431fcce1557cc46d5ae6b810310a3f1276e9e1e5e7e279949e881844d`.

    (c) Guard tests extend 52 -> 58 in the #23 module (full suite
        218): the new Rev3PostInstallVerificationTests class ACTUALLY
        INVOKES the post-install CLI as a subprocess against a real
        temporary installed path - correctly installed target passes
        (all_pass, no failures, no authorization granted); the
        uninstalled baseline is rejected; tampered admission count,
        tampered MI_dir element [0], and a removed gate authorization
        precondition are each rejected with nonzero exit; and the
        class documents WHY the phase split exists by asserting the
        Rev 2 pre-install verifier FAILS on an installed config in an
        isolated temporary copy.

    Rev 3 scope: the new post-install verifier script, the spec
    application-field revision, guard tests, and documentation ONLY.
    The Rev 2 target bytes (e81a55c1...714b) are NOT modified, the
    pre-install generator/verifier are NOT modified, both live config
    files stay byte-identical (`2a903a4a...21b47` / `8a055e2e...6fab`),
    the target bytes are NOT installed, nothing is frozen, and the
    materialization/splitting/training ban is NOT lifted; #24
    execution still requires separate explicit user authorization.
