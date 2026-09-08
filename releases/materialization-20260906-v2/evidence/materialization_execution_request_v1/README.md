# Materialization-only execution request V1

This package prepares one narrowly scoped request: deterministic
materialization of the three frozen dataset-native feature spaces under
`FEATURE-POLICY-20260905-V1-FROZEN`.

It is **not an authorization**. No raw CSV was opened while preparing this
package; no output/staging directory was created; no materialization,
splitting, encoder fitting, model fitting, or training was run. The package
does not modify either frozen configuration file.

## Current readiness

The input identity is complete. The CICIoT2023 inventory referenced by the
frozen ontology was recovered byte-for-byte from the previously frozen
`ciciot2023_evidence.zip` and is bundled with its acquisition and quality
exception manifests. Across the three inventories the fixed input is 400 CSV
files, 17,114,499,704 bytes, and 54,050,349 inventoried rows. The only data-row
exclusions are the three registered truncated CICIoT2023 final lines; the
N-BaIoT zero-row structure example produces no output. Planned accepted rows:
54,050,346 in 399 source-preserving shards.

The requested output root is fixed at:

```text
/Users/nuonanouyang/Documents/ChatGPT/TNSM-materialized/FEATURE-POLICY-20260905-V1-FROZEN/MATERIALIZATION-20260906-V1
```

The hard output cap is 25,671,749,556 bytes and the minimum free-space check is
26,745,491,380 bytes. At preparation time the destination filesystem had only
6,572,945,408 bytes available, a shortfall of 20,172,545,972 bytes. Therefore
execution at this location is currently blocked even if the request is later
accepted. Space must be provisioned and the preflight rerun; changing the
output root requires a new reviewed request version.

## Review entry points

- `proposal/materialization_execution_request_v1.json` is the complete
  machine-readable contract.
- `docs/MATERIALIZATION_EXECUTION_REQUEST.md` is the human-readable review.
- `docs/DECISIONS_25_PROPOSED.md` is proposed text only; it is not installed in
  the live decision log and records no authorization.
- `scripts/verify_materialization_request_v1.py` is a package-only, read-only
  verifier. It never opens raw dataset CSVs.
- `tests/test_materialization_request.py` exercises the positive package and
  mutation/authorization-boundary failures on temporary copies.
- `inputs/` contains only small frozen protocol, inventory, census, exception,
  acquisition, and acceptance evidence. It contains no raw dataset row data.

## Deliberately not included

No materializer is included. An executor may be prepared and reviewed against
this exact contract, but it must refuse to open raw CSVs without a separate
materialization-only authorization record. Splitting and training remain
forbidden and require their own later requests.
