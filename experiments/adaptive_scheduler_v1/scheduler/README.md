# Adaptive scheduler V1 software CLI

Run commands from the repository root with the project Python environment:

```sh
PYTHONDONTWRITEBYTECODE=1 tnsm_experiments_v1/.venv/bin/python \
  -m adaptive_scheduler_v1.scheduler validate-config

PYTHONDONTWRITEBYTECODE=1 tnsm_experiments_v1/.venv/bin/python \
  -m adaptive_scheduler_v1.scheduler validate-inputs
```

The compact NPZ adapter natively consumes the files already produced by
`adaptive_scheduler_v1/prepare_policy_inputs.py`.  It verifies their hashes and
the fixed train/validation seed sets.  It deliberately never reads
`analysis_only_phase_ids`.  Current files have no online telemetry, so the
adapter uses the neutral values recorded in the unique config and labels that
origin in every outcome; this cannot support a thermal/queue/load adaptation
claim.

## Train and freeze

Training always runs the configured 1000 episodes. Q/network updates consume
only `train_drift_*.npz`; validation labels are used only at the configured
checkpoint interval. No CLI option can substitute test data or reduce the
formal hyperparameters silently.

```sh
PYTHONDONTWRITEBYTECODE=1 tnsm_experiments_v1/.venv/bin/python -m adaptive_scheduler_v1.scheduler train-tabular \
  --output-dir /new/path/tabular-trained

PYTHONDONTWRITEBYTECODE=1 tnsm_experiments_v1/.venv/bin/python -m adaptive_scheduler_v1.scheduler train-dqn \
  --output-dir /new/path/dqn-trained

PYTHONDONTWRITEBYTECODE=1 tnsm_experiments_v1/.venv/bin/python -m adaptive_scheduler_v1.scheduler freeze-policy \
  --input-dir /new/path/tabular-trained \
  --output-dir /new/path/tabular-frozen
```

Training artifacts are deliberately not evaluable on held-out data. The
separate freeze command verifies config, weights, partition metadata, and that
no test data were accessed, then emits a no-clobber frozen artifact.

## Held-out software evaluation

These commands require the test input manifest covering exactly the ten fixed
test seeds and an explicit acknowledgment flag. The V1 results were generated
with these commands only after both learned policies were frozen.

```sh
PYTHONDONTWRITEBYTECODE=1 tnsm_experiments_v1/.venv/bin/python -m adaptive_scheduler_v1.scheduler evaluate-test \
  --policy-dir /new/path/tabular-frozen \
  --input-dir /path/to/test-policy-inputs \
  --input-manifest /path/to/test-policy-inputs/manifest.json \
  --output-dir /new/path/tabular-test \
  --acknowledge-heldout-test \
  --posthoc-labels-from-same-npz

PYTHONDONTWRITEBYTECODE=1 tnsm_experiments_v1/.venv/bin/python -m adaptive_scheduler_v1.scheduler evaluate-cfsm-test \
  --input-dir /path/to/test-policy-inputs \
  --input-manifest /path/to/test-policy-inputs/manifest.json \
  --output-dir /new/path/cfsm-test \
  --acknowledge-heldout-test \
  --posthoc-labels-from-same-npz

# Repeat with each of TinyDT, LightLR, MedRF, and HeavyMLP.
PYTHONDONTWRITEBYTECODE=1 tnsm_experiments_v1/.venv/bin/python -m adaptive_scheduler_v1.scheduler evaluate-static-test \
  --action MedRF \
  --input-dir /path/to/test-policy-inputs \
  --input-manifest /path/to/test-policy-inputs/manifest.json \
  --output-dir /new/path/static-medrf-test \
  --acknowledge-heldout-test \
  --posthoc-labels-from-same-npz
```

The evaluator loads no labels, completes and logs the full frozen action
schedule, and saves selected predictions first. Only then can the optional
posthoc pass reopen labels. `windows.jsonl` separates `window_decision`,
`window_outcome`, and `window_posthoc` events.

The label-informed comparison has its own command and cannot emit a policy:

```sh
PYTHONDONTWRITEBYTECODE=1 tnsm_experiments_v1/.venv/bin/python -m adaptive_scheduler_v1.scheduler offline-reference-test \
  --input-dir /path/to/test-policy-inputs \
  --input-manifest /path/to/test-policy-inputs/manifest.json \
  --frozen-policy-dir /new/path/tabular-frozen \
  --frozen-policy-dir /new/path/dqn-frozen \
  --output-dir /new/path/offline-reference \
  --acknowledge-heldout-test \
  --acknowledge-nondeployable-label-reference
```

Its exact name is **Label-Informed Per-Window Utility Reference**. It uses
labels after the fact, optimizes one window independently, is not deployable,
and is neither an oracle nor a globally optimal trajectory solution.
