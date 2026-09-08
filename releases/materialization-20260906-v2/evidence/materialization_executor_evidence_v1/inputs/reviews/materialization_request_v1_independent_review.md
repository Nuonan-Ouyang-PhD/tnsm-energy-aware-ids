# Materialization execution request V1 — independent review

## Decision

The uploaded request archive passes identity/integrity checks. The bundled verifier was actually rerun (114/114, exit 0), and the bundled unit tests were actually rerun (7/7, no skips). The frozen input scope, expected row counts and dataset-native feature selection are supported by the bundled metadata. No materializer is included and no actual output was generated.

**No raw-data materialization, splitting or training is authorized by this review.** Executor development and tests using invented fixtures may proceed without opening the real CSVs or creating the proposed actual output/staging paths. Before operational approval, finalize the remaining output-schema details and test the actual implementation. These refinements may be submitted together with the executor evidence, rather than as a separate documentation-only review cycle. #24 remains accepted and its configurations must not be changed.

Archive: `MATERIALIZATION_EXECUTION_REQUEST_V1.zip`

SHA-256: `55c3c6ee9d6e01fb764a650432b379ca41ca52b703dd33c9ec9cf17088271c63`

Bytes: 78,879. Entries: 31 = 18 regular files including MANIFEST + 13 directories. Modes: 18 x 0644 and 13 x 0755. CRC passed; no duplicate members, unsafe paths, symlinks, AppleDouble, __MACOSX, .DS_Store or Python bytecode/cache members.

The MANIFEST in this particular package has paths relative to the package root (the directory containing README.md), not relative to the extraction parent. All 17 entries were independently hashed; exact coverage and self-exclusion were checked. `sha256sum -c` was also rerun successfully from that package root.

## Independently reconciled metadata

| Dataset | Inventory CSVs | Planned feature/label pairs | Native features | Inventoried rows | Excluded rows | Planned accepted rows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| TON-IoT | 1 | 1 | 32 | 211,043 | 0 | 211,043 |
| CICIoT2023 | 309 | 309 | 39 | 46,776,700 | 3 | 46,776,697 |
| N-BaIoT | 90 | 89 | 115 | 7,062,606 | 0 | 7,062,606 |
| Total | 400 | 399 | Not a common feature space | 54,050,349 | 3 | 54,050,346 |

399 pairs imply 798 feature/label CSV files, plus ledgers and manifests; they are not yet produced. The N-BaIoT structure example has zero data rows and produces no pair. It is not an additional dropped data row. There are exactly three malformed rows registered for CICIoT2023; their file paths, file hashes, sizes and final row positions reconcile to the inventory. Raw-line hashes were inspected as metadata, not remeasured on the raw data.

Independent binary-label totals expected from frozen metadata:

| Dataset | benign | attack |
| --- | ---: | ---: |
| TON-IoT | 50,000 | 161,043 |
| CICIoT2023 | 1,098,191 | 45,678,506 |
| N-BaIoT | 555,932 | 6,506,674 |

TON-IoT's 44 source columns minus its 10 permanently excluded columns and 2 port columns give 32. All ten allowed native categorical columns are retained, unencoded. Dropping ports is permitted by the frozen policy. CIC's 39 columns retain the frozen order. N-BaIoT's 115-column header is consistent across the frozen inventory. No harmonised core or fit/transform is approved or produced.

Feature policy SHA-256: `e81a55c16f9439b0356295353e8b342de19d5c5606d868952592f913beda714b`.

Label ontology SHA-256: `8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab`.

Both are byte-identical to the actual uploaded #24 freeze package, not just to a declared hash. The TON inventory, N-BaIoT inventory and TON label census were also byte-compared to that prior package. The actual #24 acceptance ZIP and its README match the request's declared identities. The original historical `ciciot2023_evidence.zip` was not available as raw bytes in this audit; the bundled CIC inventory/acquisition/exception hashes and their internal bindings are checked, but the claimed recovery from that historical archive is not independently re-performed.

## Storage is an acknowledged execution prerequisite, not a newly discovered defect

Source bytes from all 400 entries: 17,114,499,704.

Hard output cap: 25,671,749,556 = ceil(1.5 x source bytes).

Scratch/replay reserve: 1,073,741,824.

Minimum free bytes: 26,745,491,380 = 24.908679891 GiB.

The bundled observation at 2026-09-06T02:36:36Z (12:36:36 in Melbourne) states available bytes of 6,572,945,408 = 6.121532440 GiB and a shortfall of 20,172,545,972 = 18.787147451 GiB. The arithmetic is correct; no live remote disk measurement was performed. The budget is a declared cap plus reserve, not a measurement or proof of future output size. The executor must enforce both the cap and resource availability; if they are exceeded, abort without publishing. It must not silently increase the cap or change the destination.

Freeing space does not by itself authorize a run. A changed output root must be explicitly reviewed and rebound to the request. This review does not authorize deleting existing research data.

## Output contract refinements before execution

These refinements do not change frozen label assignments or the 32/39/115 feature decisions. Bind them in the request revision/implementation evidence together:

1. **Label sidecar and missing metadata.** The shared sidecar has `source_family`, but TON and CIC transformation blocks define no value for it. Use a declared representation for not-applicable values; an appropriate proposed convention is the empty CSV cell for TON/CIC `source_family`, not an invented malware family. Specify JSON `null` for unavailable device/capture metadata, and the exact JSON type/serialization of the N-BaIoT three-component capture identifier. Keep the existing frozen binary-label strings `benign`/`attack`; do not introduce an unapproved numerical recoding.
2. **Stable identities and serialization.** Specify whether shard ordinals are per dataset, their starting index and whether the zero-row structure example is removed before numbering. A reasonable convention is per-dataset 1-based UTF-8 bytewise-sorted data-file order, excluding the structure example first. Specify CSV header emission and output header order, JSON/JSONL schemas/key ordering/encoding and terminal newline, exact types/fields for excluded physical/source row positions, and dataset-manifest content. Define root manifest self-exclusion and avoid mutual hash dependencies; for example feature/label hashes -> ledger -> dataset manifest -> root manifest, with the root manifest hashing all other files but not itself. These are proposals for explicit contract choices, not assertions that the present package already defines them.

## Current verifier coverage limitation

Four isolated altered-request probes were actually run. Each changed only the temporary proposal JSON and used the package's standalone content verifier. In all four cases it still returned 114/114 and exit 0:

- output root equals staging root;
- TON binary-label rule reversed;
- the request's CIC inventory SHA set to an incorrect value;
- source_subtype removed from the label-sidecar column list.

These results do **not** mean the original signed/pinned archive can be altered undetectably. Each mutation would invalidate the original ZIP/MANIFEST binding, and no attempt was made to claim those bindings remained valid. They demonstrate that the standalone 114-check verifier is not a complete semantic/output-contract validator. This review independently checked that the original current request has the correct distinct roots, binary rule, hash bindings and sidecar list.

Add direct contract assertions and synthetic expected-output fixtures in the forthcoming implementation package, not only same-code replay hash comparisons. Test denial before raw-file opening or real-path creation, wrong source identities, unexpected labels, unregistered malformed rows, input text preservation, feature/label row alignment, exact exception handling, resource failures, no-clobber publication and containment-limited cleanup. All such tests should use artificial fixtures in temporary review directories and not the real dataset or approved destination.

## Audit boundaries

No original dataset CSV was located/opened/hashed, no model or encoder was run, no real output or staging path was created, and no user repository or live configuration was changed. Only source evidence was extracted into the assistant review workspace; temporary altered-package probes used review-only copies. The supplied commit `38ac1cc5afdadd08a81317909b67c19c9b724dc9`, the current Mac working tree, real filesystem free space, and the non-execution of other Mac processes were not independently verified. Test and verifier inputs remained byte-identical.

See archive_audit.json, package_checks.json, semantic_audit.json, contract_source_excerpts.txt and contract_coverage_probes.json for the actual evidence. The synthetic label serialization example demonstrates an unspecified field only; it is not a processed real sample and not an approved materialization output.
