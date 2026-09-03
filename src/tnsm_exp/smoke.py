from __future__ import annotations

import csv
import hashlib
import time
from pathlib import Path

from .platform_info import snapshot
from .telemetry import TelemetryWriter
from .util import compact_utc_now, git_commit, read_json, sha256_file, utc_now, write_json


EVENT_FIELDS = [
    "sequence",
    "window_start_utc",
    "window_start_monotonic_ns",
    "workload_id",
    "workload_tier",
    "rounds",
    "workload_duration_ms",
    "window_duration_ms",
    "deadline_missed",
    "result_digest",
]

WORKLOAD_ROUNDS = [5_000, 20_000, 60_000, 120_000]


def diagnostic_workload(sequence: int, tier: int, rounds: int) -> str:
    value = hashlib.sha256(f"tnsm-smoke:{sequence}:{tier}".encode()).digest()
    for _ in range(rounds):
        value = hashlib.sha256(value).digest()
    return value.hex()


def register_files(run_dir: Path, names: list[str]) -> None:
    manifest_path = run_dir / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["files"] = {
        name: {
            "sha256": sha256_file(run_dir / name),
            "bytes": (run_dir / name).stat().st_size,
        }
        for name in names
        if (run_dir / name).exists()
    }
    write_json(manifest_path, manifest)


def run_smoke(repo_root: Path, windows: int, window_seconds: float) -> Path:
    run_id = f"SMOKE_pi4b8g_{compact_utc_now()}"
    run_dir = repo_root / "data" / "raw" / "smoke" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    start_ns = time.monotonic_ns()
    started_at = utc_now()
    start_snapshot = snapshot(repo_root)

    with (run_dir / "events.csv").open("w", encoding="utf-8", newline="") as event_handle:
        event_writer = csv.DictWriter(event_handle, fieldnames=EVENT_FIELDS)
        event_writer.writeheader()
        with TelemetryWriter(run_dir / "telemetry.csv", start_ns) as telemetry:
            for sequence in range(windows):
                target_start_ns = start_ns + int(sequence * window_seconds * 1e9)
                remaining = (target_start_ns - time.monotonic_ns()) / 1e9
                if remaining > 0:
                    time.sleep(remaining)
                actual_start_ns = time.monotonic_ns()
                window_start_utc = utc_now()
                telemetry.sample()
                tier = sequence % len(WORKLOAD_ROUNDS)
                rounds = WORKLOAD_ROUNDS[tier]
                workload_start_ns = time.monotonic_ns()
                digest = diagnostic_workload(sequence, tier, rounds)
                workload_ms = (time.monotonic_ns() - workload_start_ns) / 1e6
                event_writer.writerow(
                    {
                        "sequence": sequence,
                        "window_start_utc": window_start_utc,
                        "window_start_monotonic_ns": actual_start_ns,
                        "workload_id": "diagnostic_sha256_v1",
                        "workload_tier": tier,
                        "rounds": rounds,
                        "workload_duration_ms": round(workload_ms, 6),
                        "window_duration_ms": round(window_seconds * 1000, 3),
                        "deadline_missed": workload_ms > window_seconds * 1000,
                        "result_digest": digest,
                    }
                )
                event_handle.flush()

    protocol_path = repo_root / "config" / "protocol.json"
    devices_path = repo_root / "config" / "devices.json"
    manifest = {
        "schema_version": 1,
        "kind": "diagnostic_smoke",
        "run_id": run_id,
        "device_id": "pi4b8g",
        "paper_eligible": False,
        "eligibility_reason": "Diagnostic workload; not IDS inference and no external power evidence",
        "started_at_utc": started_at,
        "completed_at_utc": utc_now(),
        "source_commit": git_commit(repo_root),
        "configuration": {
            "windows": windows,
            "window_seconds": window_seconds,
            "workload": "diagnostic_sha256_v1",
            "protocol_sha256": sha256_file(protocol_path),
            "devices_sha256": sha256_file(devices_path),
        },
        "start_host_snapshot": start_snapshot,
        "end_host_snapshot": snapshot(repo_root),
        "files": {},
    }
    write_json(run_dir / "manifest.json", manifest)
    register_files(run_dir, ["events.csv", "telemetry.csv"])
    return run_dir

