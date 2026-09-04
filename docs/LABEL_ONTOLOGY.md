---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: 'acaaab64-aa12-45b1-8ad8-f9f4cb752cae'
  PropagateID: 'acaaab64-aa12-45b1-8ad8-f9f4cb752cae'
  ReservedCode1: '74a4c94a-dd80-48d4-9135-5bf16d2c7e4a'
  ReservedCode2: '74a4c94a-dd80-48d4-9135-5bf16d2c7e4a'
---

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
Current proposed families (12): `benign`, `backdoor`, `bashlite`,
`ddos`, `dos`, `injection`, `mirai`, `password`, `ransomware`,
`recon`, `web_attack`, `mitm`.

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
`TON-IOT-TYPE-MAPPING-20260904-V1-FROZEN`. The ontology-level
mappings for CICIoT2023 and N-BaIoT remain `proposed` until their own
mapping stages complete; the ontology root status therefore remains
`proposed`.

Data materialization, splitting, and training remain forbidden.

> AI生成