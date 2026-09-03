from __future__ import annotations

import csv
import os
import time
from pathlib import Path
from typing import Any

from .platform_info import (
    cpu_frequency_hz,
    decode_throttled,
    memory_available_bytes,
    temperature_c,
    throttled_value,
)
from .util import utc_now


TELEMETRY_FIELDS = [
    "timestamp_utc",
    "monotonic_ns",
    "elapsed_s",
    "temperature_c",
    "throttled_hex",
    "throttled_value",
    "undervoltage_now",
    "arm_frequency_capped_now",
    "throttled_now",
    "soft_temperature_limit_now",
    "cpu_frequency_hz",
    "memory_available_bytes",
    "load_1m",
]


def collect_row(start_ns: int) -> dict[str, Any]:
    now_ns = time.monotonic_ns()
    throttle = throttled_value()
    flags = decode_throttled(throttle)
    return {
        "timestamp_utc": utc_now(),
        "monotonic_ns": now_ns,
        "elapsed_s": round((now_ns - start_ns) / 1e9, 6),
        "temperature_c": temperature_c(),
        "throttled_hex": None if throttle is None else hex(throttle),
        "throttled_value": throttle,
        "undervoltage_now": flags["undervoltage_now"],
        "arm_frequency_capped_now": flags["arm_frequency_capped_now"],
        "throttled_now": flags["throttled_now"],
        "soft_temperature_limit_now": flags["soft_temperature_limit_now"],
        "cpu_frequency_hz": cpu_frequency_hz(),
        "memory_available_bytes": memory_available_bytes(),
        "load_1m": os.getloadavg()[0],
    }


class TelemetryWriter:
    def __init__(self, path: Path, start_ns: int):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = path.open("w", encoding="utf-8", newline="")
        self._writer = csv.DictWriter(self._handle, fieldnames=TELEMETRY_FIELDS)
        self._writer.writeheader()
        self._start_ns = start_ns

    def sample(self) -> dict[str, Any]:
        row = collect_row(self._start_ns)
        self._writer.writerow(row)
        self._handle.flush()
        return row

    def close(self) -> None:
        self._handle.close()

    def __enter__(self) -> "TelemetryWriter":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
