from __future__ import annotations

import argparse
import json
from pathlib import Path

from .dataset_registry import inventory_csv_tree, register_acquisition
from .platform_info import snapshot
from .preflight import run_primary_preflight
from .quality_exceptions import register_quality_exceptions
from .smoke import register_files, run_smoke
from .util import read_json, repo_root_from_module, write_json
from .validate import formal_gate, validate_smoke


def emit(value: object) -> None:
    print(json.dumps(value, indent=2, sort_keys=True))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="TNSM experiment harness")
    parser.add_argument("--repo-root", type=Path, default=repo_root_from_module())
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("snapshot")
    subparsers.add_parser("preflight")
    subparsers.add_parser("smoke")
    validate_parser = subparsers.add_parser("validate-smoke")
    validate_parser.add_argument("run_dir", type=Path)
    register_parser = subparsers.add_parser("dataset-register")
    register_parser.add_argument("dataset_id", choices=["ton_iot", "ciciot2023", "n_baiot"])
    register_parser.add_argument("input_path", type=Path)
    inventory_parser = subparsers.add_parser("dataset-inventory")
    inventory_parser.add_argument("dataset_id", choices=["ton_iot", "ciciot2023", "n_baiot"])
    inventory_parser.add_argument("input_path", type=Path)
    exceptions_parser = subparsers.add_parser("dataset-quality-exceptions")
    exceptions_parser.add_argument("dataset_id", choices=["ton_iot", "ciciot2023", "n_baiot"])
    exceptions_parser.add_argument("input_path", type=Path)
    subparsers.add_parser("formal-gate")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    repo_root = args.repo_root.resolve()
    protocol = read_json(repo_root / "config" / "protocol.json")
    smoke_config = protocol["smoke"]

    if args.command == "snapshot":
        emit(snapshot(repo_root))
        return 0

    if args.command == "preflight":
        output = repo_root / "artifacts" / "preflight" / "pi4b8g_latest.json"
        result = run_primary_preflight(repo_root, output)
        emit(result)
        return 0 if result["passed"] else 2

    if args.command == "smoke":
        preflight_path = repo_root / "artifacts" / "preflight" / "pi4b8g_latest.json"
        preflight = run_primary_preflight(repo_root, preflight_path)
        if not preflight["passed"]:
            emit({"passed": False, "error": "Primary-device preflight failed", "preflight": preflight})
            return 2
        run_dir = run_smoke(
            repo_root,
            int(smoke_config["windows"]),
            float(smoke_config["window_seconds"]),
        )
        result = validate_smoke(
            run_dir,
            int(smoke_config["windows"]),
            float(smoke_config["temperature_limit_c"]),
        )
        register_files(run_dir, ["events.csv", "telemetry.csv", "validation.json"])
        emit({"run_dir": str(run_dir), "validation": result})
        return 0 if result["passed"] else 2

    if args.command == "validate-smoke":
        run_dir = args.run_dir.resolve()
        result = validate_smoke(
            run_dir,
            int(smoke_config["windows"]),
            float(smoke_config["temperature_limit_c"]),
        )
        register_files(run_dir, ["events.csv", "telemetry.csv", "validation.json"])
        emit(result)
        return 0 if result["passed"] else 2

    if args.command == "dataset-register":
        output_path, result = register_acquisition(
            repo_root,
            args.dataset_id,
            args.input_path,
        )
        emit({"output_path": str(output_path), "manifest": result})
        return 0

    if args.command == "dataset-inventory":
        output_path, result = inventory_csv_tree(
            repo_root,
            args.dataset_id,
            args.input_path,
        )
        emit({"output_path": str(output_path), "inventory": result})
        return 0 if result["all_rows_well_formed"] else 2

    if args.command == "dataset-quality-exceptions":
        output_path, result = register_quality_exceptions(
            repo_root,
            args.dataset_id,
            args.input_path,
        )
        emit({"output_path": str(output_path), "quality_exceptions": result})
        return 0

    if args.command == "formal-gate":
        result = formal_gate(repo_root)
        write_json(repo_root / "artifacts" / "reports" / "formal_gate_latest.json", result)
        emit(result)
        return 0 if result["passed"] else 3

    raise AssertionError(args.command)
