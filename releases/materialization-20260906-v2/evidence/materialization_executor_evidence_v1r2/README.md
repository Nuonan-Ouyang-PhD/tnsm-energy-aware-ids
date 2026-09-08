# Materialization Executor Evidence V1R2

Status: **E01–E04 implementation revision complete; real materialization not
authorized**.

This package is the combined revision permitted by the independent review of
`MATERIALIZATION_EXECUTOR_EVIDENCE_V1.zip`. It preserves the frozen #24 inputs
and dataset-native 32/39/115 feature path while correcting the four reproducible
runtime boundaries identified in that review.

## Revision outcome

- **E01 — runtime evidence binding:** before any source-root inspection, the CLI
  safely reads the authorization-bound evidence ZIP without extracting it,
  verifies its MANIFEST and every member, and requires the actual contract,
  executor source, two frozen configs, three inventories, census, quality
  exceptions, and request JSON to be byte-identical to the approved archive.
  The authoritative archive contract is parsed once and retained in memory; the
  execution core does not reload a possibly changed contract path.
- **E02 — replay storage:** deterministic replay uses incremental digest/count
  sinks and writes no replay file or in-memory output copy. Hash, byte count, row
  count, exclusion record, source hash, and label counts are compared per shard.
  Scratch-reserve checks also run after every replayed shard and metadata phase.
- **E03 — complete preflight and LF boundary:** all 400 inventoried CSV entries,
  including `n_baiot/demonstrate_structure.csv`, are checked before staging. The
  structure file must remain the one frozen zero-row file. Headers and normal
  records require LF; the only missing-LF allowance is the exact three frozen CIC
  malformed final rows whose complete registered identities match.
- **E04 — publication and failure safety:** publication uses Darwin
  `renameatx_np(..., RENAME_EXCL)` and never falls back to a replacing rename.
  Output-parent and staging device/inode identities are retained and rechecked.
  Because pathname recursive deletion cannot condition deletion atomically on an
  inode, failed staging is preserved and reported; the executor performs no
  automatic `rmtree`, so a foreign replacement is never deleted.

## Verification result

- Unit tests: **37/37 passed** — 26 executor/runtime tests and 11 evidence-verifier
  tests.
- Package-only semantic and hash checks: **187/187 passed**.
- Bundled CSV files: **22 invented fixtures only**.
- Real CSV access: **false**.
- Real output or staging creation: **false**.
- Materialization, splitting, encoding, fitting, and training: **not run**.

Run from this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tests/test_materializer_synthetic.py tests/test_executor_evidence.py
PYTHONDONTWRITEBYTECODE=1 python3 \
  scripts/verify_executor_evidence_v1r2.py --root .
```

Recorded stdout is under `reports/`. The detailed closure matrix is in
`docs/E01_E04_CLOSURE.md`.

## Authorization and new-disk boundary

This package contains no execution authorization. A future authorization must
bind the exact evidence ZIP SHA-256, archive root, evidence MANIFEST SHA-256,
contract SHA-256, executor SHA-256, request ZIP SHA-256, output root, operation
map, and an append-only `DECISIONS.md` entry containing all those values.

The old internal output path remains only as an explicitly unusable baseline.
No new-volume path was guessed. After the 1 TB disk is mounted, its exact volume
path, capacity, filesystem, output/staging siblings, and real support for
`RENAME_EXCL` must be checked with non-dataset temporary paths and reviewed in a
separate rebind. A rebind is not authorization to read real CSVs or materialize.
