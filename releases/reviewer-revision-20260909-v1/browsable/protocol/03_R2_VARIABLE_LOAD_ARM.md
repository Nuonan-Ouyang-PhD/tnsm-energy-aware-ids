# R2 — Prospectively frozen variable-load physical arm

## Scientific question
Does the previously frozen learned controller exhibit useful adaptation once arrival-rate state actually leaves the four-state support of the original campaign, and how does it compare with static and conditional non-learning controls?

This arm is NOT constructed to make RL win. The factorial load/threat schedule below is frozen before execution and the result is valid whether learned policies switch, collapse, or fail.

## Methods
A = Static-LightLR
B = ConfidenceCascade_0p3_0p7
C = Tabular-Q_frozen
D = DQN_frozen
E = Static-MedRF
F = DeadlineGuard (new predeclared non-learning load-aware reference)

Do not retrain any learned policy.

### DeadlineGuard semantics (freeze before R2)
DeadlineGuard exists specifically to test the Reviewer-2 scenario in which the resource-feasible static choice changes with load. It is a deterministic two-point controller, not a learned policy:
1. Let $N_t$ be the causal arrival count for the current one-second service interval.
2. Let $L^{95}_{RF}$ be the already archived pre-R2 p95 MedRF latency per 100 rows (use the exact frozen timing artifact and hash it in `REVISION_CONFIG_LOCK.json`).
3. Predict MedRF service demand as `ceil(N_t/100) * L95_MedRF`.
4. If predicted demand <= 1.0 s, choose MedRF; otherwise choose LightLR.
5. No current label, phase ID, future arrival, or current detector output is available to this rule.

The one-second threshold is the actual scheduling/service interval, not a value selected from R2 outcomes. The rule must be unit-tested over all predeclared load levels before the first R2 physical run. At least one load level must map to MedRF and at least one to LightLR under the frozen pre-R2 latency profile; otherwise STOP before R2 and report that the proposed workload does not instantiate the intended changing-feasibility scenario.

## Workload
Each formal run is 500 s:
- nine 50-s factorial cells covering load x attack prevalence exactly once;
- one final 50-s recovery cell.

Load levels (rows/s):
- LOW = 50
- MID = 100
- HIGH = 4000

Threat prevalence targets:
- LOW = 0.10
- MID = 0.50
- HIGH = 0.90

Why 4000 rows/s:
The previously measured MedRF batch time is approximately 30.95 ms per 100 rows, so 4000 rows/s deliberately enters the regime where its inference-only service demand can exceed a one-second interval. This is a workload-stress choice derived from the already measured capacity scale, not from method outcomes in this new arm.

For each block, generate a permutation of the nine factorial cells using the frozen generator seed `20260908 + block_id`, then append the recovery cell `(100 rows/s, 0.10 attack prevalence)`. Freeze all ten full schedules, row IDs, labels, features, hashes, and phase boundaries before the first hardware run.

The controller receives only causal arrival count/queue/temperature/threat context under its existing semantics. It never receives the factorial cell ID or target prevalence.

## Paired block order
Six methods are used. Ten blocks cannot be perfectly position-balanced across six positions; the following fixed order was selected before execution to keep each method/position count to 1--3 while distributing first-order carryover. Do not regenerate it after results are observed.

B01: D B E C F A
B02: F D E A B C
B03: B C A E D F
B04: E F C B D A
B05: A C F D E B
B06: F E B C A D
B07: B D C A F E
B08: C B F D A E
B09: C E B F A D
B10: E A D B C F

Each method run is preceded by a 60-s instrumented reference-idle segment.

## Mandatory state-coverage outputs
For every learned-policy decision retain:
- exact encoded state index;
- temperature/threat/queue/load bins;
- previous action;
- selected action;
- whether the state was visited during original policy training if that support map is reconstructable.

Report:
- unique states visited;
- count/fraction in each load bin;
- count/fraction in each threat bin;
- full action occupancy;
- between-window switch count;
- TinyDT fallback frequency for Tabular-Q;
- deadline/backlog violations.

## Service diagnostic
Predeclare a one-second window service deadline. For each static detector, compute per-window processing completion relative to that deadline from actual timestamps; do not infer feasibility only from historic latency. Report deadline miss rate and queue growth.

This diagnostic establishes whether the variable-load arm actually creates a management regime where the best feasible static choice changes with load. Do NOT alter the workload if it does not.

## Outcomes
Detection: F1, recall, FPR, BA and confusion counts.
Systems: energy, power, decision latency, detector latency, end-to-end window completion, queue/backlog, temperature, throttle/undervoltage.
Policy: occupancy, switches, state coverage, off-support actions.

## Analysis
Primary repeat unit = paired block.
Preserve all ten block-level contrasts.
Report raw and preceding-idle-adjusted power as separate endpoints.
No window-level pseudo-replication.

