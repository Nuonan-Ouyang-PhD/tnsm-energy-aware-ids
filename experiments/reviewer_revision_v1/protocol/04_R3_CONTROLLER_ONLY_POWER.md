# R3 — Controller-only whole-device power decomposition

## Scientific question
Does the whole-device DQN premium observed in P1A contain a measurable controller-process power component that is not captured by state-to-action timing alone?

## Conditions
A = Static selector (always returns LightLR)
B = CFSM
C = Tabular-Q_frozen
D = DQN_frozen

No detector inference is executed during timed controller segments.
All four detector artifacts remain resident, telemetry remains active, and the process environment matches the P1B replacement as closely as possible.

## State stream
Cycle the four original observed-support encoded states at exactly one scheduler decision per second.
No labels, no detector inference, no policy update.

## Design
4 paired physical blocks.
Each condition is 450 s per block = 1800 s total per condition.
Predeclared order:
B01: A B C D
B02: B C D A
B03: C D A B
B04: D A B C

Before each condition record a 60-s instrumented process-idle reference under the same model residency.

## Outcomes
- integrated energy J;
- mean whole-device power W;
- preceding-idle-adjusted mean power;
- controller decision count;
- decision timing distribution;
- CPU frequency, CPU utilization, RSS/peak RSS;
- kernel temperature;
- throttle/undervoltage.

## Interpretation boundary
A timing difference is not converted into joules. This experiment directly measures the controller-process whole-device power effect.
If differences are not resolved, report that rather than attributing the P1A DQN premium to controller computation.
