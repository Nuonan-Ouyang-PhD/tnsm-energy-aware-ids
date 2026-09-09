# R1 — Fixed-rate physical confidence-cascade control

## Scientific question
At the original 100 rows/s cadence, can a simple current-confidence escalation rule recover MedRF-like detection while avoiding running MedRF on every row, and how much whole-device energy does it actually consume?

## Methods
A = Static-LightLR
B = ConfidenceCascade_0p3_0p7
C = Tabular-Q_frozen
D = Static-MedRF

Cascade semantics:
1. Execute frozen LightLR on every row.
2. If LightLR attack probability is within [0.3, 0.7], execute frozen MedRF for that row.
3. Final prediction/score for deferred rows comes from MedRF; otherwise from LightLR.
4. Ground truth is never available to the cascade decision.
5. Thresholds/models are frozen; no test tuning.

## Physical design
- primary Raspberry Pi 4B 8 GB;
- same model-residency mode as P1A;
- same KM003C path and parser;
- 10 paired blocks;
- 4 method runs per block;
- 500 s per method run;
- same frozen 100-row/s trace within a block;
- use the ten already frozen drift traces or a frozen R0 revision holdout trace family if available;
- each method run is preceded immediately by a 60-s instrumented reference-idle segment with all four models resident and the same telemetry process but no detector inference.

Predeclared method order:
B01: D A C B
B02: A B D C
B03: B D A C
B04: D C B A
B05: C B D A
B06: A B C D
B07: C A D B
B08: C D B A
B09: B A C D
B10: B C A D

The order is frozen before execution. Do not rebalance after seeing outcomes.

## Primary outcomes
- raw integrated energy J over actual timestamps;
- mean whole-device power W;
- F1, recall, FPR, balanced accuracy;
- cascade escalation fraction;
- total detector inference time and p50/p95 per window;
- missed-positive presentations per 50,000-row run.

## Drift diagnostic
For every method run retain the immediately preceding 60-s idle-reference mean power.
Derived sensitivity:
`idle_adjusted_mean_power = method_mean_power - preceding_idle_mean_power`.
The raw method energy remains a primary measurement; idle adjustment is a drift sensitivity, not a replacement endpoint.

## Validity
Preserve every attempted run. No automatic retries based on scientific outcome.
A replacement is permitted only for a predeclared instrument/harness validity failure, with a new run ID and `replacement_for`.

## Required evidence
Raw power frames, Pi telemetry, per-window/per-row cascade decisions, deferred-row IDs, both model scores where escalation occurs, final predictions, manifests, hashes, validation JSON, run registry, and block-level paired analysis.
