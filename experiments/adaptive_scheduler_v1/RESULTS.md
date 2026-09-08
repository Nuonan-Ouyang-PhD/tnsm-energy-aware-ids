# Adaptive scheduler V1 results

Campaign: `TNSM-ADAPTIVE-SCHEDULER-20260907-V1`

## Completion and evidence

- The excluded end-to-end pilot passed with 121 power samples and 120 decision/telemetry windows.
- All 40 precommitted formal runs passed: four methods in each of ten paired trace blocks, 500 seconds and 50,000 rows per run.
- Every formal run has 501 KM003C power samples, 500 decisions, 500 outcomes, no missing samples, no throttle event, and no automatic retry.
- Tabular-Q and DQN were trained and selected with the fixed training/validation inputs, frozen, and hash-bound before the unchanged held-out test manifest was opened.
- Test labels were unavailable to online decisions and were reopened only after each frozen schedule completed.

## Software comparison on the ten held-out traces

Mean posthoc F1 was 0.60678 for Static-TinyDT, 0.97044 for Static-LightLR,
0.98386 for Static-MedRF, 0.98222 for Static-HeavyMLP, 0.63644 for CFSM,
and 0.97044 for both Tabular-Q and DQN. The two learned policies produced the
same held-out decisions as Static-LightLR in this configuration; this is an
observed result, not a claim that the algorithms are generally equivalent.

The label-informed per-window utility reference remains a nondeployable,
posthoc diagnostic. It is neither an oracle nor a globally optimal trajectory
solution.

## Paired physical results

The table reports the mean across ten trace-matched blocks. Intervals in the
CSV artifacts use a two-sided Student-t 95% interval with df=9 and critical
value 2.262157.

| Method | Energy (J) | Mean power (W) | F1 |
|---|---:|---:|---:|
| Static-MedRF | 1206.787 | 2.41357 | 0.983864 |
| CFSM | 1196.842 | 2.39368 | 0.636440 |
| Tabular-Q | 1193.719 | 2.38743 | 0.970439 |
| DQN | 1200.560 | 2.40112 | 0.970439 |

Against Static-MedRF within the same trace blocks:

- CFSM used 9.945 J less on average (95% CI: 7.117 to 12.773 J less) but F1 was lower by 0.34742.
- Tabular-Q used 13.068 J less (95% CI: 9.736 to 16.400 J less), about 1.083%, while F1 was lower by 0.01343.
- DQN used 6.227 J less (95% CI: 1.600 to 10.853 J less), about 0.516%, while F1 was lower by 0.01343.

Tabular-Q and DQN chose the same model schedule and therefore had the same
classification metrics. Their measured energy differs because the physical
runs occurred at different randomized positions and times. The method-position
counts are unbalanced in this ten-block randomization; `position_sensitivity.csv`
is supplied for that reason, and small energy differences should be interpreted
with the paired estimates and this order limitation.

## Claim boundary

Physical energy is an uncalibrated KM003C USB load-side whole-Pi measurement on
the identified Raspberry Pi 4B 8GB under the accepted supply condition. It is
not AC-wall power. The measured cost registry and these physical results apply
to TON-IoT only. CIC-IoT2023 and N-BaIoT remain explicitly unmeasured; no TON
power value is presented as their measured cost.

The concurrently collected identity audit recorded hostname `pi4b8g`, model
`Raspberry Pi 4 Model B Rev 1.5`, 8,007,464 kB memory, and CPU serial
`100000005368e39d`. The immutable runtime used for this campaign checked the
Pi model and fixed SSH target but did not emit memory and serial in every ready
event. Updated source performs and logs those additional checks for future
reproduction; it did not alter this completed campaign.

## Main artifacts

- `results_v2/software/`: per-window software decisions, outcomes, posthoc scores, and selected prediction artifacts.
- `results_v2/training/`: complete 1,000-episode training logs, trained policies, frozen policies, and inspections.
- `results_v2/physical/raw_execution/`: pilot and all formal power, telemetry, decision, timing, and summary logs.
- `results_v2/physical/run_results.csv`: one row per formal physical run.
- `results_v2/physical/method_summary_t95.csv`: method-level means and intervals.
- `results_v2/physical/paired_vs_static_t95.csv`: trace-paired differences against Static-MedRF.
- `results_v2/physical/position_sensitivity.csv`: method-by-position diagnostic.
- `finalize_results.py`: validation, collection, and result-generation code.
