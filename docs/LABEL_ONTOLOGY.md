# Label ontology

This document defines the label schema shared by all three datasets
(TON-IoT, CICIoT2023, N-BaIoT). It is derived only from the three frozen
inventory manifests; no preprocessing, splitting, or training has occurred.
All mappings listed here carry status `proposed` until the official field
definitions have been reviewed and the TON-IoT `type` value inventory is
complete (see "Freeze conditions").

## 1. Three-layer label schema

### `binary_label` — the only mandatory cross-dataset label

Values: `benign` / `attack`.

- This is the single label that is comparable across all three datasets and
  the only label permitted in cross-dataset comparison and transfer claims.
- Derivation per dataset (all derivations deterministic, no inference):
  - TON-IoT: from the `label` column (`0` -> `benign`, `1` -> `attack`),
    with the official label semantics verified against the dataset
    documentation before freeze.
  - CICIoT2023: from the category directory name. `Benign_Final` ->
    `benign`; all other 33 categories -> `attack`.
  - N-BaIoT: from the file location. `<device>/benign_traffic.csv` ->
    `benign`; files under `<device>/gafgyt_attacks_extracted/` and
    `<device>/mirai_attacks_extracted/` -> `attack`. The root-level
    `demonstrate_structure.csv` is a zero-row structure example and is
    never assigned any label because it never enters any data pipeline
    (see section 4).

### `canonical_family` — conservative standardized family

Used for within-dataset multiclass tasks and for comparisons between
datasets that genuinely share a family. Absent families are recorded as
`not_available`:

- `not_available` is a statement about coverage, not a negative class.
- `not_available` rows must never be treated as negatives, and families
  must never be forced into an `other` bucket for the sake of alignment.
Current proposed families (14): `benign`, `backdoor`, `bashlite`,
`brute_force`, `ddos`, `dos`, `injection`, `mirai`, `password`,
`ransomware`, `recon`, `web_attack`, `mitm`, `spoofing`. (`spoofing`
proposed by the CICIoT2023 v1 mapping; `brute_force` adopted at v2
per user verification — both pending final freeze.)

Fixed decisions already made:

- `source_family = gafgyt` maps to `canonical_family = bashlite`
  (semantic_disposition = exact, decision_status = frozen).
  Evidence: Meidan et al. 2018, p.4: "BASHLITE (also known as Gafgyt,
  Q-Bot, Torlus, Lizard-Stresser, and Lizkebab)". The subtypes
  `combo/junk/scan/tcp/udp` stay as `source_subtype`.
- Gafgyt `tcp/udp` subtypes are NOT re-labelled as `ddos`, and Gafgyt
  `scan` is NOT merged into `recon`: malware family and behavior type
  are different ontological axes. A separate `behavior_tag` may be added
  later if evidence supports it, but it will never replace
  `canonical_family`.

### TON-IoT type → canonical_family mapping table (FROZEN)

Frozen as `TON-IOT-TYPE-MAPPING-20260904-V1-FROZEN`: all 10 entries
carry `decision_status = frozen` (frozen from evidence v3 ZIP
SHA-256 `f774457585db719bc223a89cc965aabef7019bec1f0f6209a0ce160e3a4e
ecc4`, source commit `b95e7bc`). No mapping, semantic_disposition,
evidence, or rationale was changed by the freeze. The ontology root
and `canonical_family.decision_status` remain `proposed` until the
CICIoT2023 and N-BaIoT mappings are also frozen.

| source_type | canonical_family | semantic_disposition | rationale |
|---|---|---|---|
| `normal` | `benign` | exact | Coverage invariant: all label=0 rows have type=normal and vice versa (census confirmed zero exceptions). Not one of the 9 attack classes. |
| `backdoor` | `backdoor` | exact | Identity-preserving mapping: the official TON-IoT source label is retained without semantic broadening. Detailed attack mechanisms are not inferred from the selected dataset documentation. |
| `ddos` | `ddos` | exact | Identity-preserving mapping. CICIoT2023 also carries a DDoS category; candidate for cross-dataset family comparison, subject to separate CICIoT2023 mapping freeze and subtype-coverage audit. |
| `dos` | `dos` | exact | Identity-preserving mapping. CICIoT2023 also carries a DoS category; candidate for cross-dataset family comparison, subject to separate CICIoT2023 mapping freeze and subtype-coverage audit. |
| `injection` | `injection` | exact | Identity-preserving mapping: the official TON-IoT source label is retained without semantic broadening. Detailed attack mechanisms are not inferred from the selected dataset documentation. |
| `password` | `password` | exact | Identity-preserving mapping. CICIoT2023 carries a BruteForce category; candidate for cross-dataset family comparison, subject to separate CICIoT2023 mapping freeze and subtype-coverage audit. |
| `ransomware` | `ransomware` | exact | Identity-preserving mapping: the official TON-IoT source label is retained without semantic broadening. Detailed attack mechanisms are not inferred from the selected dataset documentation. |
| `scanning` | `recon` | derived | Scanning maps to recon (source_type name differs from canonical_family name). The UNB CICIoT2023 official taxonomy (https://www.unb.ca/cic/datasets/iotdataset-2023.html) places Port/OS/Vulnerability Scan under Recon. Does NOT merge Gafgyt scan into recon (different axis). Candidate for cross-dataset family comparison, subject to separate CICIoT2023 mapping freeze and subtype-coverage audit. |
| `xss` | `web_attack` | derived | XSS maps to web_attack (specific to broader family). The UNB CICIoT2023 official taxonomy (https://www.unb.ca/cic/datasets/iotdataset-2023.html) places XSS under the Web-based category. Candidate for cross-dataset family comparison, subject to separate CICIoT2023 mapping freeze and subtype-coverage audit. |
| `mitm` | `mitm` | exact | Identity-preserving mapping. 1,043 rows (natural imbalance, not error). CICIoT2023 carries a MITM-ArpSpoofing source subtype, but its official taxonomy places ARP spoofing under Spoofing; no cross-dataset MITM comparison until the CICIoT2023 mapping freeze. |

Coverage invariant: `normal → benign` must hold for all rows. Evidence:
TON-IoT label census (`TON-IOT-LABEL-CENSUS-20260903-V1-VERIFIED`):
50,000 label=0 rows all have type=normal; 161,043 label=1 rows all
have type in {backdoor, ddos, dos, injection, password, ransomware,
scanning, xss, mitm}; zero exceptions.

### CICIoT2023 category → canonical_family mapping table (FROZEN)

Frozen as `CICIOT2023-TYPE-MAPPING-20260904-V1-FROZEN` (per
DECISIONS.md #18, on explicit user authorization after V2R2
verification): all 34 entries carry `decision_status = frozen`,
**34 exact / 0 derived**. Frozen from evidence V2R2 ZIP SHA-256
`f8529ea2c721057ce205b862ff37bb3a4cbcb1c8d5524d30cc0b28f93f3d447b`,
source commit `93e8350`. The freeze changed only decision_status
values and the description freeze metadata; no mapping,
official_category, semantic_disposition, evidence, or rationale was
altered. Evidence basis: the
official `README.pdf` (SHA-256 `0f48daba395be03985f612ce706d33f1a25e4008cb94c3ad7b6f6332fbd
bee92`) page-2 "Attacks Executed" classification table (7 category
panels visually extracted, archived under
`references/dataset_docs/ciciot2023/readme_p2_panels/` with SHA-256
in `registry.json`) plus frozen inventory `ciciot2023_20260903T142539Z.json`
(`label_source: Directory and filename`; the frozen CSVs carry no
label column, so the directory name is the sole label carrier) plus
the official UNB page snapshot `unb_iotdataset_page_2026-09-04.html`
(SHA-256 `99ae08c233d26aaa1c6cc5baa9eb6860587077cc2bc1097c63457bface422852`).

User verification of v1 (four adjudications, DECISIONS.md #17):

1. **`spoofing` family accepted** (UNB places ARP/DNS spoofing under
   Spoofing).
2. **`MITM-ArpSpoofing → spoofing` accepted, exact** (official
   category axis; directory name retained verbatim as
   `source_subtype`). Consequence: the TON-IoT `mitm` family has no
   CICIoT2023 member; the deferred cross-dataset MITM comparison is
   not established.
3. **`DictionaryBruteForce → password` REJECTED**; v2 adopts a
   separate `brute_force` family (exact on the official category
   axis), candidate_families 13 → 14. Explicitly recorded:
   **TON-IoT `password` ≠ CICIoT2023 `brute_force`** — insufficient
   evidence for a cross-dataset comparison; the comparison-candidate
   phrase in the frozen TON-IoT `password` rationale predates this
   decision and is NOT established (superseded by DECISIONS.md #17).
4. **`Backdoor_Malware → web_attack` accepted, exact** (UNB places
   Backdoor malware under Web-based).

Official-source inconsistency disclosure: the UNB page states 33
attacks but its own category detail lists enumerate only 32 (the
DDoS list omits `DDoS-ICMP_Fragmentation`); the frozen dataset
directories and README.pdf both contain it, so the formal
enumeration baseline is the **frozen inventory directories plus
README.pdf**, not the UNB page detail lists.

Naming reconciliation: normalization covers case, spacing,
underscores and hyphens; the README lists the single attack name
`Dictionary Brute Force` (one name rendered across three lines
by the PDF page layout), carried by the single
`DictionaryBruteForce` directory; `VulnerabilityScan` lacks the
`Recon-` prefix but its official category is Recon;
`Backdoor_Malware`'s directory name conflicts with its official
Web-based category.

| source_type (directory name, verbatim) | official_category | canonical_family | semantic_disposition | rationale (abridged; full text in config) |
|---|---|---|---|---|
| `Benign_Final` | benign | `benign` | exact | Official benign directory; coverage invariant: the only benign source, 4 files / 1,098,191 rows matching DECISIONS.md #12. |
| `DDoS-ACK_Fragmentation` … `DDoS-UDP_Fragmentation` (12 entries) | DDoS | `ddos` | exact | Official DDoS category → normalized `ddos`. |
| `DoS-HTTP_Flood`, `DoS-SYN_Flood`, `DoS-TCP_Flood`, `DoS-UDP_Flood` | DoS | `dos` | exact | Official DoS category → normalized `dos`. DoS-UDP_Flood rationale records the 3 registered truncated-line exceptions (DoS-UDP_Flood7/8/9) as row-count-only, not label-relevant. |
| `Recon-HostDiscovery`, `Recon-OSScan`, `Recon-PingSweep`, `Recon-PortScan` | Recon | `recon` | exact | Official Recon category → normalized `recon`. |
| `VulnerabilityScan` | Recon | `recon` | exact | Official Recon category; disclosure: no `Recon-` prefix in the directory name; category axis governs. |
| `SqlInjection`, `CommandInjection`, `Uploading_Attack`, `XSS`, `BrowserHijacking` | Web-based | `web_attack` | exact | Official Web-based category → normalized `web_attack`. |
| `Backdoor_Malware` | Web-based | `web_attack` | exact | Official Web-based category; disclosure: directory name contains `Backdoor`, mapping targets `web_attack` NOT `backdoor`; category axis takes precedence. |
| `DictionaryBruteForce` | Brute Force | `brute_force` | exact | v2 (v1's password path REJECTED): separate brute_force family, exact on the official category axis. TON-IoT password ≠ CICIoT2023 brute_force recorded; comparison candidate in the frozen TON-IoT password rationale superseded by DECISIONS.md #17, NOT established. |
| `DNS_Spoofing`, `MITM-ArpSpoofing` | Spoofing | `spoofing` | exact | Official Spoofing category → new normalized `spoofing` family. MITM-ArpSpoofing disclosure: `MITM-` prefix vs official Spoofing category; spoofing selected, mitm alternative considered and rejected under DECISIONS.md #17; consequence: TON-IoT mitm has no CICIoT2023 member. |
| `Mirai-greeth_flood`, `Mirai-greip_flood`, `Mirai-udpplain` | Mirai | `mirai` | exact | Official Mirai category; `mirai` keeps the botnet-malware name; family presence in N-BaIoT (mirai_attacks_extracted/) recorded as presence only, subject to separate freezes. |

v2 evidence-package revision (Rev 1): injected watermark
artifacts stripped from this file and DECISIONS.md; the Brute Force README item
corrected to the single attack name `Dictionary Brute Force`
(rendered across three lines by the PDF page layout, not two
names); the
`MITM-ArpSpoofing` mitm alternative now recorded as considered and
rejected under DECISIONS.md #17 (not open); the seven README.pdf
page-2 panel PNGs now carry SHA-256 entries in `registry.json`. The
v2 mapping remains entirely `proposed`; nothing is frozen in this
revision.

v2 Rev 2 (commit `93e8350`): pure-copy revision - the line-count
wording corrected to "rendered across three lines by the PDF page
layout" (the panel PNG shows Dictionary / Brute / Force on three
lines); no other change.

Freeze (DECISIONS.md #18, on explicit user authorization after V2R2
user verification): all 34 entries now carry `decision_status =
frozen` as `CICIOT2023-TYPE-MAPPING-20260904-V1-FROZEN`; only
decision_status values and the description freeze metadata changed.

Coverage invariant: `Benign_Final → benign` as the only benign
source; all 33 attack directories map to attack families; the
34 directory names each appear exactly once. Cross-dataset family
comparison claims remain conditional on the other mapping freezes
and subtype-coverage audits.

### `source_subtype` — official original label, verbatim

- TON-IoT: the `type` column value, verbatim.
- CICIoT2023: the category directory name, verbatim (34 values).
- N-BaIoT: the family directory (`mirai_attacks`/`gafgyt_attacks`) plus
  CSV filename (e.g. `ack`, `combo`, `scan`), verbatim, stored separately
  (`source_family` and `source_subtype`).

`source_subtype` is never a cross-dataset unified task.

## 2. Grouping metadata — never model input

The following columns are carried for provenance and for group-aware
splits. They must never enter model features:

- `dataset_id`
- `device_id` (N-BaIoT only; also derivable from path for N-BaIoT)
- `capture_id` (CICIoT2023: derived from the filename stem, e.g.
  `DDoS-ACK_Fragmentation12`; N-BaIoT: the device + family + subtype
  triple; TON-IoT: not available in the selected train_test_network.csv)
- `source_file` (relative path of the CSV within the extracted tree)
- `source_row` (1-based data row index within the source file, excluding
  header)

IP addresses, device identifiers, file names, and capture identifiers may
be used to construct group-aware splits, but never as model features.

## 3. Verified dataset facts (from frozen inventories)

- TON-IoT: 1 CSV, 211,043 rows, 44 columns, label carried in `label`
  (0/1) + `type` (attack subtype string).
- CICIoT2023: 309 CSVs, 46,776,700 raw rows across 34 category
  directories; attack rows 45,678,509, benign rows 1,098,191. Three
  truncated final lines (one each in `DoS-UDP_Flood7/8/9.pcap.csv`) are
  registered quality exceptions; after deterministic exclusion:
  45,678,506 attack + 1,098,191 benign = 46,776,697 rows. Two distinct
  ratios must not be conflated: the binary attack:benign ratio is
  45,678,509 / 1,098,191 ≈ 41.594:1, while the largest/smallest source
  class ratio is DDoS-ICMP_Flood (7,200,501 rows) vs Uploading_Attack
  (1,252 rows) ≈ 5,751.2:1.
- N-BaIoT: 90 CSVs = 89 data files (9 benign + 45 gafgyt + 35 mirai) +
  1 zero-row `demonstrate_structure.csv`; 7,062,606 rows, 115 columns,
  one identical header across all files, 0 malformed rows.

## 4. Special-case files

- `demonstrate_structure.csv` sits at the ROOT of the N-BaIoT extracted
  tree (not inside any device directory). It contains 1,776 bytes of
  header only, zero data rows. It is retained in the frozen inventory as
  shipped, but it never enters training, evaluation, or any label
  assignment.
- The three CICIoT2023 truncated lines are excluded by their registered
  file and row positions (quality-exception manifest); the raw CSVs stay
  unchanged.

## 5. Freeze conditions

The family mapping table is NOT frozen yet. Before freezing
`canonical_family` assignments:

1. ~~Complete the TON-IoT `type` unique-value inventory~~ DONE:
   `TON-IOT-LABEL-CENSUS-20260903-V1-VERIFIED`.
2. ~~Review the official field/statistics documents of all three
   datasets~~ DONE: `FIELD-SEMANTICS-REVIEW-20260904-V1-FROZEN`.
3. ~~Re-verify the TON-IoT `label` semantics against the official
   description~~ DONE: Network Features-Description.pdf row 45 confirms
   0=normal, 1=attacks.

All three freeze conditions are satisfied. The TON-IoT type
→ canonical_family mapping table in section 1 is frozen as
`TON-IOT-TYPE-MAPPING-20260904-V1-FROZEN`. The CICIoT2023 category →
canonical_family mapping table in section 1 is frozen as
`CICIOT2023-TYPE-MAPPING-20260904-V1-FROZEN` (DECISIONS.md #18). The
N-BaIoT mapping remains `proposed` until its own mapping stage
completes; the ontology root status therefore remains `proposed`.

Data materialization, splitting, and training remain forbidden.
