# Experiment implementations

- `classification_static_v1/`: dataset-specific classification, prediction-cache,
  Raspberry Pi parity, and static replay implementation plus execution logs.
- `static_physical_v1/`: static physical-campaign controller, worker, measurement,
  schedule-preparation, and tests. Large raw evidence is in the article-data release.
- `adaptive_scheduler_v1/`: CFSM, Tabular-Q, DQN, reward/state handling, physical runtime,
  cost registry, robustness/sensitivity runners, and final packaging validators.

Python virtual environments, source datasets, materialized datasets, duplicate local
packaging candidates, and caches are intentionally excluded from Git.
