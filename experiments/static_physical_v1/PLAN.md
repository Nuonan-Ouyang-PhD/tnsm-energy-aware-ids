# Physical static profiles V1 — fixed before collection

Authority: user's all-experiment grant and subsequent explicit instruction:
“我已经验证了这个电源就是这样偏高我测试了其他的几个Pi也都是一样的结果 你就开始实验吧这个过”.
The user accepts the observed above-label supply voltage as this setup's fixed
condition. This supersedes the previous unresolved-voltage start gate, but is
not independent instrument calibration, certification, or a voltage-safety claim.
No change to PD, voltage, firmware, or meter calibration is authorized or needed.

Pi4B8GB pi4b8g, KM003C USB serial075356 HW2.4 FW2.0.6, XBS-0530 label5V3A
(user identifies it as official). Observed supply approximately5.4V. Supply
identity/voltage and single-device nature must accompany published claims.
Meter male connector enters Pi; normalize consumed current as minus the signed
ADC value. Preserve original sign and bytes. The HID logger is on the Mac;
reported power is at the meter's USB measurement point, not AC-wall power.
No additional instrument calibration or ambient thermometer is available;
temperature inside the meter is not substituted for ambient temperature.

15 sequential profiles: three repetitions, each begins with 1800s idle and
then each of four frozen TON classifiers for1800s. Model order within repetition
is randomized with seed20260906 and recorded before starting. No adaptive policy
is trained or evaluated by this profile stage. No automatic retry after failure.
All four models stay loaded during idle and active runs, with the same two-thread
CPU limit and telemetry loop. Thus idle means instrumented process-idle, not an
unmodified minimal operating system. No artificial CPU stress is added.

Active profile input: first10000 rows of the previously fixed TON training tensor
and their source IDs; no test labels or holdout-driven selection. Cycle successive
100-row batches at one batch per second. All models use identical input order.
Thirty-minute profiles comprise1800 inference batches (180000 row presentations,
10000 unique training rows), not new independent traffic or 180000 unique rows.
Twenty untimed warmup batches/model occur before each run's cooldown/start gate.
Artifacts and reference predictions are hash-checked; Pi validates parity before
the first formal window. Latency is batch encoded-input inference, not per-row
or end-to-end network IDS latency. Preprocessing is excluded and disclosed.

Mac records1801 voltage/current boundary samples at1Hz for1800s. Each sample
retains request ID, exact reply, UTC, monotonic request/receive timestamps and
round-trip duration. Integrate P=V*(-I) by trapezoids on observed host sample
times; report actual duration and no extrapolation. This is a1Hz approximation,
not a precision energy-integrator calibration or a guarantee against aliasing.
Pi records1Hz temperature, throttle flags, frequencies, load and workload timing.
Both align to a shared future UTC; record SSH clock-offset/round-trip checks.
Maximum clock-offset bound0.25s; deadlines may be at most0.25s late; an excessive
interval (>1.5s) invalidates the run. No missing sample interpolation.

Start: clean throttle flags, temperature<=45C, NTP synchronized, free disk>=1GB,
meter reply valid, correct serial and artifacts. Per-window guards: temperature
<70C, clean throttle flags, valid1Hz telemetry, finite positive consumption.
Accepted run voltage envelope4.75–5.50V is an operational abort criterion chosen
for this accepted setup, NOT the board's specified operating range. Also stop if
voltage shifts by>0.30V from the session's initial reading, current exceeds3A,
communication fails or timing bounds are exceeded. No software voltage correction.

On any failure stop the workload, retain partial logs and mark invalid. Remote
controller has a watchdog: Mac sends heartbeats and Pi stops on control-channel
closure or >5s heartbeat loss. No automatic delete, power-off, reboot, retry or
firmware action. Cooldown between runs is instrumented idle, checked every5s,
up to30min; otherwise stop the campaign. This phase takes7.5 active hours plus
setup/cooldown. Summaries are provisional until end-to-end count/hash validation.
