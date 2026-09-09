# STOP CONDITIONS / prohibited actions

STOP and report rather than silently modify protocol if:
- the cascade cannot be executed with the frozen LightLR/MedRF artifacts;
- the variable-load harness cannot deliver the predeclared rates while preserving timestamps;
- R0 lineage cannot distinguish unused from previously used source rows;
- the primary policy files/hashes do not match frozen P1 artifacts;
- KM003C logging becomes unavailable or parser identity changes;
- the system throttles/undervolts beyond the predeclared validity rule;
- a reference-load device is not actually available.

Never:
- change the confidence band after seeing R1/R2;
- change 4000 rows/s because results are unfavorable;
- change attack prevalence cells after seeing actions;
- retrain Q/DQN;
- alter reward/state/hyperparameters;
- choose new seeds to make switching happen;
- hide TinyDT fallback;
- remove failed attempts;
- relabel post-hoc source reuse as untouched holdout;
- claim a workload creates changing static optimum unless the measured service/detection evidence actually establishes it.
