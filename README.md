# TNSM Energy-Aware IDS: Real-Experiment Rebuild

This repository rebuilds the paper experiments from auditable raw evidence.
The first supported target is the Raspberry Pi 4 Model B 8 GB (`pi4b8g`).

## Current stage: v0.1 preflight and smoke only

The current code deliberately produces **no paper-eligible result**. It checks
the host, records telemetry, runs a deterministic diagnostic workload, and
validates the resulting files. Formal runs remain locked until the official
dataset, shared inference cache, trained-model registry, policy registry, and
external power-logger configuration have all been registered.

## From the Mac mini

```bash
./scripts/check_primary.sh
./scripts/deploy_primary.sh
```

The deployment command tests the Mac copy, copies the repository, runs a
read-only Pi preflight, executes the 30-second smoke only if preflight passes,
and copies the resulting evidence back under `collected/pi4b8g/`.

The deployment target defaults to `pi@pi4b8g.local` and the remote directory
defaults to `~/tnsm-energy-aware-ids`. Override them if needed:

```bash
PI_HOST=192.168.1.50 PI_USER=pi ./scripts/deploy_primary.sh
```

If the Pi reports that `python3-venv` or `rsync` is missing, install only the
named prerequisite and rerun the deployment. No third-party Python package is
required for this stage.

## Local verification

```bash
make test
make formal-gate
```

`make formal-gate` is expected to exit with status 3 until the formal inputs
exist. See `docs/PROTOCOL.md` and `docs/DATA_CONTRACT.md`.
