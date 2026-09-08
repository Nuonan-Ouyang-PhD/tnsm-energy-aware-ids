# Adaptive scheduling campaign V1

Date: 2026-09-07 (Australia/Melbourne)

This campaign continues from the accepted classifier, materialization, Pi parity,
and fifteen-run static power baselines. Those artifacts are immutable inputs and
will not be regenerated.

## Scope and order

1. Integrate the already-computed replay-interval and encoded-overlap corrections.
2. Build the resource-cost registry without relabelling TON-IoT measurements as
   measurements for CIC-IoT2023 or N-BaIoT.
3. Freeze one scheduler configuration. Train Tabular-Q and DQN only from the
   existing training/validation partitions and eligible measured/calibration
   costs. CFSM is a fixed rule baseline.
4. Hash policy artifacts before any held-out test replay. Evaluate all methods on
   identical frozen traces with no policy updates and no label or phase leakage
   into online decisions. Test labels are used only for post-hoc scoring.
5. Run one end-to-end physical pilot using training/validation-derived TON-IoT
   input. The pilot is excluded from formal statistics and is not used to tune a
   policy based on held-out performance.
6. If configuration, policy hashes, authorization, pilot, Pi, meter, telemetry,
   and failure guards all pass, execute 10 paired blocks of four 500-second runs:
   Static-MedRF, CFSM, Tabular-Q, and DQN. Each block uses one identical 50,000-row
   TON-IoT held-out drift trace and a precommitted randomized method order.

## Fixed boundaries

- Existing split seed 11 and classifier threshold 0.5 remain unchanged.
- The four accepted classifier checkpoints and preprocessors remain unchanged.
- Formal physical scope is one identified Pi 4B 8GB and TON-IoT only.
- Existing static power data are 100-row/s, resident-model, USB load-side KM003C
  measurements. They are not tight-loop latency measurements, wall power, or
  three-dataset power measurements.
- All four classifiers remain resident. An action changes the selected resident
  model at a window boundary; it does not cold-load a model.
- No policy updates occur during pilot test scoring, software test replay, or the
  40 formal physical runs.
- A failed physical run is retained as invalid. It is never stitched, fabricated,
  silently deleted, or automatically retried.

## Physical validity gate

A formal run requires: Pi identity match, clean throttle status, temperature below
the fixed limit, synchronized clocks, intact bound artifacts, the KM003C interface
and serial match, valid signed-current decoding, stable accepted voltage envelope,
fresh 1 Hz power and Pi telemetry, complete predictions, and no missed workload
deadline. Any failure stops the campaign and preserves the run directory.

The software configuration file and generated policy manifests contain the exact
numeric definitions, seeds, normalization, selection rule, and hashes. They are
the machine-readable authority for this campaign.
