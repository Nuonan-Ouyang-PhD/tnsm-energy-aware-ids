# Corrected supplemental paired follow-up

60 accepted runs / ten complete six-method blocks; two invalid attempts retained.
Blocks 1 and 5 span recovery periods. Original V1/P0/P1/R1/R2 are historical,
separate evidence, never pooled. No new measurement or retraining is authorized
by this directory. See `docs/SCIENTIFIC_CORRECTIONS_20261114.md` from repo root.

## Status and interpretation

Author-side raw-frame/state/accounting validation reports 197,922 checks, plus
12.5 million training-transition records. Independent full ZIP/raw-log acceptance
is **NOT COMPLETE**. The external reviewer reported an unavailable execution
environment; absence of independent PASS is not a failed artifact finding.

Q/DQN realize LightLR; DeadlineGuard realizes MedRF. Current detection summaries
match their corresponding static controls. All methods have zero recorded
deadline-miss windows. RL/static intervals spanning zero establish neither
adaptive savings nor equivalence. Cascade has an implementation-specific trade-off.
See all three block sets and both raw/idle-adjusted outcomes, not a selected set.
Queue is constant in the training surrogate; temperature is safety-only. Earlier
constant-coordinate ablations do not prove load/queue/thermal robustness.

## Safe reanalysis

From repository root, using Python 3.11+ standard library only:

```bash
python3 experiments/scheduler_followup/reanalyse_json.py releases/supplemental-followup-20261113/analysis
```

This reads existing JSON and checks all exported paired statistics. It never
imports a physical launcher, connects to a Pi, opens HID, trains or changes files.
It is author-side derived-table checking, not independent evidence acceptance.

## Evidence downloads and packaging

The full evidence ZIP SHA-256 is
`300e40e4474faabcaa63ab6bc02d927e8f52f2f0268cc42e1b4a2115f4735f11`.
Large raw logs remain outside normal Git; this directory publishes browsable
summaries and source bindings, not a claim that Git contains all original bytes.
The two separately uploaded files are **independent standard ZIPs**, not byte
chunks: `TNSM_EVIDENCE_PART_1.zip` and `TNSM_EVIDENCE_PART_2.zip`. Do NOT use `cat`
or old `.zip.part-*` reconstruction instructions for these files. Read each
UPLOAD_PART_INFO and its local manifest, then validate the combined original
member set against the full original MANIFEST_SHA256. Repeated original manifest
bytes must match. Uploaded packaging sidecars are distinct from original evidence.

The small review ZIP omits full raw logs. Its review cannot stand in for ADC,
CPU-accounting, executable binding or full ZIP integrity acceptance. Existing
hash/self-test reports are author declarations until independently reproduced.
