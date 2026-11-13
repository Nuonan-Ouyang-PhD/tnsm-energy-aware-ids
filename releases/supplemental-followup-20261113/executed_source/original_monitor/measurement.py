"""POWER-Z KM003C ADC framing and conservative energy integration."""
from __future__ import annotations

import math
import struct


def request(sequence: int) -> bytes:
    return bytes(1) + struct.pack("<I", 12 | ((sequence % 256) << 8) | (1 << 17)) + bytes(60)


def decode(raw: bytes, sequence: int, baseline: float | None = None) -> dict[str, float]:
    if len(raw) != 64:
        raise ValueError("ADC reply length")
    header, attribute = struct.unpack_from("<II", raw)
    if header & 127 != 65 or (header >> 8) & 255 != sequence % 256 or attribute & 32767 != 1:
        raise ValueError("ADC reply type/id/attribute")
    microvolts, microamps = struct.unpack_from("<ii", raw, 16)
    volts = microvolts / 1e6
    signed_amps = microamps / 1e6
    consumed_amps = -signed_amps
    if not 4.75 <= volts <= 5.50:
        raise ValueError("run voltage envelope exceeded")
    if not 0 < consumed_amps <= 3:
        raise ValueError("unexpected current sign or range")
    if baseline is not None and abs(volts - baseline) > 0.30:
        raise ValueError("supply voltage shift")
    return {"volts": volts, "signed_amps": signed_amps, "consumed_amps": consumed_amps, "watts": volts * consumed_amps}


def integrate(samples: list[dict[str, float]]) -> tuple[float, float]:
    if len(samples) < 2:
        raise ValueError("insufficient samples")
    energy = 0.0
    for left, right in zip(samples, samples[1:]):
        dt = right["sample_monotonic"] - left["sample_monotonic"]
        if not 0 < dt <= 1.5:
            raise ValueError("invalid sample interval")
        if not math.isfinite(left["watts"]) or not math.isfinite(right["watts"]):
            raise ValueError("nonfinite power")
        energy += (left["watts"] + right["watts"]) * 0.5 * dt
    return energy, samples[-1]["sample_monotonic"] - samples[0]["sample_monotonic"]
