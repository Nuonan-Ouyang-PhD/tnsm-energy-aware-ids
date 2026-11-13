"""Check queue identifiability in the proposed fixed-latency simulator.

This is not an assertion about physical end-to-end deadline performance.
"""
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main():
    path = ROOT / "supplemental_scheduler_20261112/latency_calibration_02/report.json"
    report = json.loads(path.read_text())
    if report["status"] != "PASS":
        raise RuntimeError("latency calibration not accepted")
    capacities = {m: math.floor(1 / x["p95_seconds"]) * 100
                  for m, x in report["latency_registry"].items()}
    invariant = all(c >= 4000 for c in capacities.values())
    result = {
        "calibration_report_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "declared_arrivals": [50, 100, 4000], "initial_backlog": 0,
        "p95_capacity_rows_per_second": capacities,
        "zero_queue_invariant_in_simulator": invariant,
        "reason": "If every action can serve at least the maximum arrivals per window, zero initial backlog remains zero by induction.",
        "queue_ablation_status": "NOT_IDENTIFIABLE" if invariant else "REQUIRES_TRACE_COVERAGE_CHECK",
        "physical_deadline_claim": "NONE: warm-input inference timing excludes full controller, logging, monitoring, and transport costs",
        "formal_training_started": False,
        "workload_or_threshold_changed": False,
    }
    out = ROOT / "supplemental_scheduler_20261112/queue_coverage_gate.json"
    with out.open("x") as handle:
        json.dump(result, handle, indent=2)
        handle.write("\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
