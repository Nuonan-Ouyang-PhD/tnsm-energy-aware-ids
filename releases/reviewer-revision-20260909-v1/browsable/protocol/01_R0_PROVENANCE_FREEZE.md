# R0 — Freeze provenance before any new physical run

## 1. Untouched-source audit
Audit the materialized TON-IoT lineage against every source-row ID already present in:
- classifier train/validation/test;
- V1 software/physical traces;
- P1A-E;
- cascade diagnostic inputs.

Create:
`r0_source_audit/unused_source_rows.csv`
`r0_source_audit/unused_source_groups.csv`
`r0_source_audit/audit.json`

If a defensible source-group-disjoint pool exists that has never been used for training, validation, test, tuning, or prior diagnostics, freeze it as `REVISION_HOLDOUT_V1` and record all hashes.

If no adequate untouched pool exists, DO NOT create one by moving existing train/validation/test rows. Use the already frozen held-out test pool only for the new systems-workload experiments and label the arm explicitly as a post-hoc physical robustness experiment rather than unseen-detection generalization.

## 2. Freeze revision configuration
Before R1/R2/R3, write and hash:
- exact Git commit;
- exact six recovered executed-source identities where relevant;
- model hashes;
- primary Tabular-Q/DQN policy hashes;
- cascade rule hash;
- workload generator source hash;
- order schedule hash;
- power-meter parser hash;
- validity rules;
- idle-reference semantics.

Create `REVISION_CONFIG_LOCK.json` and do not change it after the first formal run.

## 3. No test-driven selection
The confidence band is fixed at `[0.3, 0.7]` because it was specified in the external revision request and already evaluated as a software diagnostic. It must not be retuned from any R1/R2 outcome.
