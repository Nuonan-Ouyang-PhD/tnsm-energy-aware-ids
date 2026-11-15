# Paired Physical Experiment

This directory contains the six-method Raspberry Pi comparison reported in the [paper](../../paper/README.md): 60 accepted workloads in ten complete blocks. Methods share each block's 500-window workload. Each workload has a fresh 60-second preceding idle.

## Contents

`analysis/RUN_METRICS.json` gives run-level energy, detection, completion, and state/action occupancy. `analysis/PAIRED_STATISTICS_AND_SENSITIVITIES.json` gives every method pair across three block sets. Differences are first minus second; intervals are nominal paired Student-t 95% intervals.

`executed_source/` contains the deployed state encoder, FIFO service loop, selectors, monitoring and measurement code, and policy weights. The two runtime snapshots preserve the implementations used before and after the monitor-cadence change; they must not be interchanged when reproducing a particular run. Configuration files may contain unused descriptive fields from earlier code. The executed entry points and common encoder define the actual 108-state interface.

The method set is Static-LightLR, Static-MedRF, Confidence Cascade, DeadlineGuard, Tabular-Q, and DQN. The cascade confidence band is [0.3, 0.7]. DeadlineGuard uses the current work count and a fixed MedRF p95 of 0.015221096 seconds per 100-row batch.

## Analysis

```bash
python3 experiments/scheduler_followup/reanalyse_json.py releases/supplemental-followup-20261113/analysis
```

Run this from the repository root. It reads the supplied JSON without training, hardware access, or changes to the experimental files. The paper build uses the same run metrics to generate tables and the paired-energy plot.

Set A includes all ten blocks; B excludes block 1; C excludes blocks 1 and 5. Blocks 1 and 5 span separated measurement periods after interruptions. Both raw and preceding-idle-adjusted energy/power are retained. Exclusion and adjustment quantify sensitivity; they do not establish that all temporal drift has been removed.

Q-learning and DQN select LightLR in every physical window. DeadlineGuard selects MedRF. All methods complete the workload without recorded deadline misses. Training carryover is constant at zero; the experiment does not establish queue adaptation. Cascade observes current confidence after entry inference and is not a same-information policy ablation.

## Raw recordings

The repository provides summaries and runtime files, not the complete raw ADC, CPU, and row-level recording archives. The complete raw recording is retained separately as two standard ZIP files, `TNSM_EVIDENCE_PART_1.zip` and `TNSM_EVIDENCE_PART_2.zip`. They are not byte-split parts and must not be concatenated. Their local contents together cover the complete original archive. The original archive SHA-256 is:

```text
300e40e4474faabcaa63ab6bc02d927e8f52f2f0268cc42e1b4a2115f4735f11
```

No public download URL for those full raw archives is configured in this directory. The summary files are sufficient for the published table calculations, but not for rebuilding the original ADC integration from raw frames. Contact the corresponding author for the complete recordings.

Failed attempts and recovery associations remain in the registries. Additional fixed-rate experiments elsewhere in the repository are separate datasets and are not pooled with these ten blocks.
