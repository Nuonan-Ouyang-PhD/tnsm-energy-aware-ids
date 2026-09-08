# Resource cost registry method and boundary

## Scope

`cost_registry.json` and `cost_registry.csv` are deterministic derivatives of
already recorded evidence. The generator performs no Pi, meter, network, model
inference, or dataset operation. It binds the accepted article-data archive and
the earlier software-evidence archive by SHA-256 before producing output.

The registry contains thirteen entries: one instrumented-idle reference and four
classifier entries for each of TON-IoT, CICIoT2023, and N-BaIoT. It also retains
the fifteen accepted half-hour physical segments so each TON power aggregate can
be traced to three runs.

For every accepted segment, the generator opens its accepted `summary.json`,
checks the raw `power.jsonl` and `pi_telemetry.jsonl` identities, and independently
recomputes the telemetry window count, row count, temperature range, inference
median, and inference p95. These values must agree with the delivered profile
summary before the registry is written.

## Status vocabulary

- `measured`: directly observed in a cited existing run or timing report.
- `derived`: calculated from cited measured values, without adding observations.
- `unmeasured`: no suitable observation exists; the numeric value remains null.
- `proxy`: a measured value used outside its original cadence or residency. It
  must not be presented as an interchangeable direct cost.

Static-profile mean power is backed by measured USB voltage/current samples;
the across-run mean, standard deviation, confidence interval, and matched-idle
increment are derived summaries. Pi tight-loop median and p95 are measured timing
summaries. Their use as an online scheduler cost is marked `proxy` because the
timing loop is not the physical profile cadence and did not measure switching.

## Identity binding

Primary source:

```text
TNSM_ARTICLE_DATA_20260907_V1.zip
c135da2db921dc442b4fbea7bd2596aaef8f1eda2f553945d400168d77375c74
```

Auxiliary source for the Pi `check_X.npy` and reference-prediction identities:

```text
TNSM_SOFTWARE_EXPERIMENT_EVIDENCE_V1.zip
38c90b995d58e63c3c2149de99a6dde0dcd8f968322fb87dbcf960ccb34e4318

pi_check_bundle/inputs_manifest.json
0840fdad15ee5f3fa0e3cd7de3d726d2f48a8d0002c9267346091baaf3f4016a
```

The generator verifies each model and preprocessor member against the article
archive's root manifest. It then checks every Pi manifest model hash against the
same artifact. The physical v1, v2, and v3 input manifests must agree on all four
TON model hashes and the three input-array hashes. The transport worker changed
between collection versions, but the scientific model/input identity did not.

The preprocessor hash is registered for lineage only. Both the Pi timing calls
and physical static windows consumed already encoded arrays; preprocessing, file
I/O, packet capture, and feature extraction were outside their timing boundary.

## Two rhythms are kept separate

The TON physical profiles invoked one selected model on one successive 100-row
encoded batch per second for 1,800 seconds. The KM003C and Pi telemetry were
sampled at 1 Hz. All four classifiers were loaded, parity-checked, and warmed
before the start gate and stayed resident. Consequently, `idle` means this
instrumented process with the four-model pool and telemetry active but with no
per-second inference call. It is not minimal operating-system idle.

The Pi inference report instead timed each dataset/model sequentially: 20 warmup
calls followed by 1,000 tightly looped 100-row calls, without one-second pacing
and without a meter. It is encoded in-memory inference latency, not end-to-end
IDS latency.

The target scheduler semantics are recorded separately: all four
dataset-specific models remain loaded and an action transition selects an
already resident model; it does not load or unload one. TON's static profiles
measured that resident-pool configuration. CICIoT2023 and N-BaIoT timing did not,
so their scheduler-residency evidence status remains `unmeasured` even though the
same target semantics are declared.

These rhythms are not multiplied together. In particular, the registry does not
derive joules per batch from static watts and tight-loop milliseconds. That field
remains `unmeasured`.

## Power scope and uncertainty

Physical power applies only to TON-IoT on the recorded Raspberry Pi 4 Model B
Rev 1.5, 8 GB system. The measurement point was a POWER-Z KM003C at the Pi USB
input/load side, not AC wall power. The meter was not independently calibrated,
the accepted supply read approximately 5.4 V, one Pi was used, and no ambient
thermometer was available.

For each profile, `n=3` sequential repetitions. Across-profile uncertainty uses
sample standard deviation and a two-sided Student-t 95% interval with `df=2`
and `t=4.3026527299`. Incremental power is paired within repetition against the
corresponding instrumented-idle profile. These intervals describe repeat
variation in this one-device setup; they do not represent multiple hardware
units or meter calibration uncertainty.

TON scheduled-latency summaries use the same calculation on the three per-run
batch-median values. Pi tight-loop latency retains its empirical median and p95
over 1,000 calls, but it has no independent-run confidence interval. The
generator recomputes both timing statistics from the 1,000 saved durations in
each Pi report entry.

CICIoT2023 and N-BaIoT have measured Pi tight-loop inference time, but no
dataset-specific physical power or one-batch-per-second latency measurement.
Their power fields therefore remain null and `unmeasured`; TON power is not
silently copied into them. A future explicit proxy assumption, if needed, would
be a separate reviewed choice.

## Necessary measurement gaps

- Model-switch latency is unmeasured. Under the fixed four-model-resident
  semantics, any supplement should measure action-to-action selection and the
  resulting inference behavior, not invent model load/unload cold-start cost.
- First-batch latency after a switch is unmeasured. Existing runs warmed every
  model first, so their medians cannot fill this field.
- A calibrated temperature-response relationship is unmeasured. The observed
  light-load temperatures do not establish high-temperature behavior or safety.
- Dataset-specific CICIoT2023 and N-BaIoT power remains unmeasured.

## Reproduction

From the repository root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 adaptive_scheduler_v1/cost_registry/build_cost_registry.py
```

The command rewrites only `cost_registry.json` and `cost_registry.csv` after all
source checks pass. It creates no new physical measurement and makes no adaptive
policy, energy-saving, switching, or thermal-safety claim.
