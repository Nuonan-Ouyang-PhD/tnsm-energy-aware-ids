# Materialization Executor Evidence V1

Status: **implementation complete; real materialization not authorized**.

This evidence package implements the materialization-only executor permitted by
the independent review of `MATERIALIZATION_EXECUTION_REQUEST_V1.zip`. It contains
the exact frozen metadata bindings, an explicit deterministic contract, the
guarded executor, invented fixtures, static expected outputs, and mutation tests.

## What is implemented

- Complete authorization validation before any supplied source root is read.
- Exact frozen input and inventory hash validation.
- Complete source identity/header/row preflight before staging creation.
- Per-dataset UTF-8-bytewise shard ordering and one-based four-digit ordinals.
- Dataset-native feature CSVs and four-column label sidecars.
- Exact lineage JSONL, dataset manifests, run identity, and non-self-referential
  root manifest serialization.
- Output cap, free-space, no-clobber, contained cleanup, replay, and atomic publish
  controls.
- Revalidation of every bound metadata input immediately before publication.

The source reader intentionally treats one physical LF-terminated line as one CSV
record. Quoted multiline records fail closed. This makes the frozen CIC physical
line exception identity unambiguous.

## Verification result

- Executor and verifier unit tests: **20/20 passed**.
- Package-only semantic and hash checks: **149/149 passed**.
- Bundled CSV files: **22/22 invented fixture files**; no real dataset CSV is
  included.
- Real CSV access: **false**.
- Real output or staging creation: **false**.
- Splitting, encoding, fitting, and training: **not implemented and not run**.

Run the checks from this directory:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest -v \
  tests/test_materializer_synthetic.py tests/test_executor_evidence.py
PYTHONDONTWRITEBYTECODE=1 python3 scripts/verify_executor_evidence_v1.py --root .
```

Recorded stdout is under `reports/`.

## New disk boundary

The contract preserves the previously reviewed internal output path only as an
unusable baseline binding. It explicitly records that this location fails the
space check. No new-volume name or mount path was guessed.

After the 1 TB disk is mounted, a separate reviewed rebind must specify the exact
output and staging paths on that volume and pass filesystem/free-space checks.
That rebind still does not authorize execution. A distinct user authorization,
bound evidence ZIP hash, and append-only `DECISIONS.md` entry are required before
the CLI can open any real source CSV.
