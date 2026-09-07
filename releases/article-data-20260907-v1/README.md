# TNSM completed experiment data — 2026-09-07 V1

The complete ZIP is stored as four split parts because the original archive is larger than GitHub's ordinary single-file limit.

## Reassemble

From this directory on macOS or Linux:

```bash
cat TNSM_ARTICLE_DATA_20260907_V1.zip.part-* > TNSM_ARTICLE_DATA_20260907_V1.zip
shasum -a 256 TNSM_ARTICLE_DATA_20260907_V1.zip
unzip -tq TNSM_ARTICLE_DATA_20260907_V1.zip
```

Expected SHA-256:

```text
c135da2db921dc442b4fbea7bd2596aaef8f1eda2f553945d400168d77375c74
```

The archive includes classifier results, replay traces, Raspberry Pi parity and timing evidence, fifteen valid static physical power profiles, interrupted-attempt evidence, materialization evidence, summaries, scripts, and per-file hashes.

## Scope limitation

Adaptive CFSM, Tabular-Q, DQN, offline-oracle comparisons and the planned 40 × 500-second paired physical campaign had not been run when this package was created. They must not be reported as measured results.

Static power is uncalibrated Raspberry Pi load-side USB measurement, not wall-AC energy.
