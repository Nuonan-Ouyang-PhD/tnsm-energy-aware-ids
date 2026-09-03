from __future__ import annotations

from pathlib import Path
from typing import Any

from .platform_info import snapshot
from .util import utc_now, write_json


GIB = 1024**3


def check(condition: bool, name: str, observed: Any, expected: str) -> dict[str, Any]:
    return {
        "name": name,
        "passed": bool(condition),
        "observed": observed,
        "expected": expected,
    }


def run_primary_preflight(repo_root: Path, output_path: Path) -> dict[str, Any]:
    host = snapshot(repo_root)
    model = host.get("hardware_model") or ""
    governors = host.get("cpu_governors") or {}
    checks = [
        check(host["hostname"] == "pi4b8g", "hostname", host["hostname"], "pi4b8g"),
        check("Raspberry Pi 4 Model B" in model, "hardware_model", model, "Raspberry Pi 4 Model B"),
        check(host["memory_total_bytes"] >= 7 * GIB, "memory", host["memory_total_bytes"], ">= 7 GiB"),
        check(host["architecture"] == "aarch64", "architecture", host["architecture"], "aarch64"),
        check(host["ntp_synchronized"] is True, "ntp_synchronized", host["ntp_synchronized"], "true"),
        check(host["temperature_c"] is not None, "temperature", host["temperature_c"], "readable"),
        check(host["throttled_hex"] == "0x0", "throttled", host["throttled_hex"], "0x0"),
        check(host["disk_free_bytes"] >= 5 * GIB, "disk_free", host["disk_free_bytes"], ">= 5 GiB"),
        check(
            bool(governors) and len(set(governors.values())) == 1,
            "cpu_governor_consistency",
            governors,
            "one value on all online cores",
        ),
    ]
    result = {
        "schema_version": 1,
        "kind": "primary_preflight",
        "created_at_utc": utc_now(),
        "device_id": "pi4b8g",
        "paper_eligible": False,
        "passed": all(item["passed"] for item in checks),
        "host_snapshot": host,
        "checks": checks,
    }
    write_json(output_path, result)
    return result

