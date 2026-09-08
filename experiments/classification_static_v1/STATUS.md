# Continuation status and remaining physical dependency

The user authorized all defined experiment stages without another approval.
No further approval request is needed. This is not a claim that all experiments
are complete.

Completed locally on the Mac:

- Actual full materialization: 400 inputs, 399 shard pairs, 54,050,346 rows;
  all preflight, streaming replay and native no-replace publication checks pass.
- Group-isolated train/validation/test pools and train-only preprocessing.
- Twelve classifiers: four model families on each of three separate datasets.
- Fifty shared test traces with ten workload seeds and 200 static evaluations.
- Saved-model/cache, metric, row identity and cross-split duplicate audits.

Completed on the actual Pi 4B:

- Read-only hardware/throttle/clock checks and isolated dependency installation.
- All twelve models checked against Mac predictions on 10,000 test rows each;
  zero thresholded label disagreements. Artifact hashes verified before loading.
- Each model: twenty warmup calls and 1,000 timed batches of 100 encoded rows.
  This is in-memory encoded-input readiness timing, not end-to-end IDS latency,
  a thirty-minute static profile, or whole-device energy measurement.

Still incomplete:

- A logging external power meter must be identified and connected, with model,
  calibration, wiring and an actual timestamped export/reading interface.
- The matrix's fifteen thirty-minute idle/model profiles and measured cost
  registry; remaining adaptive-state/reward details fixed before policy fitting.
- Tabular-Q/DQN fitting and CFSM/adaptive/oracle replay with valid cost and
  thermal inputs; no synthetic energy substituted for actual measurements.
- Forty paired 500-second Pi physical runs and paired energy/statistical analysis.

The Pi was reachable; its USB inventory showed no logging meter. That does not
rule out a Bluetooth meter or a meter connected to another machine. The user was
asked for its model and log interface, not for another execution permission.

## Configuration identity boundary

The actual materializer uses the authorization-bound package inputs, not the
repository's top-level config paths. Bound feature policy SHA-256 is
`e81a55c16f9439b0356295353e8b342de19d5c5606d868952592f913beda714b`;
bound ontology SHA-256 is
`8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab`.
Both were rechecked unchanged after execution.

The separate repository `config/feature_policy.json` still has the historical
baseline hash `2a903a4a0dd54e4307b7dce24599c39ce62b378b4cd8a95f8a633ffedb321b47`.
It was not the runtime input and was not silently overwritten or represented as
the frozen runtime policy. New experiment code reads the published data and
its recorded lineage, not this unused top-level feature policy.

All outputs and code live in `tnsm_experiments_v1`; source data and the accepted
historical evidence archives remain unchanged. No manuscript result table was
overwritten with partial results.
