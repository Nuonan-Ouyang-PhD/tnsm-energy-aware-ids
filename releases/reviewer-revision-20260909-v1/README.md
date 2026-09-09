# Reviewer-revision evidence V1

This release publishes the complete R0-R4 reviewer-requested revision evidence without
modifying or rerunning the evidence-locked original V1 or P0/P1 campaigns.

Reconstruct the archive:

```bash
cat TNSM_REVIEWER_REVISION_EVIDENCE_20260909_V1.zip.part-* > TNSM_REVIEWER_REVISION_EVIDENCE_20260909_V1.zip
```

Expected archive SHA-256:

```text
845ced5c96f932ee8d3509e2effcb39870a2fb9995bad9a6fe524f6c60b270e4
```

The archive contains 1,912 file entries and a 1,911-entry root manifest. The root
manifest verified 1,911/1,911 files; ZIP CRC/self-test passed; duplicate member names,
unsafe paths, and symlinks were absent. Final validation also confirmed frozen V1/P1
hashes, replacement linkage, no policy retraining, and no test-driven selection.

The factual stage outcomes are R0 PASS, R1 40/40 valid physical runs, R2 60/60 valid
physical runs, R3 not executed under its predeclared stop condition, R4A complete, and
R4B not executed because a stable reference-load device was unavailable. Invalid and
interrupted attempts remain preserved and traceable in the archive.

The `browsable/` directory exposes factual summaries, registries, stop/failure records,
the frozen protocol, validators, and packaging scripts. Raw frame/event streams and
large frozen inputs remain in the split archive.
