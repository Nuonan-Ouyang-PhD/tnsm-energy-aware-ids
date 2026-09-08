"""Precommit the paired physical run order before policies see held-out traces."""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "physical_schedule_v1.json"
METHODS = ("Static-MedRF", "CFSM", "Tabular-Q", "DQN")
TRACE_SEEDS = (11, 23, 37, 53, 71, 89, 107, 131, 157, 191)
ORDER_SEED = 20260907


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    rng = random.Random(ORDER_SEED)
    runs = []
    blocks = []
    for block, trace_seed in enumerate(TRACE_SEEDS, start=1):
        order = list(METHODS)
        rng.shuffle(order)
        blocks.append({"block": block, "trace_seed": trace_seed, "method_order": order})
        for position, method in enumerate(order, start=1):
            runs.append({
                "run_id": f"b{block:02d}-p{position}-{method}",
                "block": block,
                "position": position,
                "trace_seed": trace_seed,
                "method": method,
                "seconds": 500,
                "rows": 50000,
            })
    value = {
        "campaign_id": "TNSM-ADAPTIVE-SCHEDULER-20260907-V1",
        "status": "precommitted_before_policy_freeze_or_heldout_scheduler_evaluation",
        "order_seed": ORDER_SEED,
        "paired_block_count": 10,
        "runs_per_block": 4,
        "total_runs": 40,
        "same_trace_within_block": True,
        "policy_updates_during_runs": False,
        "failed_run_rule": "stop campaign, retain invalid run, no automatic retry",
        "blocks": blocks,
        "runs": runs,
    }
    payload = json.dumps(value, indent=2) + "\n"
    OUT.write_text(payload)
    print(json.dumps({"event": "physical_schedule_precommitted", "sha256": hashlib.sha256(payload.encode()).hexdigest()}))


if __name__ == "__main__":
    main()
