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

## 6. Feature/label protocol freeze proposal (staging record)

This section is the staging record for DECISIONS.md #23
(FEATURE-POLICY-20260905-V1-PROPOSED). It is a proposal for review
only: no status is flipped here, config/feature_policy.json is
byte-identical to the pre-proposal commit (SHA-256
`2a903a4a0dd54e4307b7dce24599c39ce62b378b4cd8a95f8a633ffedb321b47`),
and config/label_ontology.json stays frozen
(`8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab`).

Proposal pre-condition satisfied (one-off user-authorized audit
exception, NOT a gate lift): the TON-IoT `proto` value census
completed read-only over the frozen train_test_network.csv
(artifacts/datasets/proto_census/ton_iot_proto_20260905T110840Z.json,
SHA-256
`89f06e9c3913e2d429be6021ff42f907727f36e69cebf5bc5639b9793e689830`):
exactly 3 raw values (tcp 168747, udp 42015, icmp 281), zero
anomalies, rows reconciled 211043 = 211043. The census is audit
evidence only; it must not become an all-data encoder vocabulary, and
the training-split-only encoder rule stands.

What a future #24 freeze would change (subject to separate explicit
authorization; the full enumeration with evidence anchors is in
DECISIONS.md #23):

1. Four structured status fields proposed -> frozen: the policy root
   `status`;
   `semantic_core.candidate_examples[0].decision_status`
   (total_transferred_bytes, stays `unresolved` - not admitted this
   version); `semantic_core.candidate_examples[1].decision_status`
   (decayed_window_statistics, stays `rejected` - the cross-dataset
   mapping is rejected, N-BaIoT native features are not deleted);
   `semantic_core.review_outcome_2026_09_04.resolved_points[0].
   decision_status` (MI_dir, stays `derived`). `frozen` here locks
   the review decision of this version; it does not assert the
   mapping holds, does not resolve the unresolved, and does not bar a
   future evidence-based version.
2. Evidence completion per record (additions, not flips): official
   documents cited with path, SHA-256, and page/table/section
   anchors, per the strict reading of freeze condition 3.
3. New target wording for the two string-embedded candidate records:
   protocol_indicators - exactly the subset {tcp, udp} proposed for
   admission as pairwise ton_iot__ciciot2023 mappings (both sides
   officially transport-layer; seven gates pass); icmp stays
   `unresolved` (TON-IoT proto is officially transport-layer while
   CICIoT2023 ICMP is officially the network-layer indicator; value
   coincidence is not semantic equivalence); no counterpart is
   invented for the remaining CICIoT2023 protocol columns.
   packet_count stays `unresolved` (connection vs flow aggregation
   object unconfirmed). If #24 converts these to structured records,
   the status-path enumeration must be re-derived from the resulting
   config.
4. Data-handling gate target values, effective only at #24 under its
   own authorization: materialization/splitting/training each change
   from "forbidden before protocol freeze" to "permitted after
   protocol freeze (#24), subject to the label-ontology chain, this
   feature/label protocol freeze, and the standing experimental
   discipline". Until #24, all three gates remain forbidden.

All statuses are UNCHANGED at proposal time. Nothing outside the
freeze scope (label_ontology.json, frozen mapping tables, semantic
dispositions, audit gates, native feature sets) is touched by this
proposal, and the freeze alone does not lift the
materialization/splitting/training ban - that requires #24 and its
own authorization.

> AI生成
