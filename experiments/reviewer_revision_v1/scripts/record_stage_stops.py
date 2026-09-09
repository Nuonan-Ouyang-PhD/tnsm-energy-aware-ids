"""Record predeclared unavailable-stage outcomes without improvising hardware."""
from __future__ import annotations

import json
from pathlib import Path
import shutil


ROOT = Path(__file__).resolve().parents[1]


def write_new(path: Path, value) -> None:
    if path.exists(): raise RuntimeError(f"record already exists: {path}")
    with path.open("x") as handle: json.dump(value, handle, indent=2, allow_nan=False); handle.write("\n")


def main() -> None:
    source = ROOT / "r0_source_audit" / "r3_state_stream_precondition.json"
    target = ROOT / "r3_controller_power" / "R3_NOT_EXECUTED.json"
    if target.exists(): raise RuntimeError("R3 stop record already exists")
    shutil.copy2(source, target)
    write_new(ROOT / "r4_threshold_and_reference" / "REFERENCE_LOAD_NOT_AVAILABLE.json", {
        "status": "REFERENCE_LOAD_NOT_AVAILABLE",
        "inventory_scope": "physically available equipment disclosed for this experiment",
        "available_measurement_device": "POWER-Z KM003C USB meter",
        "available_powered_device": "Raspberry Pi 4B and its user-verified official 5V/3A supply",
        "independently_specified_stable_usb_electronic_or_resistive_reference_load": False,
        "reason": "No independently specified electronic/resistive USB reference load was supplied or identified. The Pi and its supply are not a traceable reference load.",
        "action": "R4B not executed; no improvised calibration source used.",
    })
    print(json.dumps({"R3": "NOT_EXECUTED", "R4B": "REFERENCE_LOAD_NOT_AVAILABLE"}))


if __name__ == "__main__": main()
