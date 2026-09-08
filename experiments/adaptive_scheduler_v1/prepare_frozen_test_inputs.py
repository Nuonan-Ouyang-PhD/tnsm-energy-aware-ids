"""Bind the already-fixed held-out TON traces after both policies are frozen."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np


ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / "tnsm_experiments_v1" / "results" / "static_replay"
OUT = ROOT / "test_policy_inputs"
CONFIG = ROOT / "config" / "scheduler_experiment_v1.json"
POLICIES = {
    "Tabular-Q": Path("/Users/nuonanouyang/Library/Application Support/Codex/TNSM-adaptive-runtime-v1/software/tabular-frozen"),
    "DQN": Path("/Users/nuonanouyang/Library/Application Support/Codex/TNSM-adaptive-runtime-v1/software/dqn-frozen"),
}


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    config_hash = digest(CONFIG)
    frozen = {}
    for algorithm, directory in POLICIES.items():
        metadata_path = directory / "metadata.json"
        metadata = json.loads(metadata_path.read_text())
        if metadata.get("algorithm") != algorithm or metadata.get("frozen") is not True:
            raise RuntimeError(f"{algorithm} policy is not frozen")
        if metadata.get("config_sha256") != config_hash or metadata.get("test_data_accessed") is not False:
            raise RuntimeError(f"{algorithm} policy binding mismatch")
        frozen[algorithm] = {
            "policy_identity_sha256": metadata["policy_identity_sha256"],
            "metadata_sha256": digest(metadata_path),
            "weights_sha256": metadata["weights_sha256"],
        }
    config = json.loads(CONFIG.read_text())
    seeds = config["experiment_scope"]["formal_test_trace_seeds"]
    OUT.mkdir(parents=True)
    source_hashes = {}
    output_hashes = {}
    for seed in seeds:
        source = BASE / f"ton_iot-drift-{seed}.npz"
        source_meta = BASE / f"ton_iot-drift-{seed}.json"
        with np.load(source, allow_pickle=False) as archive:
            # These arrays were fixed in the accepted static replay. Labels remain
            # packaged for a later posthoc pass; the online evaluator does not load them.
            payload = {name: archive[name] for name in (
                "indices", "source_ids", "feature_fingerprints", "labels",
                "model_probabilities", "models",
            )}
        phase_ids = np.concatenate([
            np.full(windows, phase, dtype=np.int8)
            for phase, windows in enumerate((100, 100, 120, 100, 80), start=1)
        ])
        target = OUT / f"test_drift_{seed}.npz"
        np.savez_compressed(
            target,
            **payload,
            analysis_only_phase_ids=phase_ids,
            windows=np.int64(500),
            samples_per_window=np.int64(100),
        )
        source_hashes[source.name] = digest(source)
        source_hashes[source_meta.name] = digest(source_meta)
        output_hashes[target.name] = digest(target)
    report = {
        "status": "PASS",
        "created_only_after_both_policies_frozen": True,
        "config_sha256": config_hash,
        "frozen_policies": frozen,
        "test_trace_seeds": seeds,
        "rows_per_trace": 50000,
        "source_sha256": source_hashes,
        "output_sha256": output_hashes,
        "online_label_rule": "labels are present only for a separate posthoc pass; online loader requests load_labels=false",
        "phase_id_rule": "analysis-only; forbidden to state and ignored by online loader",
    }
    (OUT / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"event": "frozen_test_inputs_ready", "traces": len(seeds), "config_sha256": config_hash}))


if __name__ == "__main__":
    main()
