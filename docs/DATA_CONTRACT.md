# Data contract

Every run receives a unique directory and must preserve the following layers.

| Layer | Required evidence |
|---|---|
| Manifest | Run ID, UTC timestamps, host snapshot, source revision, configuration hashes, eligibility flag |
| Events | One row per scheduler/inference window, monotonic sequence, workload/model/action identifiers, latency |
| Device telemetry | UTC and monotonic time, temperature, throttle flags, CPU frequency, available memory, load |
| External power | Meter-native samples with its own timestamp, voltage, current, power, and cumulative energy |
| Validation | Machine-readable pass/fail checks and reasons |

Formal raw files are append-only evidence. Corrections create derived files and
must not overwrite originals. The run manifest must contain SHA-256 hashes for
all registered inputs and outputs before analysis.

The current smoke workload is a deterministic SHA-256 diagnostic. It is not IDS
inference, does not estimate accuracy or energy savings, and cannot be cited as
a paper result.

