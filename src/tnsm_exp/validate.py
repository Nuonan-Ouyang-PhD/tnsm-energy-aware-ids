from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any

from .util import read_json, utc_now, write_json


ACTIVE_THROTTLE_FIELDS = [
    "undervoltage_now",
    "arm_frequency_capped_now",
    "throttled_now",
    "soft_temperature_limit_now",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def verdict(name: str, passed: bool, observed: Any, expected: str) -> dict[str, Any]:
    return {"name": name, "passed": bool(passed), "observed": observed, "expected": expected}


def bool_is_false(raw: str) -> bool:
    return raw.strip().lower() in {"false", "0"}


def validate_smoke(run_dir: Path, expected_windows: int, temperature_limit_c: float) -> dict[str, Any]:
    events = read_csv(run_dir / "events.csv")
    telemetry = read_csv(run_dir / "telemetry.csv")
    manifest = read_json(run_dir / "manifest.json")
    event_ns = [int(row["window_start_monotonic_ns"]) for row in events]
    telemetry_ns = [int(row["monotonic_ns"]) for row in telemetry]
    temperatures = [float(row["temperature_c"]) for row in telemetry if row["temperature_c"]]
    throttle_values_present = all(
        row["throttled_hex"] and all(row[field] for field in ACTIVE_THROTTLE_FIELDS)
        for row in telemetry
    )
    active_flags_clean = all(
        bool_is_false(row[field])
        for row in telemetry
        for field in ACTIVE_THROTTLE_FIELDS
        if row[field]
    )
    start_throttle = manifest["start_host_snapshot"].get("throttled_hex")
    end_throttle = manifest["end_host_snapshot"].get("throttled_hex")
    source_commit = manifest.get("source_commit")
    checks = [
        verdict("paper_eligible_false", manifest.get("paper_eligible") is False, manifest.get("paper_eligible"), "false"),
        verdict(
            "source_commit_present",
            isinstance(source_commit, str) and re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None,
            source_commit,
            "40-character lowercase Git commit",
        ),
        verdict("event_count", len(events) == expected_windows, len(events), str(expected_windows)),
        verdict("telemetry_count", len(telemetry) == expected_windows, len(telemetry), str(expected_windows)),
        verdict(
            "event_sequence",
            [int(row["sequence"]) for row in events] == list(range(expected_windows)),
            len(events),
            "contiguous from zero",
        ),
        verdict("event_monotonic", all(a < b for a, b in zip(event_ns, event_ns[1:])), event_ns[:3], "strictly increasing"),
        verdict("telemetry_monotonic", all(a < b for a, b in zip(telemetry_ns, telemetry_ns[1:])), telemetry_ns[:3], "strictly increasing"),
        verdict("temperature_present", len(temperatures) == expected_windows, len(temperatures), str(expected_windows)),
        verdict(
            "temperature_limit",
            bool(temperatures) and max(temperatures) <= temperature_limit_c,
            max(temperatures) if temperatures else None,
            f"<= {temperature_limit_c}",
        ),
        verdict("throttle_telemetry_present", throttle_values_present, throttle_values_present, "all fields present"),
        verdict("active_throttle_flags", active_flags_clean, active_flags_clean, "all false"),
        verdict("start_throttled", start_throttle == "0x0", start_throttle, "0x0"),
        verdict("end_throttled", end_throttle == "0x0", end_throttle, "0x0"),
    ]
    result = {
        "schema_version": 1,
        "kind": "smoke_validation",
        "run_id": manifest.get("run_id"),
        "validated_at_utc": utc_now(),
        "paper_eligible": False,
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
    }
    write_json(run_dir / "validation.json", result)
    return result


FORMAL_REQUIRED_PATHS = [
    "artifacts/datasets/official_dataset_manifest.json",
    "artifacts/caches/shared_cache_manifest.json",
    "artifacts/models/model_registry.json",
    "artifacts/policies/policy_registry.json",
    "config/power_logger.json",
]


def formal_gate(repo_root: Path) -> dict[str, Any]:
    from .util import git_commit

    protocol = read_json(repo_root / "config" / "protocol.json")
    formal_enabled = protocol.get("formal", {}).get("enabled") is True
    source_commit = git_commit(repo_root)
    missing = [relative for relative in FORMAL_REQUIRED_PATHS if not (repo_root / relative).is_file()]
    checks = [
        verdict(
            "source_revision_available",
            isinstance(source_commit, str) and re.fullmatch(r"[0-9a-f]{40}", source_commit) is not None,
            source_commit,
            "40-character lowercase Git commit",
        ),
        verdict("formal_enabled", formal_enabled, formal_enabled, "true after protocol freeze"),
        verdict("required_artifacts", not missing, missing, "none missing"),
    ]
    return {
        "schema_version": 1,
        "kind": "formal_gate",
        "created_at_utc": utc_now(),
        "paper_eligible": False,
        "passed": all(item["passed"] for item in checks),
        "checks": checks,
    }
