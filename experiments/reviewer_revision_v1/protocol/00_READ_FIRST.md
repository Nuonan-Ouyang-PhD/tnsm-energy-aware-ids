# 00 — READ FIRST: TNSM reviewer-requested revision experiments
Date: 2026-09-08

This is a NEW revision-evidence stage. The original V1 campaign and P0/P1 strengthening package are evidence-locked and MUST NOT be modified, overwritten, reinterpreted as new runs, or rerun because of unfavorable outcomes.

The manuscript has already been restructured around the real finding:
- the learned policies collapsed to LightLR on the formal support;
- most of the original Q-vs-MedRF energy difference is detector operating-point selection;
- candidate-range reward normalization can make pairwise preference algebraically non-reversible;
- sparse state support exposes off-support behavior.

This revision stage answers the remaining reviewer requests with prospectively frozen NEW controls. A valid negative result is acceptable. Do not tune the workload, thresholds, controller, reward, split, or seeds to make a method win.

Execution order:
R0 -> R1 -> R2 -> R3 -> R4 -> final validators/package.

R0: untouched-source audit and immutable revision configuration.
R1: fixed-rate physical confidence-cascade control with within-run idle references.
R2: prospectively frozen variable-load physical arm.
R3: controller-only power decomposition.
R4: TinyDT validation-threshold diagnostic and optional reference-load metrology check.

Do not alter:
- original classifier models or threshold-0.5 primary results;
- original Tabular-Q/DQN/CFSM policies;
- V1/P1 run registries;
- P1A/P1B/P1C/P1D/P1E;
- existing test/validation memberships;
- reward/state/hyperparameter settings.

All new outputs must use a new namespace under `revision_experiments_20260908/`.
