# Final output contract

Create a new append-only package:
`TNSM_REVIEWER_REVISION_EVIDENCE_202609XX_V1.zip`

Top-level:
README.md
REVISION_CONFIG_LOCK.json
r0_source_audit/
r1_cascade_physical/
r2_variable_load/
r3_controller_power/
r4_threshold_and_reference/
registries/
analysis/
validation/
failures/
MANIFEST_SHA256.txt

Required registries:
- `r1_run_registry.csv`
- `r2_run_registry.csv`
- `r3_segment_registry.csv`
- `r4_tinydt_threshold_diagnostic.csv`
- `revision_attempt_registry.csv`

For R1/R2 physical rows include:
block_id, run_id, method, valid, run_order, trace_hash, config_hash, model_hashes,
policy_hash, start/end/duration, energy_j, mean_power_w, preceding_idle_power_w,
tn,fp,fn,tp,f1,recall,fpr,balanced_accuracy, escalation_fraction if applicable,
scheduler latency, detector latency, end-to-end completion, queue/backlog,
max/mean temperature, throttle, undervoltage, missing samples/windows,
failure_reason, replacement_for.

For R2 also include:
unique_state_count, load-bin occupancy, threat-bin occupancy, model occupancy,
switch count, TinyDT fallback count, deadline miss count/rate.

For R3:
condition, block_id, segment_id, valid, order, energy_j, mean_power_w,
preceding_idle_power_w, decision_count, decision mean/p50/p95/p99, CPU/RSS/temp,
throttle/undervoltage.

Validation gates:
- no current/future ground truth enters action selection;
- cascade band remains exactly [0.3,0.7];
- no original policy retraining;
- no original V1/P1 modification;
- all attempted runs retained;
- all replacements linked;
- all root/nested manifests internally consistent;
- ZIP CRC PASS;
- final SHA-256 reported.

Final factual summary must explicitly distinguish:
- existing V1/P1 evidence;
- new revision evidence;
- software-only diagnostics;
- physical measurements;
- any unavailable optional reference-load check.

Do NOT draft manuscript claims. Return evidence to ChatGPT for independent recomputation.
