# P0/P1 strengthening evidence

This release contains the final P0/P1 evidence package produced after the limited
P1B/P1C closure authorization. It includes the exact-source P0 archive, P1A matched
physical control, corrected P1B replacement with the invalid historical attempt,
P1C frozen-policy derived evaluations, P1D reward/state sensitivity, and P1E
gamma/alpha sensitivity.

Reconstruct the archive:

```bash
cat TNSM_P0_P1_STRENGTHENING_20260908_V1.zip.part-* > TNSM_P0_P1_STRENGTHENING_20260908_V1.zip
```

Expected archive SHA-256:

```text
d4e1e96960f1279c79445c744a02be1033e288dad27f440b87753934a3f4b108
```

The archive contains 1,918 file entries and a 1,917-entry root manifest. ZIP CRC,
manifest verification, P1A replacement linkage, P1B semantic validation, frozen-policy
hash checks, and test-leakage checks passed. The `browsable/` directory exposes the
final validator, factual summary, registries, provenance, and packaging scripts.

These outputs are strengthening evidence. They do not replace or modify the original
evidence-locked 40-run adaptive campaign.
