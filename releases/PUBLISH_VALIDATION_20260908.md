# GitHub publication validation — 2026-09-08

This record describes checks run against the publication worktree immediately
before its Git commit and push. It is a publication-integrity record, not a new
experiment or a reinterpretation of existing results.

## Test results

| Scope | Result |
| --- | --- |
| Repository test suite (`make test`) | 230/230 passed |
| Adaptive scheduler unit tests | 13/13 passed |
| Materialization executor V1R3 tests | 32/32 passed |

## Archive verification

| Archive | Bytes | ZIP entries | SHA-256 | Result |
| --- | ---: | ---: | --- | --- |
| `TNSM_ADAPTIVE_SCHEDULER_20260907_V1.zip` | 93,360,624 | 625 | `cc40aa48f2cabdbc7112823c57b89fbdfa571590a501a7985aeac338e13e040f` | split-part reconstruction and CRC passed |
| `TNSM_P0_P1_STRENGTHENING_20260908_V1.zip` | 141,322,551 | 1,918 | `d4e1e96960f1279c79445c744a02be1033e288dad27f440b87753934a3f4b108` | split-part reconstruction and CRC passed; 1,917/1,917 manifest entries matched |

## Publication guards

- No Git object added by this publication exceeds GitHub's 100 MB per-file limit.
- Python virtual environments, bytecode caches, and macOS metadata are excluded.
- The original adaptive 40-run evidence and invalid/interrupted attempts remain
  preserved; this publication did not rerun or rewrite them.
- P1B's original 240-unit attempt remains marked invalid, while the corrected
  240/240 replacement is separately identifiable.
- P1C contains derived validation/test evaluation of the 20 frozen policies and
  no policy retraining.
