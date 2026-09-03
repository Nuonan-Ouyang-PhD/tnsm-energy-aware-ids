from __future__ import annotations

import os
import platform
import re
import shutil
import socket
import time
from pathlib import Path
from typing import Any

from .util import run_text, utc_now


THROTTLE_BITS = {
    "undervoltage_now": 0,
    "arm_frequency_capped_now": 1,
    "throttled_now": 2,
    "soft_temperature_limit_now": 3,
    "undervoltage_occurred": 16,
    "arm_frequency_capped_occurred": 17,
    "throttled_occurred": 18,
    "soft_temperature_limit_occurred": 19,
}


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except (FileNotFoundError, PermissionError, OSError):
        return None


def model_name() -> str | None:
    return read_text(Path("/proc/device-tree/model"))


def memory_total_bytes() -> int:
    raw = read_text(Path("/proc/meminfo")) or ""
    match = re.search(r"^MemTotal:\s+(\d+)\s+kB$", raw, flags=re.MULTILINE)
    return int(match.group(1)) * 1024 if match else 0


def memory_available_bytes() -> int:
    raw = read_text(Path("/proc/meminfo")) or ""
    match = re.search(r"^MemAvailable:\s+(\d+)\s+kB$", raw, flags=re.MULTILINE)
    return int(match.group(1)) * 1024 if match else 0


def temperature_c() -> float | None:
    raw = read_text(Path("/sys/class/thermal/thermal_zone0/temp"))
    if raw:
        try:
            return float(raw) / 1000.0
        except ValueError:
            pass
    raw = run_text(["vcgencmd", "measure_temp"])
    if raw:
        match = re.search(r"(-?\d+(?:\.\d+)?)", raw)
        if match:
            return float(match.group(1))
    return None


def throttled_value() -> int | None:
    raw = run_text(["vcgencmd", "get_throttled"])
    if not raw:
        return None
    match = re.search(r"0x[0-9a-fA-F]+", raw)
    return int(match.group(0), 16) if match else None


def decode_throttled(value: int | None) -> dict[str, bool | None]:
    if value is None:
        return {name: None for name in THROTTLE_BITS}
    return {name: bool(value & (1 << bit)) for name, bit in THROTTLE_BITS.items()}


def cpu_frequency_hz() -> int | None:
    raw = read_text(Path("/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"))
    try:
        return int(raw) * 1000 if raw is not None else None
    except ValueError:
        return None


def cpu_governors() -> dict[str, str]:
    governors: dict[str, str] = {}
    root = Path("/sys/devices/system/cpu")
    for path in sorted(root.glob("cpu[0-9]*/cpufreq/scaling_governor")):
        value = read_text(path)
        if value:
            governors[path.parts[-3]] = value
    return governors


def ntp_synchronized() -> bool | None:
    raw = run_text(["timedatectl", "show", "--property=NTPSynchronized", "--value"])
    if raw is None:
        return None
    return raw.strip().lower() == "yes"


def disk_free_bytes(path: Path) -> int:
    return shutil.disk_usage(path).free


def snapshot(path_for_disk: Path) -> dict[str, Any]:
    throttle = throttled_value()
    return {
        "captured_at_utc": utc_now(),
        "monotonic_ns": time.monotonic_ns(),
        "hostname": socket.gethostname(),
        "fqdn": socket.getfqdn(),
        "hardware_model": model_name(),
        "architecture": platform.machine(),
        "kernel": platform.release(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "memory_total_bytes": memory_total_bytes(),
        "memory_available_bytes": memory_available_bytes(),
        "temperature_c": temperature_c(),
        "throttled_hex": None if throttle is None else hex(throttle),
        "throttle_flags": decode_throttled(throttle),
        "cpu_frequency_hz": cpu_frequency_hz(),
        "cpu_governors": cpu_governors(),
        "ntp_synchronized": ntp_synchronized(),
        "disk_free_bytes": disk_free_bytes(path_for_disk),
        "load_1m": os.getloadavg()[0],
    }

