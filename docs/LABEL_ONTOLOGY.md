---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: 'e53655da-1cf4-46a9-9572-4c8e5bf653bf'
  PropagateID: 'e53655da-1cf4-46a9-9572-4c8e5bf653bf'
  ReservedCode1: 'e0957560-3135-4338-9c01-dadc0027f458'
  ReservedCode2: 'e0957560-3135-4338-9c01-dadc0027f458'
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

Current proposed families (to be finalized after the TON-IoT `type`
inventory): `benign`, `ddos`, `dos`, `mirai`, `recon`, `bashlite`,
`web_attack`, and others as the TON-IoT inventory requires.

Fixed decisions already made:

- `source_family = gafgyt` maps to `canonical_family = bashlite`. The
  subtypes `combo/junk/scan/tcp/udp` stay as `source_subtype`.
- Gafgyt `tcp/udp` subtypes are NOT re-labelled as `ddos`, and Gafgyt
  `scan` is NOT merged into `recon`: malware family and behavior type are
  different ontological axes. A separate `behavior_tag` may be added later
  if evidence supports it, but it will never replace `canonical_family`.

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
  triple; TON-IoT: not available in the directory release)
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
  45,678,506 attack + 1,098,191 benign = 46,776,697 rows. Largest class
  DDoS-ICMP_Flood (7,200,501 rows) vs smallest Uploading_Attack (1,252
  rows) is a ratio of approximately 5,751:1.
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

1. Complete the TON-IoT `type` unique-value inventory (value counts, from
   the raw CSV — a read-only pass, no data copies).
2. Review the official field/statistics documents of all three datasets
   (TON-IoT Network Features-Description; CICIoT2023 field definitions;
   N-BaIoT feature description) against every proposed mapping.
3. Re-verify the TON-IoT `label` semantics against the official
   description (which value is attack).

Until then, every mapping in `config/label_ontology.json` carries
`mapping_status: "proposed"`.

> AI生成