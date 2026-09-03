---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '6d2fbee9-63e7-49d6-9d8d-25cf4032502d'
  PropagateID: '6d2fbee9-63e7-49d6-9d8d-25cf4032502d'
  ReservedCode1: '8b487292-fb93-4347-9715-9bd1bf829f5b'
  ReservedCode2: '8b487292-fb93-4347-9715-9bd1bf829f5b'
---

# Feature mapping protocol

The manuscript's historical claim of a common 44-feature mapping is not
assumed correct and is not to be reconstructed. The three frozen
inventories show zero shared column names across datasets:

- TON-IoT: 44 columns, Zeek connection-record style (`src_ip`, `dst_ip`,
  `proto`, `service`, `duration`, `src_bytes`, `dst_bytes`, DNS/SSL/HTTP
  protocol fields, ...).
- CICIoT2023: 39 columns, statistical-aggregate style (`Header_Length`,
  `Protocol Type`, flag counts, protocol counts, `Tot sum`, `Min`, `Max`,
  `AVG`, `Std`, `IAT`, ...).
- N-BaIoT: 115 columns, decayed-window flow statistics (`MI_dir_*`,
  `H_*`, `HH_*`, `HH_jit_*`, `HpHp_*` × windows L5/L3/L1/L0.1/L0.01 ×
  weight/mean/variance/std/magnitude/radius/covariance/pcc).

Direction (DECISIONS.md #14): dataset-native feature sets are primary; a
strictly audited semantic core is secondary. No feature is invented for
the sake of recovering the old manuscript's form. All mappings below are
`proposed` until the audit gates in section 3 pass.

## 1. Primary: dataset-native feature sets

Each dataset uses its own defensible features:

- TON-IoT: at most 42 candidate predictor columns (44 minus `label` and
  `type`), then leakage exclusion per section 2.
- CICIoT2023: 39 candidate features (label is not a column; derived from
  the directory name).
- N-BaIoT: 115 candidate features (label is not a column; derived from
  the file location).

All three datasets use the same model families, training budgets,
evaluation rules, and the same scheduling algorithm; input dimensions may
differ. The headline comparisons are within-dataset. Cross-dataset claims
are limited to what the secondary core (if any) supports.

## 2. TON-IoT leakage exclusion

Permanently excluded from model features:

```
label
type
src_ip
dst_ip
dns_query
ssl_subject
ssl_issuer
http_uri
http_user_agent
weird_addl
```

Rationale: direct label leakage (`label`, `type`), entity identifiers
with memorization risk (`src_ip`, `dst_ip`), and free-text fields whose
values can memorize capture-specific artifacts.

`src_port` / `dst_port` are never used as raw numeric values. If kept at
all, they must be converted to a predefined port class (well-known /
registered / dynamic), with the mapping fixed before any split.

The following categorical fields are permitted only in the TON-IoT
native model, and their category encoders must be fitted on the training
split only:

```
proto
service
conn_state
ssl_version
ssl_cipher
http_method
http_version
http_orig_mime_types
http_resp_mime_types
weird_name
```

`dns_AA`, `dns_RD`, `dns_RA` and other low-cardinality protocol flag
columns remain native candidates, subject to the same encoder rule.

IP, device, file, and capture identifiers may be used for group-aware
splits, never as model features (see LABEL_ONTOLOGY.md section 2).

## 3. Secondary: harmonised semantic core

A semantic core is admitted only per-mapping, through ALL of these gates:

1. Physical/statistical meaning is the same.
2. Units are identical, or an explicit conversion is defined.
3. Aggregation object is the same (packet / flow / connection).
4. Time window is the same.
5. Directionality is the same.
6. The derivation formula is reproducible.
7. The official field documentation supports the mapping.

Every candidate mapping is recorded with the full audit record:

```text
canonical_concept
dataset_column
derivation_formula
unit
aggregation_level
time_window
directionality
missing_value_policy
evidence_source
mapping_status: exact / derived / rejected
```

Worked examples of why gates matter:

- `src_bytes + dst_bytes` (TON-IoT, per-connection byte totals) vs
  `Tot sum` (CICIoT2023, window aggregate) is currently only a candidate.
  They may be connection totals vs window statistics; the official field
  definitions must be reviewed before any status is assigned.
- N-BaIoT decayed-window statistics (L5/L3/L1/L0.1/L0.01) must not be
  passed off as plain flow totals; the window semantics gate applies.

Pairwise cores are permitted: a mapping may join only the two datasets
that pass the gates. Only mappings that pass the gates in all three
datasets enter the three-way core. If the three-way core turns out to be
empty or too small to be meaningful, that is reported honestly; no
alignment is forced.

The number of core features is an outcome of the audit, not a
precondition. No target size (including any "10-20") is assumed.

## 4. Paper positioning consequence

The claim structure becomes: the scheduler adapts to heterogeneous
detectors over heterogeneous feature spaces. This is stronger and honest;
the paper must not claim a universal 44-dimensional representation.

## 5. Freeze conditions

Before any mapping in `config/feature_policy.json` moves from `proposed`
to `exact` / `derived` / `rejected`:

1. Review the official field/statistics documents of all three datasets.
2. Complete the TON-IoT `type` value inventory (read-only pass).
3. Each mapping's `evidence_source` must cite the specific official
   document (and section/field where possible).

No data materialization, splitting, or training begins before the
feature/label protocol freeze. Disk budget: design work reads inventory
JSONs and small doc files only; no data copies are created.

> AI生成