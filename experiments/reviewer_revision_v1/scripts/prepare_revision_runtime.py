"""Prepare and freeze label-free Pi inputs plus local R1/R2 evaluation bindings."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import numpy as np


ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SOURCE = REPO / "adaptive_scheduler_v1" / "p1a_static_lightlr_physical"
PREDICTIONS = REPO / "tnsm_experiments_v1" / "results" / "ton_iot" / "test_predictions.npz"
SEEDS = [11, 23, 37, 53, 71, 89, 107, 131, 157, 191]
CELLS = [(rate, prevalence) for rate in (50, 100, 4000) for prevalence in (0.10, 0.50, 0.90)]


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def copy_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def main() -> None:
    for name in ("TinyDT.joblib", "LightLR.joblib", "MedRF.joblib", "HeavyMLP.pt", "test_X.npy", "validation_X.npy", "warm_X.npy"):
        copy_file(SOURCE / "inputs" / name, ROOT / "inputs" / name)
    copy_file(SOURCE / "config" / "scheduler_experiment_v1.json", ROOT / "config" / "scheduler_experiment_v1.json")
    if (ROOT / "scheduler").exists():
        shutil.rmtree(ROOT / "scheduler")
    shutil.copytree(SOURCE / "scheduler", ROOT / "scheduler", copy_function=shutil.copy2)
    for policy in ("tabular-frozen", "dqn-frozen"):
        destination = ROOT / "policies" / policy
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(SOURCE / "policies" / policy, destination, copy_function=shutil.copy2)
    for seed in SEEDS:
        copy_file(SOURCE / "traces" / f"formal_test_{seed}.indices.npy", ROOT / "traces" / f"formal_test_{seed}.indices.npy")

    prediction = np.load(PREDICTIONS, allow_pickle=False)
    test_y = prediction["labels"].astype(np.int8)
    source_ids = prediction["ids"].astype(np.int64)
    if len(test_y) != 22490 or source_ids.shape != (22490, 2):
        raise RuntimeError("frozen test prediction dimensions changed")
    np.save(ROOT / "inputs" / "test_y.npy", test_y, allow_pickle=False)
    np.save(ROOT / "inputs" / "test_source_ids.npy", source_ids, allow_pickle=False)
    positive = np.flatnonzero(test_y == 1)
    negative = np.flatnonzero(test_y == 0)
    if not len(positive) or not len(negative):
        raise RuntimeError("test pool lacks a class")

    block_registry = {}
    for block in range(1, 11):
        seed = 20260908 + block
        rng = np.random.default_rng(seed)
        order = [CELLS[index] for index in rng.permutation(len(CELLS))]
        phases = order + [(100, 0.10)]
        arrivals = []
        indices_parts = []
        boundaries = []
        row_offset = 0
        for phase_index, (rate, prevalence) in enumerate(phases):
            start_second = phase_index * 50
            phase_start = row_offset
            for _ in range(50):
                positives = int(rate * prevalence)
                negatives = rate - positives
                chosen = np.concatenate([
                    rng.choice(positive, size=positives, replace=True),
                    rng.choice(negative, size=negatives, replace=True),
                ])
                rng.shuffle(chosen)
                indices_parts.append(chosen.astype(np.int32))
                arrivals.append(rate)
                row_offset += rate
            boundaries.append({
                "phase_index": phase_index, "start_second": start_second, "end_second_exclusive": start_second + 50,
                "start_row_offset": phase_start, "end_row_offset_exclusive": row_offset,
                "load_rows_per_s": rate, "attack_prevalence": prevalence,
                "recovery": phase_index == 9,
            })
        indices = np.concatenate(indices_parts)
        arrivals_array = np.asarray(arrivals, dtype=np.int32)
        offsets = np.concatenate(([0], np.cumsum(arrivals_array, dtype=np.int64)))
        labels = test_y[indices]
        if len(indices) != 627500 or len(arrivals_array) != 500:
            raise RuntimeError("unexpected R2 workload dimensions")
        for boundary in boundaries:
            values = labels[boundary["start_row_offset"]:boundary["end_row_offset_exclusive"]]
            observed = float(values.mean())
            if observed != boundary["attack_prevalence"]:
                raise RuntimeError("R2 exact prevalence generation failed")
            boundary["observed_attack_prevalence"] = observed
        prefix = ROOT / "r2_workloads" / f"block_{block:02d}"
        np.save(prefix.with_suffix(".indices.npy"), indices, allow_pickle=False)
        np.save(prefix.with_suffix(".arrivals.npy"), arrivals_array, allow_pickle=False)
        np.save(prefix.with_suffix(".offsets.npy"), offsets, allow_pickle=False)
        np.save(prefix.with_suffix(".labels.npy"), labels, allow_pickle=False)
        np.save(prefix.with_suffix(".source_ids.npy"), source_ids[indices], allow_pickle=False)
        schedule = {
            "block": block, "seed": seed, "generator": "numpy.random.Generator(PCG64)",
            "duration_seconds": 500, "total_rows": int(len(indices)), "boundaries": boundaries,
            "labels_available_to_runtime": False,
        }
        with prefix.with_suffix(".schedule.json").open("x") as handle:
            json.dump(schedule, handle, indent=2, allow_nan=False); handle.write("\n")
        block_registry[str(block)] = {
            "indices_file": f"r2_workloads/{prefix.name}.indices.npy",
            "arrivals_file": f"r2_workloads/{prefix.name}.arrivals.npy",
            "offsets_file": f"r2_workloads/{prefix.name}.offsets.npy",
            "labels_file_local_only": f"r2_workloads/{prefix.name}.labels.npy",
            "source_ids_file_local_only": f"r2_workloads/{prefix.name}.source_ids.npy",
            "schedule_file": f"r2_workloads/{prefix.name}.schedule.json",
        }
    with (ROOT / "r2_workloads" / "registry.json").open("x") as handle:
        json.dump({"status": "FROZEN_BEFORE_R1", "blocks": block_registry}, handle, indent=2, allow_nan=False); handle.write("\n")
    print(json.dumps({
        "status": "PASS", "test_rows": len(test_y), "r2_blocks": len(block_registry),
        "r2_rows_per_block": 627500, "test_predictions_sha256": digest(PREDICTIONS),
    }, indent=2))


if __name__ == "__main__":
    main()
