#!/usr/bin/env python3
"""Build the scheduler resource-cost registry from existing evidence only.

This program performs no hardware access and no new measurement.  It verifies
the two source archives, reads the accepted 15-profile summary, the Pi timing
report, and the artifact/input manifests, then writes deterministic CSV/JSON
registries.  It deliberately leaves cross-cadence energy-per-batch, switching,
first-batch, and thermal-response costs unmeasured.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import sys
import zipfile
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


ARTICLE_ARCHIVE_SHA256 = (
    "c135da2db921dc442b4fbea7bd2596aaef8f1eda2f553945d400168d77375c74"
)
SOFTWARE_ARCHIVE_SHA256 = (
    "38c90b995d58e63c3c2149de99a6dde0dcd8f968322fb87dbcf960ccb34e4318"
)
PI_INPUT_MANIFEST_SHA256 = (
    "0840fdad15ee5f3fa0e3cd7de3d726d2f48a8d0002c9267346091baaf3f4016a"
)

ARTICLE_ROOT = "TNSM_ARTICLE_DATA_20260907_V1"
SOFTWARE_ROOT = "tnsm_software_experiment_evidence_v1"
DATASETS = ("ton_iot", "ciciot2023", "n_baiot")
MODELS = ("TinyDT", "LightLR", "MedRF", "HeavyMLP")
MODEL_FILENAMES = {
    "TinyDT": "TinyDT.joblib",
    "LightLR": "LightLR.joblib",
    "MedRF": "MedRF.joblib",
    "HeavyMLP": "HeavyMLP.pt",
}
T95_DF2 = 4.3026527299

PROFILE_MEMBER = "summary/physical_static_profiles.csv"
POWER_AGGREGATE_MEMBER = "summary/physical_static_aggregates.csv"
PI_REPORT_MEMBER = "raw/software/execution/pi_inference_report.json"
PI_SNAPSHOT_MEMBER = "raw/software/execution/pi_readonly_snapshot.json"
ARTICLE_MANIFEST_MEMBER = "MANIFEST_SHA256.txt"
PI_INPUT_MANIFEST_MEMBER = "pi_check_bundle/inputs_manifest.json"

CSV_FIELDS = [
    "entry_id",
    "dataset",
    "model",
    "device",
    "model_artifact_sha256",
    "preprocessor_sha256",
    "pi_timing_input_sha256",
    "physical_power_input_sha256",
    "resident_input_bundle_sha256",
    "batch_size_rows",
    "physical_active_rows_per_second",
    "physical_cadence",
    "pi_timing_cadence",
    "target_scheduler_residency_semantics",
    "scheduler_residency_evidence_status",
    "power_residency_semantics",
    "pi_timing_residency_semantics",
    "power_measurement_point",
    "latency_measurement_point",
    "power_evidence_status",
    "power_aggregate_status",
    "power_repeats",
    "mean_watts",
    "sd_watts",
    "mean_watts_ci95_low",
    "mean_watts_ci95_high",
    "mean_energy_joules_30min",
    "increment_vs_matched_idle_status",
    "mean_increment_vs_matched_idle_watts",
    "increment_sd_watts",
    "increment_ci95_low",
    "increment_ci95_high",
    "scheduled_1hz_latency_status",
    "scheduled_1hz_batch_ms_mean_of_run_medians",
    "scheduled_1hz_batch_ms_sd_of_run_medians",
    "scheduled_1hz_batch_ms_ci95_low",
    "scheduled_1hz_batch_ms_ci95_high",
    "tight_loop_latency_status",
    "tight_loop_batch_ms_median",
    "tight_loop_batch_ms_p95",
    "tight_loop_timing_loops",
    "scheduler_latency_applicability",
    "energy_per_batch_status",
    "switch_latency_status",
    "first_batch_latency_status",
    "temperature_observation_status",
    "static_temperature_min_c",
    "static_temperature_max_c",
    "temperature_response_status",
    "uncertainty",
]


class RegistryError(RuntimeError):
    """Evidence is absent, inconsistent, or outside the fixed contract."""


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def require_equal(observed: Any, expected: Any, label: str) -> None:
    if observed != expected:
        raise RegistryError(f"{label}: expected {expected!r}, observed {observed!r}")


def read_json_bytes(data: bytes, label: str) -> Any:
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryError(f"invalid JSON in {label}: {exc}") from exc


def read_csv_bytes(data: bytes, label: str) -> list[dict[str, str]]:
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise RegistryError(f"invalid UTF-8 in {label}: {exc}") from exc
    return list(csv.DictReader(io.StringIO(text, newline="")))


def article_member(archive: zipfile.ZipFile, relative: str) -> bytes:
    name = f"{ARTICLE_ROOT}/{relative}"
    try:
        return archive.read(name)
    except KeyError as exc:
        raise RegistryError(f"article archive member missing: {relative}") from exc


def parse_manifest(data: bytes) -> dict[str, str]:
    result: dict[str, str] = {}
    for line_number, raw in enumerate(data.decode("utf-8").splitlines(), start=1):
        digest, separator, relative = raw.partition("  ")
        if separator != "  " or len(digest) != 64 or not relative or relative in result:
            raise RegistryError(f"invalid article MANIFEST line {line_number}")
        result[relative] = digest
    return result


def verified_article_member(
    archive: zipfile.ZipFile, manifest: Mapping[str, str], relative: str
) -> bytes:
    data = article_member(archive, relative)
    if relative not in manifest:
        raise RegistryError(f"article MANIFEST does not cover: {relative}")
    require_equal(sha256_bytes(data), manifest[relative], f"article member {relative}")
    return data


def as_int(value: str, label: str) -> int:
    try:
        return int(value)
    except ValueError as exc:
        raise RegistryError(f"{label} is not an integer: {value!r}") from exc


def as_float(value: str, label: str) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise RegistryError(f"{label} is not numeric: {value!r}") from exc
    if not math.isfinite(result):
        raise RegistryError(f"{label} is not finite")
    return result


def optional_float(value: str, label: str) -> float | None:
    return None if value == "" else as_float(value, label)


def mean_sd_t95(values: Sequence[float]) -> dict[str, float | int]:
    if len(values) != 3:
        raise RegistryError(f"three observations required, found {len(values)}")
    mean = statistics.fmean(values)
    sd = statistics.stdev(values)
    half_width = T95_DF2 * sd / math.sqrt(len(values))
    return {
        "n": len(values),
        "mean": mean,
        "sd": sd,
        "ci95_low": mean - half_width,
        "ci95_high": mean + half_width,
    }


def percentile(values: Sequence[float], quantile: float) -> float:
    if not values or not 0 <= quantile <= 1:
        raise RegistryError("invalid percentile input")
    ordered = sorted(values)
    position = (len(ordered) - 1) * quantile
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return ordered[lower]
    return ordered[lower] * (upper - position) + ordered[upper] * (position - lower)


def summarize_telemetry(data: bytes, label: str) -> dict[str, Any]:
    try:
        text = data.decode("utf-8")
    except UnicodeError as exc:
        raise RegistryError(f"invalid telemetry UTF-8 in {label}: {exc}") from exc
    temperatures: list[float] = []
    inference_ms: list[float] = []
    window_indices: list[int] = []
    window_rows: set[int] = set()
    throttles: set[str] = set()
    for line_number, line in enumerate(text.splitlines(), start=1):
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RegistryError(f"invalid telemetry JSON {label}:{line_number}") from exc
        if "temperature_c" in record:
            temperatures.append(float(record["temperature_c"]))
        if "throttled" in record:
            throttles.add(str(record["throttled"]))
        if record.get("event") == "window":
            window_indices.append(int(record["index"]))
            window_rows.add(int(record["rows"]))
            inference_ms.append(float(record["inference_ns"]) / 1_000_000)
    if not temperatures or not inference_ms:
        raise RegistryError(f"telemetry lacks required observations: {label}")
    return {
        "window_count": len(window_indices),
        "window_indices_sequential": window_indices == list(range(len(window_indices))),
        "window_rows": sorted(window_rows),
        "temperature_min_c": min(temperatures),
        "temperature_max_c": max(temperatures),
        "inference_batch_ms_median": statistics.median(inference_ms),
        "inference_batch_ms_p95": percentile(inference_ms, 0.95),
        "throttle_values": sorted(throttles),
    }


def canonical_hash(value: Any) -> str:
    data = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return sha256_bytes(data)


def nullable(value: Any) -> Any:
    return "" if value is None else value


def flatten_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    artifact = entry.get("artifact") or {}
    preprocessing = entry.get("preprocessing") or {}
    inputs = entry["inputs"]
    power = entry["power"]
    scheduled = entry["scheduled_1hz_latency"]
    tight = entry["tight_loop_latency"]
    gaps = entry["gaps"]
    temperature = entry["temperature"]
    uncertainty = entry["uncertainty"]
    return {
        "entry_id": entry["entry_id"],
        "dataset": entry["dataset"],
        "model": entry["model"],
        "device": entry["device"],
        "model_artifact_sha256": nullable(artifact.get("sha256")),
        "preprocessor_sha256": nullable(preprocessing.get("sha256")),
        "pi_timing_input_sha256": nullable(inputs.get("pi_check_X_sha256")),
        "physical_power_input_sha256": nullable(inputs.get("physical_train_X_sha256")),
        "resident_input_bundle_sha256": nullable(
            inputs.get("resident_input_bundle_sha256")
        ),
        "batch_size_rows": entry["batch_size_rows"],
        "physical_active_rows_per_second": nullable(
            entry["physical_active_rows_per_second"]
        ),
        "physical_cadence": entry["physical_cadence"],
        "pi_timing_cadence": entry["pi_timing_cadence"],
        "target_scheduler_residency_semantics": entry[
            "target_scheduler_residency_semantics"
        ],
        "scheduler_residency_evidence_status": entry[
            "scheduler_residency_evidence_status"
        ],
        "power_residency_semantics": entry["power_residency_semantics"],
        "pi_timing_residency_semantics": entry["pi_timing_residency_semantics"],
        "power_measurement_point": entry["power_measurement_point"],
        "latency_measurement_point": entry["latency_measurement_point"],
        "power_evidence_status": power["evidence_status"],
        "power_aggregate_status": power["aggregate_status"],
        "power_repeats": nullable(power.get("repeats")),
        "mean_watts": nullable(power.get("mean_watts")),
        "sd_watts": nullable(power.get("sd_watts")),
        "mean_watts_ci95_low": nullable(power.get("ci95_low_watts")),
        "mean_watts_ci95_high": nullable(power.get("ci95_high_watts")),
        "mean_energy_joules_30min": nullable(
            power.get("mean_energy_joules_30min")
        ),
        "increment_vs_matched_idle_status": power["increment_status"],
        "mean_increment_vs_matched_idle_watts": nullable(
            power.get("mean_increment_watts")
        ),
        "increment_sd_watts": nullable(power.get("increment_sd_watts")),
        "increment_ci95_low": nullable(power.get("increment_ci95_low_watts")),
        "increment_ci95_high": nullable(power.get("increment_ci95_high_watts")),
        "scheduled_1hz_latency_status": scheduled["status"],
        "scheduled_1hz_batch_ms_mean_of_run_medians": nullable(
            scheduled.get("mean_of_run_medians_ms")
        ),
        "scheduled_1hz_batch_ms_sd_of_run_medians": nullable(
            scheduled.get("sd_of_run_medians_ms")
        ),
        "scheduled_1hz_batch_ms_ci95_low": nullable(scheduled.get("ci95_low_ms")),
        "scheduled_1hz_batch_ms_ci95_high": nullable(scheduled.get("ci95_high_ms")),
        "tight_loop_latency_status": tight["status"],
        "tight_loop_batch_ms_median": nullable(tight.get("batch_ms_median")),
        "tight_loop_batch_ms_p95": nullable(tight.get("batch_ms_p95")),
        "tight_loop_timing_loops": nullable(tight.get("timing_loops")),
        "scheduler_latency_applicability": tight["scheduler_applicability"],
        "energy_per_batch_status": gaps["energy_per_batch_status"],
        "switch_latency_status": gaps["switch_latency_status"],
        "first_batch_latency_status": gaps["first_batch_latency_status"],
        "temperature_observation_status": temperature["observation_status"],
        "static_temperature_min_c": nullable(temperature.get("static_min_c")),
        "static_temperature_max_c": nullable(temperature.get("static_max_c")),
        "temperature_response_status": temperature["response_status"],
        "uncertainty": uncertainty["summary"],
    }


def write_outputs(output_dir: Path, registry: Mapping[str, Any]) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "cost_registry.json"
    csv_path = output_dir / "cost_registry.csv"
    json_path.write_text(
        json.dumps(registry, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS, lineterminator="\n")
        writer.writeheader()
        for entry in registry["entries"]:
            writer.writerow(flatten_entry(entry))


def build_registry(article_path: Path, software_path: Path) -> dict[str, Any]:
    require_equal(
        sha256_file(article_path), ARTICLE_ARCHIVE_SHA256, "article archive SHA-256"
    )
    require_equal(
        sha256_file(software_path), SOFTWARE_ARCHIVE_SHA256, "software archive SHA-256"
    )

    with zipfile.ZipFile(article_path) as article:
        manifest_bytes = article_member(article, ARTICLE_MANIFEST_MEMBER)
        manifest = parse_manifest(manifest_bytes)
        profile_bytes = verified_article_member(article, manifest, PROFILE_MEMBER)
        aggregate_bytes = verified_article_member(
            article, manifest, POWER_AGGREGATE_MEMBER
        )
        pi_report_bytes = verified_article_member(article, manifest, PI_REPORT_MEMBER)
        pi_snapshot_bytes = verified_article_member(article, manifest, PI_SNAPSHOT_MEMBER)
        profile_rows = read_csv_bytes(profile_bytes, PROFILE_MEMBER)
        aggregate_rows = read_csv_bytes(aggregate_bytes, POWER_AGGREGATE_MEMBER)
        pi_report = read_json_bytes(pi_report_bytes, PI_REPORT_MEMBER)
        pi_snapshot = read_json_bytes(pi_snapshot_bytes, PI_SNAPSHOT_MEMBER)

        artifact_records: dict[str, dict[str, dict[str, str]]] = {}
        for dataset in DATASETS:
            artifact_records[dataset] = {}
            for model in MODELS:
                relative = (
                    f"raw/software/results/{dataset}/{MODEL_FILENAMES[model]}"
                )
                data = verified_article_member(article, manifest, relative)
                artifact_records[dataset][model] = {
                    "archive_member": relative,
                    "sha256": sha256_bytes(data),
                }
            relative = f"raw/software/results/{dataset}/preprocessor.joblib"
            data = verified_article_member(article, manifest, relative)
            artifact_records[dataset]["preprocessor"] = {
                "archive_member": relative,
                "sha256": sha256_bytes(data),
            }

        physical_manifests: dict[str, dict[str, str]] = {}
        physical_manifest_hashes: dict[str, str] = {}
        for version in ("v1", "v2", "v3"):
            relative = f"raw/physical/{version}/inputs_manifest.json"
            data = verified_article_member(article, manifest, relative)
            physical_manifests[version] = read_json_bytes(data, relative)
            physical_manifest_hashes[version] = sha256_bytes(data)

        run_evidence: dict[str, dict[str, Any]] = {}
        for row in profile_rows:
            summary_relative = (
                f"raw/physical/{row['source_version']}/execution/"
                f"{row['run_id']}/summary.json"
            )
            telemetry_relative = summary_relative.replace(
                "/summary.json", "/pi_telemetry.jsonl"
            )
            power_relative = summary_relative.replace("/summary.json", "/power.jsonl")
            summary_data = verified_article_member(article, manifest, summary_relative)
            telemetry_data = verified_article_member(article, manifest, telemetry_relative)
            power_data = verified_article_member(article, manifest, power_relative)
            run_evidence[row["run_id"]] = {
                "summary": read_json_bytes(summary_data, summary_relative),
                "summary_sha256": sha256_bytes(summary_data),
                "telemetry_sha256": sha256_bytes(telemetry_data),
                "power_sha256": sha256_bytes(power_data),
                "telemetry": summarize_telemetry(telemetry_data, telemetry_relative),
            }

    with zipfile.ZipFile(software_path) as software:
        name = f"{SOFTWARE_ROOT}/{PI_INPUT_MANIFEST_MEMBER}"
        try:
            pi_input_manifest_bytes = software.read(name)
        except KeyError as exc:
            raise RegistryError(f"software archive member missing: {name}") from exc
    require_equal(
        sha256_bytes(pi_input_manifest_bytes),
        PI_INPUT_MANIFEST_SHA256,
        "Pi input manifest SHA-256",
    )
    pi_input_manifest = read_json_bytes(
        pi_input_manifest_bytes, PI_INPUT_MANIFEST_MEMBER
    )

    require_equal(len(profile_rows), 15, "valid physical profile count")
    expected_profiles = {"idle", *MODELS}
    profile_groups: dict[str, list[dict[str, Any]]] = {
        profile: [] for profile in expected_profiles
    }
    segment_records: list[dict[str, Any]] = []
    seen_runs: set[str] = set()
    for row in profile_rows:
        run_id = row["run_id"]
        profile = row["profile"]
        if run_id in seen_runs or profile not in expected_profiles:
            raise RegistryError(f"duplicate or unexpected physical profile: {run_id}")
        seen_runs.add(run_id)
        require_equal(row["status"], "PASS", f"{run_id} status")
        require_equal(as_int(row["power_samples"], run_id), 1801, f"{run_id} samples")
        require_equal(
            as_int(row["telemetry_windows"], run_id), 1800, f"{run_id} windows"
        )
        require_equal(row["throttle_values"], "throttled=0x0", f"{run_id} throttle")
        evidence = run_evidence[run_id]
        run_summary = evidence["summary"]
        require_equal(run_summary["status"], "PASS", f"{run_id} summary status")
        require_equal(run_summary["run_id"], run_id, f"{run_id} summary identity")
        require_equal(run_summary["model"], profile, f"{run_id} summary profile")
        require_equal(
            int(run_summary["repetition"]),
            as_int(row["repetition"], f"{run_id} repetition"),
            f"{run_id} summary repetition",
        )
        require_equal(
            int(run_summary["power_samples"]), 1801, f"{run_id} summary power count"
        )
        require_equal(
            int(run_summary["telemetry_windows"]),
            1800,
            f"{run_id} summary telemetry count",
        )
        for summary_key, csv_key in (
            ("observed_duration_seconds", "duration_seconds"),
            ("energy_joules", "energy_joules"),
            ("mean_watts", "mean_watts"),
            ("voltage_min", "voltage_min"),
            ("voltage_max", "voltage_max"),
        ):
            if not math.isclose(
                float(run_summary[summary_key]),
                as_float(row[csv_key], f"{run_id} {csv_key}"),
                rel_tol=0,
                abs_tol=1e-12,
            ):
                raise RegistryError(f"{run_id} accepted summary {summary_key} mismatch")
        require_equal(evidence["power_sha256"], row["power_sha256"], f"{run_id} power")
        require_equal(
            evidence["telemetry_sha256"], row["telemetry_sha256"], f"{run_id} telemetry"
        )
        telemetry = evidence["telemetry"]
        require_equal(telemetry["window_count"], 1800, f"{run_id} telemetry count")
        require_equal(
            telemetry["window_indices_sequential"], True, f"{run_id} window sequence"
        )
        require_equal(
            telemetry["window_rows"], [0] if profile == "idle" else [100],
            f"{run_id} rows per window",
        )
        require_equal(
            telemetry["throttle_values"], ["throttled=0x0"], f"{run_id} telemetry throttle"
        )
        telemetry_checks = (
            ("temperature_min_c", "temperature_min_c"),
            ("temperature_max_c", "temperature_max_c"),
            ("inference_batch_ms_median", "inference_batch_ms_median"),
            ("inference_batch_ms_p95", "inference_batch_ms_p95"),
        )
        for telemetry_key, csv_key in telemetry_checks:
            observed = telemetry[telemetry_key]
            expected = optional_float(row[csv_key], f"{run_id} {csv_key}")
            if expected is None or not math.isclose(
                observed, expected, rel_tol=0, abs_tol=1e-12
            ):
                raise RegistryError(f"{run_id} telemetry-derived {csv_key} mismatch")
        parsed = {
            "run_id": run_id,
            "repetition": as_int(row["repetition"], f"{run_id} repetition"),
            "profile": profile,
            "source_version": row["source_version"],
            "status": "PASS",
            "batch_size_rows": 100,
            "active_rows_per_second": 0 if profile == "idle" else 100,
            "duration_seconds": as_float(row["duration_seconds"], run_id),
            "power_samples": 1801,
            "telemetry_windows": 1800,
            "energy_joules": as_float(row["energy_joules"], run_id),
            "mean_watts": as_float(row["mean_watts"], run_id),
            "voltage_min": as_float(row["voltage_min"], run_id),
            "voltage_max": as_float(row["voltage_max"], run_id),
            "temperature_min_c": as_float(row["temperature_min_c"], run_id),
            "temperature_max_c": as_float(row["temperature_max_c"], run_id),
            "inference_batch_ms_median": optional_float(
                row["inference_batch_ms_median"], run_id
            ),
            "inference_batch_ms_p95": optional_float(
                row["inference_batch_ms_p95"], run_id
            ),
            "power_sha256": row["power_sha256"],
            "telemetry_sha256": row["telemetry_sha256"],
            "summary_sha256": evidence["summary_sha256"],
            "source_member_prefix": (
                f"raw/physical/{row['source_version']}/execution/{run_id}"
            ),
            "evidence_status": "measured",
            "telemetry_summary_status": "derived",
        }
        profile_groups[profile].append(parsed)
        segment_records.append(parsed)
    for profile, rows in profile_groups.items():
        require_equal(len(rows), 3, f"{profile} physical repetition count")
        require_equal(
            sorted(row["repetition"] for row in rows),
            [1, 2, 3],
            f"{profile} repetition identities",
        )
    segment_records.sort(key=lambda row: (row["repetition"], row["run_id"]))

    aggregate_by_profile = {row["profile"]: row for row in aggregate_rows}
    require_equal(set(aggregate_by_profile), expected_profiles, "aggregate profiles")
    for profile, row in aggregate_by_profile.items():
        require_equal(as_int(row["repeats"], profile), 3, f"{profile} aggregate n")
        recomputed = mean_sd_t95(
            [segment["mean_watts"] for segment in profile_groups[profile]]
        )
        for key, csv_key in (
            ("mean", "mean_watts"),
            ("sd", "sd_watts"),
            ("ci95_low", "mean_watts_ci95_low"),
            ("ci95_high", "mean_watts_ci95_high"),
        ):
            observed = as_float(row[csv_key], f"{profile} {csv_key}")
            if not math.isclose(observed, float(recomputed[key]), rel_tol=0, abs_tol=1e-12):
                raise RegistryError(f"{profile} aggregate differs from 15-profile evidence")
        energy_mean = statistics.fmean(
            segment["energy_joules"] for segment in profile_groups[profile]
        )
        if not math.isclose(
            as_float(row["mean_energy_joules_30min"], profile),
            energy_mean,
            rel_tol=0,
            abs_tol=1e-9,
        ):
            raise RegistryError(f"{profile} aggregate energy differs from profile evidence")

    idle_by_repetition = {
        segment["repetition"]: segment["mean_watts"]
        for segment in profile_groups["idle"]
    }
    for profile, row in aggregate_by_profile.items():
        increments = (
            [0.0, 0.0, 0.0]
            if profile == "idle"
            else [
                segment["mean_watts"] - idle_by_repetition[segment["repetition"]]
                for segment in profile_groups[profile]
            ]
        )
        recomputed = mean_sd_t95(increments)
        for key, csv_key in (
            ("mean", "mean_increment_vs_matched_idle_watts"),
            ("sd", "increment_sd_watts"),
            ("ci95_low", "increment_ci95_low"),
            ("ci95_high", "increment_ci95_high"),
        ):
            observed = as_float(row[csv_key], f"{profile} {csv_key}")
            if not math.isclose(observed, float(recomputed[key]), rel_tol=0, abs_tol=1e-12):
                raise RegistryError(
                    f"{profile} matched-idle aggregate differs from profile evidence"
                )

    require_equal(pi_report.get("status"), "PASS", "Pi timing report status")
    require_equal(pi_report.get("meter_used"), False, "Pi timing meter_used")
    require_equal(
        pi_report.get("paper_energy_result"), False, "Pi timing energy boundary"
    )
    require_equal(set(pi_report["datasets"]), set(DATASETS), "Pi timing datasets")
    for dataset in DATASETS:
        require_equal(
            set(pi_report["datasets"][dataset]), set(MODELS), f"{dataset} Pi models"
        )
        for model in MODELS:
            timing = pi_report["datasets"][dataset][model]
            require_equal(timing["batch_size"], 100, f"{dataset}/{model} batch size")
            require_equal(timing["timing_loops"], 1000, f"{dataset}/{model} loops")
            require_equal(timing["warmup_loops"], 20, f"{dataset}/{model} warmups")
            require_equal(
                timing["label_disagreements"], 0, f"{dataset}/{model} parity"
            )
            duration_ms = [float(value) / 1_000_000 for value in timing["durations_ns"]]
            require_equal(len(duration_ms), 1000, f"{dataset}/{model} duration count")
            if not math.isclose(
                statistics.median(duration_ms),
                float(timing["batch_ms_median"]),
                rel_tol=0,
                abs_tol=1e-12,
            ):
                raise RegistryError(f"{dataset}/{model} timing median mismatch")
            if not math.isclose(
                percentile(duration_ms, 0.95),
                float(timing["batch_ms_p95"]),
                rel_tol=0,
                abs_tol=1e-12,
            ):
                raise RegistryError(f"{dataset}/{model} timing p95 mismatch")

    common_physical_inputs = {
        key: value
        for key, value in physical_manifests["v1"].items()
        if key != "profile_worker.py"
    }
    for version in ("v2", "v3"):
        require_equal(
            {
                key: value
                for key, value in physical_manifests[version].items()
                if key != "profile_worker.py"
            },
            common_physical_inputs,
            f"{version} physical model/input identity",
        )
    require_equal(
        set(common_physical_inputs),
        {
            "inputs/HeavyMLP.pt",
            "inputs/LightLR.joblib",
            "inputs/MedRF.joblib",
            "inputs/TinyDT.joblib",
            "inputs/train_X.npy",
            "inputs/train_ids.npy",
            "inputs/train_predictions.npy",
        },
        "physical input manifest keys",
    )
    for model in MODELS:
        require_equal(
            common_physical_inputs[f"inputs/{MODEL_FILENAMES[model]}"],
            artifact_records["ton_iot"][model]["sha256"],
            f"TON physical/software artifact {model}",
        )
    for dataset in DATASETS:
        for model in MODELS:
            require_equal(
                pi_input_manifest[
                    f"inputs/{dataset}/{MODEL_FILENAMES[model]}"
                ],
                artifact_records[dataset][model]["sha256"],
                f"{dataset}/{model} Pi/software artifact",
            )

    snapshot_stdout = pi_snapshot.get("stdout")
    if not isinstance(snapshot_stdout, str):
        raise RegistryError("Pi snapshot stdout missing")
    snapshot = read_json_bytes(snapshot_stdout.encode("utf-8"), "Pi snapshot stdout")
    require_equal(snapshot["architecture"], "aarch64", "Pi architecture")
    if not snapshot["hardware_model"].startswith("Raspberry Pi 4 Model B Rev 1.5"):
        raise RegistryError("unexpected Pi hardware model")

    resident_bundle_sha = canonical_hash(common_physical_inputs)
    entries: list[dict[str, Any]] = []
    for dataset in DATASETS:
        for model in MODELS:
            power_available = dataset == "ton_iot"
            if power_available:
                agg = aggregate_by_profile[model]
                power: dict[str, Any] = {
                    "evidence_status": "measured",
                    "aggregate_status": "derived",
                    "repeats": 3,
                    "mean_watts": as_float(agg["mean_watts"], model),
                    "sd_watts": as_float(agg["sd_watts"], model),
                    "ci95_low_watts": as_float(agg["mean_watts_ci95_low"], model),
                    "ci95_high_watts": as_float(agg["mean_watts_ci95_high"], model),
                    "mean_energy_joules_30min": as_float(
                        agg["mean_energy_joules_30min"], model
                    ),
                    "increment_status": "derived",
                    "mean_increment_watts": as_float(
                        agg["mean_increment_vs_matched_idle_watts"], model
                    ),
                    "increment_sd_watts": as_float(agg["increment_sd_watts"], model),
                    "increment_ci95_low_watts": as_float(
                        agg["increment_ci95_low"], model
                    ),
                    "increment_ci95_high_watts": as_float(
                        agg["increment_ci95_high"], model
                    ),
                    "scope": agg["measurement_scope"],
                }
                latency_summary = mean_sd_t95(
                    [
                        float(row["inference_batch_ms_median"])
                        for row in profile_groups[model]
                    ]
                )
                scheduled_latency: dict[str, Any] = {
                    "status": "derived",
                    "source_status": "measured",
                    "repeats": 3,
                    "mean_of_run_medians_ms": latency_summary["mean"],
                    "sd_of_run_medians_ms": latency_summary["sd"],
                    "ci95_low_ms": latency_summary["ci95_low"],
                    "ci95_high_ms": latency_summary["ci95_high"],
                    "cadence": "one selected-model batch of 100 encoded rows per second",
                }
                temperature = {
                    "observation_status": "measured",
                    "static_min_c": min(
                        row["temperature_min_c"] for row in profile_groups[model]
                    ),
                    "static_max_c": max(
                        row["temperature_max_c"] for row in profile_groups[model]
                    ),
                    "response_status": "unmeasured",
                    "response_note": (
                        "Observed light-load temperatures are not a calibrated thermal "
                        "response curve and do not establish hot-condition safety."
                    ),
                }
                physical_input_sha = common_physical_inputs["inputs/train_X.npy"]
                active_rows_per_second: int | None = 100
                physical_cadence = (
                    "measured: 1800 seconds; one successive 100-row encoded TON batch "
                    "per second after all four models were loaded and warmed"
                )
                power_residency = (
                    "measured with TinyDT, LightLR, MedRF, and HeavyMLP all resident "
                    "and warmed; only the named model was invoked each second"
                )
                uncertainty_summary = (
                    "Power and matched-idle increment: n=3 sequential profiles, sample "
                    "SD and two-sided Student-t 95% CI (df=2); single Pi and uncalibrated "
                    "meter. Scheduled latency: same n=3 treatment of run medians. Tight-"
                    "loop latency: empirical median/p95 from one 1000-call session only."
                )
            else:
                power = {
                    "evidence_status": "unmeasured",
                    "aggregate_status": "unmeasured",
                    "repeats": None,
                    "mean_watts": None,
                    "sd_watts": None,
                    "ci95_low_watts": None,
                    "ci95_high_watts": None,
                    "mean_energy_joules_30min": None,
                    "increment_status": "unmeasured",
                    "mean_increment_watts": None,
                    "increment_sd_watts": None,
                    "increment_ci95_low_watts": None,
                    "increment_ci95_high_watts": None,
                    "scope": None,
                    "note": "TON-IoT static power is not relabeled as this dataset's power.",
                }
                scheduled_latency = {
                    "status": "unmeasured",
                    "source_status": "unmeasured",
                    "repeats": None,
                    "mean_of_run_medians_ms": None,
                    "sd_of_run_medians_ms": None,
                    "ci95_low_ms": None,
                    "ci95_high_ms": None,
                    "cadence": None,
                }
                temperature = {
                    "observation_status": "unmeasured",
                    "static_min_c": None,
                    "static_max_c": None,
                    "response_status": "unmeasured",
                    "response_note": "No dataset-specific static power/thermal profile exists.",
                }
                physical_input_sha = None
                active_rows_per_second = None
                physical_cadence = "unmeasured for this dataset"
                power_residency = "unmeasured for this dataset"
                uncertainty_summary = (
                    "No dataset-specific physical power, scheduled 1 Hz latency, or "
                    "temperature-response uncertainty is available. Tight-loop latency "
                    "has empirical median/p95 from one 1000-call session, with no "
                    "independent-run confidence interval."
                )

            timing = pi_report["datasets"][dataset][model]
            entries.append(
                {
                    "entry_id": f"{dataset}/{model}",
                    "dataset": dataset,
                    "model": model,
                    "device": "Raspberry Pi 4 Model B Rev 1.5, 8 GB, aarch64",
                    "artifact": artifact_records[dataset][model],
                    "preprocessing": {
                        **artifact_records[dataset]["preprocessor"],
                        "execution_status": (
                            "not executed inside either timing or static power window; "
                            "inputs were already encoded"
                        ),
                    },
                    "inputs": {
                        "pi_check_X_sha256": pi_input_manifest[
                            f"inputs/{dataset}/check_X.npy"
                        ],
                        "pi_reference_predictions_sha256": pi_input_manifest[
                            f"inputs/{dataset}/check_predictions.npy"
                        ],
                        "physical_train_X_sha256": physical_input_sha,
                        "resident_input_bundle_sha256": (
                            resident_bundle_sha if power_available else None
                        ),
                    },
                    "batch_size_rows": 100,
                    "physical_active_rows_per_second": active_rows_per_second,
                    "physical_cadence": physical_cadence,
                    "pi_timing_cadence": (
                        "measured in a tight loop: 20 warmups then 1000 consecutive "
                        "100-row encoded-input predict calls; no one-second pacing"
                    ),
                    "target_scheduler_residency_semantics": (
                        "all four dataset-specific models stay loaded; an action switch "
                        "selects an already resident model and does not load or unload it"
                    ),
                    "scheduler_residency_evidence_status": (
                        "measured" if power_available else "unmeasured"
                    ),
                    "power_residency_semantics": power_residency,
                    "pi_timing_residency_semantics": (
                        "models were loaded and timed sequentially; the Pi timing report "
                        "does not measure all-four-resident switching"
                    ),
                    "power_measurement_point": (
                        "POWER-Z KM003C at the Pi USB input/load side, sampled at 1 Hz; "
                        "not AC-wall power"
                        if power_available
                        else "unmeasured for this dataset; no measurement point applies"
                    ),
                    "latency_measurement_point": (
                        "inside the model predict call on the Pi CPU over an encoded "
                        "in-memory 100-row batch; excludes preprocessing, file/network "
                        "I/O, packet capture, feature extraction, and end-to-end IDS delay"
                    ),
                    "power": power,
                    "scheduled_1hz_latency": scheduled_latency,
                    "tight_loop_latency": {
                        "status": "measured",
                        "batch_ms_median": timing["batch_ms_median"],
                        "batch_ms_p95": timing["batch_ms_p95"],
                        "timing_loops": timing["timing_loops"],
                        "warmup_loops": timing["warmup_loops"],
                        "rows_checked": timing["rows_checked"],
                        "maximum_probability_error": timing[
                            "maximum_probability_error"
                        ],
                        "label_disagreements": timing["label_disagreements"],
                        "scheduler_applicability": "proxy",
                        "applicability_note": (
                            "The value is measured, but using it as a scheduler cost is a "
                            "proxy because the tight-loop cadence/residency differs from "
                            "the one-batch-per-second static workload and future switching."
                        ),
                    },
                    "temperature": temperature,
                    "gaps": {
                        "energy_per_batch_status": "unmeasured",
                        "energy_per_batch_note": (
                            "Not computed by multiplying static power and tight-loop "
                            "latency because that would mix incompatible cadences."
                        ),
                        "switch_latency_status": "unmeasured",
                        "switch_latency_ms": None,
                        "first_batch_latency_status": "unmeasured",
                        "first_batch_latency_ms": None,
                    },
                    "uncertainty": {"summary": uncertainty_summary},
                }
            )

    idle_agg = aggregate_by_profile["idle"]
    idle_temperatures = profile_groups["idle"]
    idle_entry = {
        "entry_id": "ton_iot/idle",
        "dataset": "ton_iot",
        "model": "idle",
        "device": "Raspberry Pi 4 Model B Rev 1.5, 8 GB, aarch64",
        "artifact": None,
        "preprocessing": {
            **artifact_records["ton_iot"]["preprocessor"],
            "execution_status": "not executed; no inference batch was invoked",
        },
        "inputs": {
            "pi_check_X_sha256": None,
            "pi_reference_predictions_sha256": None,
            "physical_train_X_sha256": common_physical_inputs["inputs/train_X.npy"],
            "resident_input_bundle_sha256": resident_bundle_sha,
        },
        "batch_size_rows": 100,
        "physical_active_rows_per_second": 0,
        "physical_cadence": (
            "measured for 1800 seconds at 1 Hz with no inference calls; batch size 100 "
            "remained the configured active-profile unit"
        ),
        "pi_timing_cadence": "not measured for idle",
        "target_scheduler_residency_semantics": (
            "all four TON models stay loaded; idle and action switches do not load or "
            "unload a model"
        ),
        "scheduler_residency_evidence_status": "measured",
        "power_residency_semantics": (
            "TinyDT, LightLR, MedRF, and HeavyMLP were all loaded, parity-checked, and "
            "warmed; telemetry and control remained active, but no model was invoked "
            "inside each second"
        ),
        "pi_timing_residency_semantics": "not applicable to idle",
        "power_measurement_point": (
            "POWER-Z KM003C at the Pi USB input/load side, sampled at 1 Hz; not AC-wall power"
        ),
        "latency_measurement_point": "unmeasured for idle; no predict call was made",
        "power": {
            "evidence_status": "measured",
            "aggregate_status": "derived",
            "repeats": 3,
            "mean_watts": as_float(idle_agg["mean_watts"], "idle"),
            "sd_watts": as_float(idle_agg["sd_watts"], "idle"),
            "ci95_low_watts": as_float(idle_agg["mean_watts_ci95_low"], "idle"),
            "ci95_high_watts": as_float(idle_agg["mean_watts_ci95_high"], "idle"),
            "mean_energy_joules_30min": as_float(
                idle_agg["mean_energy_joules_30min"], "idle"
            ),
            "increment_status": "derived",
            "mean_increment_watts": 0.0,
            "increment_sd_watts": 0.0,
            "increment_ci95_low_watts": 0.0,
            "increment_ci95_high_watts": 0.0,
            "scope": idle_agg["measurement_scope"],
        },
        "scheduled_1hz_latency": {
            "status": "unmeasured",
            "source_status": "unmeasured",
            "repeats": None,
            "mean_of_run_medians_ms": None,
            "sd_of_run_medians_ms": None,
            "ci95_low_ms": None,
            "ci95_high_ms": None,
            "cadence": None,
        },
        "tight_loop_latency": {
            "status": "unmeasured",
            "batch_ms_median": None,
            "batch_ms_p95": None,
            "timing_loops": None,
            "warmup_loops": None,
            "rows_checked": None,
            "maximum_probability_error": None,
            "label_disagreements": None,
            "scheduler_applicability": "unmeasured",
            "applicability_note": "No idle predict-call timing exists.",
        },
        "temperature": {
            "observation_status": "measured",
            "static_min_c": min(row["temperature_min_c"] for row in idle_temperatures),
            "static_max_c": max(row["temperature_max_c"] for row in idle_temperatures),
            "response_status": "unmeasured",
            "response_note": (
                "Instrumented idle temperatures are not a calibrated response curve."
            ),
        },
        "gaps": {
            "energy_per_batch_status": "unmeasured",
            "energy_per_batch_note": "Idle has no inference batch.",
            "switch_latency_status": "unmeasured",
            "switch_latency_ms": None,
            "first_batch_latency_status": "unmeasured",
            "first_batch_latency_ms": None,
        },
        "uncertainty": {
            "summary": (
                "Power: n=3 sequential instrumented-idle profiles, sample SD and two-"
                "sided Student-t 95% CI (df=2); single Pi and uncalibrated meter. No "
                "inference-latency uncertainty applies."
            )
        },
    }
    entries.insert(0, idle_entry)

    return {
        "schema_version": 1,
        "registry_id": "TNSM-RESOURCE-COST-REGISTRY-20260907-V1",
        "created_date": "2026-09-07",
        "scope": (
            "Derived registry of already recorded static power and Pi encoded-input "
            "timing; no new measurement and no adaptive-policy result"
        ),
        "status_vocabulary": {
            "measured": "directly observed in the cited existing run/report",
            "derived": "computed only from cited measured values",
            "unmeasured": "no suitable existing observation; numeric value remains null",
            "proxy": "measured under a different cadence/residency and not interchangeable",
        },
        "source_evidence": {
            "article_archive": {
                "file": article_path.name,
                "sha256": ARTICLE_ARCHIVE_SHA256,
                "manifest_sha256": sha256_bytes(manifest_bytes),
                "physical_profiles_member": {
                    "path": PROFILE_MEMBER,
                    "sha256": sha256_bytes(profile_bytes),
                },
                "physical_aggregates_member": {
                    "path": POWER_AGGREGATE_MEMBER,
                    "sha256": sha256_bytes(aggregate_bytes),
                },
                "pi_inference_report_member": {
                    "path": PI_REPORT_MEMBER,
                    "sha256": sha256_bytes(pi_report_bytes),
                },
                "pi_readonly_snapshot_member": {
                    "path": PI_SNAPSHOT_MEMBER,
                    "sha256": sha256_bytes(pi_snapshot_bytes),
                },
                "physical_input_manifest_sha256": physical_manifest_hashes,
            },
            "software_evidence_archive": {
                "file": software_path.name,
                "sha256": SOFTWARE_ARCHIVE_SHA256,
                "pi_input_manifest_member": PI_INPUT_MANIFEST_MEMBER,
                "pi_input_manifest_sha256": PI_INPUT_MANIFEST_SHA256,
            },
        },
        "device": {
            "hardware_model": snapshot["hardware_model"].rstrip("\x00"),
            "architecture": snapshot["architecture"],
            "memory_total_bytes": snapshot["memory_total_bytes"],
            "cpu_count": snapshot["cpu_count"],
            "inference_cpu_thread_limit": 2,
            "meter": "POWER-Z KM003C serial 075356, HW 2.4, FW 2.0.6",
            "measurement_point": "Pi USB input/load side; not AC wall",
            "instrument_limit": (
                "uncalibrated meter, user-accepted approximately 5.4 V supply, one Pi; "
                "no ambient thermometer"
            ),
        },
        "cadence_separation": {
            "physical_static": (
                "TON-IoT only; one 100-row encoded batch each second for 1800 seconds; "
                "all four models resident; 1 Hz meter and telemetry"
            ),
            "pi_tight_loop": (
                "all three datasets; each model timed sequentially for 1000 consecutive "
                "100-row calls after 20 warmups; no meter and no one-second pacing"
            ),
            "forbidden_combination": (
                "Do not multiply or otherwise combine the two rhythms into energy per "
                "batch without a separately justified calibration."
            ),
        },
        "resident_physical_inputs": {
            "status": "measured",
            "files": common_physical_inputs,
            "canonical_mapping_sha256": resident_bundle_sha,
            "note": (
                "The common model/data hashes are identical across v1/v2/v3; only the "
                "transport/control worker revision changed."
            ),
        },
        "physical_segments": segment_records,
        "entries": entries,
        "known_gaps": [
            {
                "gap": "model_switch_latency",
                "status": "unmeasured",
                "requirement": (
                    "Measure action-to-action switching under the final all-four-resident "
                    "scheduler semantics; do not insert cold load/unload cost."
                ),
            },
            {
                "gap": "first_batch_latency",
                "status": "unmeasured",
                "requirement": (
                    "Measure the first batch after a scheduler action transition; existing "
                    "reports used 20 warmup calls and cannot supply it."
                ),
            },
            {
                "gap": "temperature_response",
                "status": "unmeasured",
                "requirement": (
                    "Calibrate only if required by the final scheduler; existing light-load "
                    "temperature range does not prove a hot-condition response or safety."
                ),
            },
            {
                "gap": "ciciot2023_and_n_baiot_power",
                "status": "unmeasured",
                "requirement": (
                    "Keep null unless dataset-specific physical measurement or an explicit, "
                    "separately reviewed proxy assumption is introduced."
                ),
            },
        ],
    }


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    repo_root = Path(__file__).resolve().parents[2]
    parser.add_argument(
        "--article-archive",
        type=Path,
        default=repo_root / "TNSM_ARTICLE_DATA_20260907_V1.zip",
    )
    parser.add_argument(
        "--software-archive",
        type=Path,
        default=repo_root / "TNSM_SOFTWARE_EXPERIMENT_EVIDENCE_V1.zip",
    )
    parser.add_argument(
        "--output-dir", type=Path, default=Path(__file__).resolve().parent
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        registry = build_registry(args.article_archive, args.software_archive)
        write_outputs(args.output_dir, registry)
    except (OSError, zipfile.BadZipFile, RegistryError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    print(f"WROTE {len(registry['entries'])} cost entries")
    print(f"BOUND {len(registry['physical_segments'])} existing physical segments")
    print("NEW_MEASUREMENTS 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
