# Formal reproduction matrix (draft until Gate D)

This matrix replaces the unavailable historical experiment. Values below are
the intended protocol, not completed results. It must be frozen before formal
data collection.

## Computing roles

| Component | Role |
|---|---|
| M4 Mac mini, 16 GB | Dataset preparation, model and policy training, cache creation, orchestration, analysis |
| Raspberry Pi 4B, 8 GB (`pi4b8g`) | Primary on-device inference and scheduler evaluation |
| One external logging power meter | Sequential whole-device USB-input measurement |
| Other Raspberry Pis | Optional later portability checks; never pooled as identical boards |

## Classifier pool

| ID | Frozen specification |
|---|---|
| TinyDT | Decision tree: max depth 6, min split 20, min leaf 10 |
| LightLR | L2 logistic regression: C=1, liblinear |
| MedRF | 25 trees: max depth 10, min split 10, min leaf 5 |
| HeavyMLP | Hidden layers 64/32/16, ReLU, dropout 0.2, Adam 0.001 |

Every preprocessing transform and trained checkpoint is fitted on training data
only, serialized once on the Mac, hashed, copied to the Pi, and kept frozen for
evaluation. All methods consume the same per-model prediction cache for replay
comparisons.

## Algorithms

| ID | Evaluation behavior |
|---|---|
| Static-TinyDT | Fixed TinyDT |
| Static-MedRF | Fixed MedRF |
| Static-HeavyMLP | Fixed HeavyMLP |
| CFSM | Fixed thresholds and two-window cooldown |
| Tabular-Q | Frozen greedy Q table, no evaluation updates |
| DQN | Frozen greedy value network, no replay buffer during evaluation |
| LI-Utility-Oracle | Label-informed offline comparator only; never called deployable |

## Replay evaluation

| Scenario | Datasets | Seeds | Windows per seed | Samples per window |
|---|---:|---:|---:|---:|
| Stationary | TON-IoT, CIC-IoT2023, N-BaIoT | 10 | 200 | 100 |
| Five-phase drift | TON-IoT, CIC-IoT2023 | 10 | 500 | 100 |

The controlled phases are 100/100/120/100/80 windows with attack ratios
0.05/0.35/0.70/0.40/0.10. Dataset-local source-row IDs and feature digests must
prove that all algorithms in a dataset/seed consume the identical ordered trace.

## Primary physical study

The main physical claim is narrowed to one identified Pi 4B 8 GB, not three
independent identical boards. Use 10 paired blocks. Within each block, create
one 50,000-sample TON-IoT drift stream and replay that identical stream under
Static-MedRF, CFSM, Tabular-Q, and DQN. Randomize the four-method order using a
pre-registered seed. This gives 40 sequential 500-second method runs.

Before every method run, require the recorded cooldown threshold, clean
throttle status, stable power wiring, and synchronized clocks. Preserve 1 Hz
external meter samples, 1 Hz Pi telemetry, and all 50,000 predictions and
latencies. Because there is one board, inference is limited to repeatability on
that device; repetitions must not be described as independent hardware units.

## Separate static power profiling

Record three 30-minute idle calibrations and three 30-minute runs for each of
the four frozen classifiers. Randomize model order within each repetition.
Report USB-input whole-device power and energy plus incremental power above the
same-session idle baseline. Do not infer whole-device power from Pi-internal
voltage or temperature readings.

## Estimated bench time

- idle and four-model static profiles: 7.5 active hours;
- 40 paired physical runs: 5.6 active hours;
- additional cooldown, setup checks, and failed-run repeats: plan 6–10 hours.

The work can be split across days, with session ID, ambient conditions, wiring,
software hash, and meter identity retained as blocking factors in analysis.

