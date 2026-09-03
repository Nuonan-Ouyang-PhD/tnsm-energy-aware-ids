# v0.1 protocol

## Gate A: connectivity

From the Mac mini, resolve and contact `pi4b8g.local`, then establish SSH as
`pi`. This stage is read-only.

## Gate B: primary-device preflight

The Pi must report:

- hostname `pi4b8g`;
- Raspberry Pi 4 Model B hardware;
- at least 7 GiB RAM visible to Linux;
- `aarch64` architecture;
- synchronized system time;
- readable SoC temperature;
- `vcgencmd get_throttled=0x0` at the start;
- at least 5 GiB free in the repository filesystem; and
- one consistent CPU frequency governor across online cores.

Preflight does not alter system state. A failure blocks the smoke run.

## Gate C: diagnostic smoke

Run 30 one-second windows across four deterministic workload tiers while
sampling device telemetry. The validator requires all event rows, increasing
monotonic timestamps, temperature no higher than 60 °C, no active undervoltage,
frequency-capping, throttling, or soft-temperature flags, and clean start/end
throttle status. It also requires the exact 40-character Git commit resolved on
the Mac and transferred to the Pi; Git does not need to be installed on the Pi.

## Gate D: formal experiment lock

Formal execution remains disabled until all of these are present:

- official-dataset manifest;
- shared-cache manifest;
- model registry;
- policy registry; and
- external power-logger configuration.

Formal design and sample-size decisions will be frozen only after the dataset,
models, scheduler policies, and actual meter/export format are known.
