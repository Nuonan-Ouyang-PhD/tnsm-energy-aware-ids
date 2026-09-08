# Original adaptive scheduler physical study

This release preserves the evidence-locked original 40-run adaptive physical study.
It must not be regenerated or altered in response to later P1 findings.

Reconstruct the archive:

```bash
cat TNSM_ADAPTIVE_SCHEDULER_20260907_V1.zip.part-* > TNSM_ADAPTIVE_SCHEDULER_20260907_V1.zip
```

Verify the resulting archive with `ARCHIVE_SHA256.txt`. `PARTS_SHA256.txt` binds
the individual Git objects. The `browsable/` directory exposes the factual results,
derived-summary audit, and cost registry without requiring archive extraction.
