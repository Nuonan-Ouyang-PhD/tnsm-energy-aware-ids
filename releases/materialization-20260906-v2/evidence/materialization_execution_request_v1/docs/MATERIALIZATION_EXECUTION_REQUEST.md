# Materialization-only execution request

Request ID: `MATERIALIZATION-20260906-V1-PROPOSED`

Status: **prepared, not authorized**

## 1. Requested action and boundary

The requested future action is one deterministic materialization pass over the
already frozen TON-IoT, CICIoT2023, and N-BaIoT CSV selections. The outputs are
dataset-native feature shards, aligned label sidecars, shard-level lineage, and
hash manifests. Source order and dataset boundaries are retained.

This request does not authorize its own execution. It does not include
splitting, training, sampling, balancing, imputation, scaling, semantic-core
construction, feature encoding, or model/encoder fitting. It does not change
`feature_policy.json` or `label_ontology.json`.

Before any raw CSV may be opened, all of the following remain mandatory:

1. independent acceptance of this exact request package;
2. separate explicit user authorization for materialization only;
3. an append-only `DECISIONS.md` entry binding the request ID and accepted ZIP
   SHA-256;
4. a reviewed executor whose first action is to validate that authorization;
5. an absent output/staging root and a passing storage preflight.

## 2. Frozen input identity

The application binds the final #24 freeze ZIP
`6df601a2...ad8939d` and its independent acceptance ZIP
`64feb94b...b2f86e`. The copied protocol inputs remain byte-identical:

- feature policy: `e81a55c1...beda714b`, status `frozen`;
- label ontology: `8a055e2e...0926fab`, status `frozen`.

The authoritative source lists are the three bundled inventories. At execution
the selected CSV set must match every relative path, size, SHA-256, header, and
row count; extra or missing CSVs fail closed.

| Dataset | Inventory SHA-256 | CSVs | Source bytes | Raw rows | Accepted rows |
| --- | --- | ---: | ---: | ---: | ---: |
| TON-IoT | `66179d1b...303c55a` | 1 | 29,902,775 | 211,043 | 211,043 |
| CICIoT2023 | `d31472b2...e2f45f` | 309 | 8,943,771,319 | 46,776,700 | 46,776,697 |
| N-BaIoT | `9ffdf7e9...2fe30da` | 90 | 8,140,825,610 | 7,062,606 | 7,062,606 |
| **Total** | | **400** | **17,114,499,704** | **54,050,349** | **54,050,346** |

The CIC inventory was absent from the #24 freeze ZIP but is explicitly named
by the frozen ontology. Its original bytes were recovered from the already
frozen `ciciot2023_evidence.zip` (`7f63dbf3...4f793a`) and bundled together
with the matching acquisition and quality-exception manifests. This restores
the full 309-file identity without reading any raw CSV.

The 90 N-BaIoT entries include `demonstrate_structure.csv`, a 1,776-byte,
zero-row inventory artifact. It has no data shard and no label. All 309 CIC
files are data files; exactly three registered malformed final data lines are
excluded only when the relative path, source-file hash, physical line, raw-line
hash, and field counts all match the frozen exception manifest.

## 3. Fixed deterministic transformation

All source files are processed in inventory-relative-path byte order and all
accepted records remain in source order. Cells remain text: no trimming,
case-folding, numeric parse/reformatting, missing-value replacement, or learned
transform is allowed. The only serialization normalization is deterministic
RFC-4180-compatible CSV quoting with UTF-8 and LF line endings.

TON-IoT produces 32 native features. It drops the two labels (`label`, `type`),
the eight frozen identifier/free-text exclusions (`src_ip`, `dst_ip`,
`dns_query`, `ssl_subject`, `ssl_issuer`, `http_uri`, `http_user_agent`,
`weird_addl`), and both port columns. Dropping the ports is the conservative
choice explicitly permitted by the frozen policy; no unreviewed port-class
mapping is invented. The ten allowed native categorical fields remain verbatim
and unencoded. Binary label is derived from `label`; subtype and family are
derived through the frozen `type` map.

CICIoT2023 retains all 39 native columns. Labels come only from the category
directory and the frozen 34-entry map. The capture ID is the file stem and is
metadata only. The three exact registered truncated final lines are the sole
data-row exclusions.

N-BaIoT retains all 115 native columns. Binary label, device, source family,
subtype, canonical family, and capture tuple are derived only from the frozen
relative path rules. The root-level zero-row structure example remains
inventory evidence only.

Feature and label CSVs are separate. Provenance fields never enter feature
files. The label sidecar columns are `binary_label`, `canonical_family`,
`source_family`, and `source_subtype`.

## 4. Row-level provenance without row duplication

There is one feature/label shard pair per data source file: 399 pairs. A shard
ledger binds each pair to the dataset ID, file ordinal, relative source path,
source hash/size/header, source and accepted row counts, exclusions,
device/capture metadata, and both output hashes.

Within a shard, output row `k` maps to the `k`th non-excluded source data row.
All current exclusions are final lines, so every accepted output row `k` maps
directly to source row `k`. This gives deterministic row-level tracing without
copying file names or entity identifiers into every model-input row.

## 5. Output and storage budget

The output root and staging sibling are fixed in the JSON contract. Existing
outputs are never overwritten. Publication is one same-filesystem atomic rename
after validation.

- source bytes read-only: 17,114,499,704;
- hard output cap: 25,671,749,556 (`ceil(1.5 x source bytes)`);
- scratch/streaming replay reserve: 1,073,741,824;
- minimum free bytes: 26,745,491,380 (24.909 GiB);
- largest source shard: 315,304,260 bytes.

The preparation-time disk observation failed: 6,572,945,408 bytes available,
20,172,545,972 bytes short. It is not a prediction and must be rerun immediately
before any authorized execution. Until it passes, the application is not
executable at the fixed destination.

## 6. Validation and failure behavior

Preflight validates authorization first, before raw access; then live config
hashes/statuses, all metadata hashes, the complete source identities, path
separation, output absence, free space, and one-operation scope.

Post-validation requires 399 feature/label pairs, exact row/feature counts,
TON census reconciliation, CIC/N path-derived label reconciliation, precisely
three exclusions, manifest exact coverage, byte-identical per-shard replay, and
non-mutation of all inputs. No final root is published until every check passes.

Any mismatch, unexpected label/path, interruption, disk exhaustion, or budget
breach fails closed. Only the exact reviewed staging path may be removed after
containment checks; sources and an existing final root are never modified.
There is no automatic retry. A contract change requires a new reviewed request
version and fresh authorization.
