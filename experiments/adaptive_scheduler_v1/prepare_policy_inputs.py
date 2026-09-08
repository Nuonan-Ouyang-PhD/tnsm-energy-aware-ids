"""Prepare scheduler train/validation caches without opening held-out test data."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import torch


ROOT = Path(__file__).resolve().parent
BASE = ROOT.parent / "tnsm_experiments_v1" / "results"
OUT = ROOT / "policy_inputs"
MODELS = ("TinyDT", "LightLR", "MedRF", "HeavyMLP")
PHASES = ((100, 0.05), (100, 0.35), (120, 0.70), (100, 0.40), (80, 0.10))
TRAIN_SEEDS = (211, 223, 227, 229, 233, 239, 241, 251, 257, 263)
VALIDATION_SEEDS = (401, 409, 419, 421, 431)


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def predict_all(folder: Path, x: np.ndarray) -> np.ndarray:
    result = np.empty((len(x), len(MODELS)), dtype=np.float32)
    for column, name in enumerate(MODELS[:-1]):
        model = joblib.load(folder / f"{name}.joblib")
        result[:, column] = model.predict_proba(x)[:, 1]
    saved = torch.load(folder / "HeavyMLP.pt", map_location="cpu", weights_only=True)
    net = torch.nn.Sequential(
        torch.nn.Linear(saved["input_dim"], 64), torch.nn.ReLU(), torch.nn.Dropout(0.2),
        torch.nn.Linear(64, 32), torch.nn.ReLU(), torch.nn.Dropout(0.2),
        torch.nn.Linear(32, 16), torch.nn.ReLU(), torch.nn.Dropout(0.2),
        torch.nn.Linear(16, 1),
    )
    net.load_state_dict(saved["state_dict"])
    net.eval()
    with torch.no_grad():
        result[:, 3] = np.concatenate([
            torch.sigmoid(net(torch.from_numpy(np.array(x[start:start + 4096], copy=True)))).numpy().ravel()
            for start in range(0, len(x), 4096)
        ])
    if not np.isfinite(result).all():
        raise RuntimeError("non-finite classifier probability")
    return result


def drift_indices(labels: np.ndarray, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Return indices and analysis-only phase IDs; phase IDs are not policy inputs."""
    rng = np.random.default_rng(seed)
    need = {
        1: sum(windows * round(100 * ratio) for windows, ratio in PHASES),
        0: sum(windows * (100 - round(100 * ratio)) for windows, ratio in PHASES),
    }
    chosen = {
        label: rng.choice(np.flatnonzero(labels == label), need[label],
                          replace=need[label] > int(np.count_nonzero(labels == label)))
        for label in (0, 1)
    }
    offsets = {0: 0, 1: 0}
    rows: list[np.ndarray] = []
    phase_ids: list[int] = []
    for phase, (windows, ratio) in enumerate(PHASES, start=1):
        positive = round(100 * ratio)
        negative = 100 - positive
        for _ in range(windows):
            batch = np.concatenate((
                chosen[1][offsets[1]:offsets[1] + positive],
                chosen[0][offsets[0]:offsets[0] + negative],
            ))
            offsets[1] += positive
            offsets[0] += negative
            rng.shuffle(batch)
            rows.append(batch)
            phase_ids.append(phase)
    return np.concatenate(rows).astype(np.int64), np.asarray(phase_ids, dtype=np.int8)


def save_trace(path: Path, cache: dict[str, np.ndarray], seed: int) -> None:
    indices, phase_ids = drift_indices(cache["labels"], seed)
    np.savez_compressed(
        path,
        indices=indices,
        source_ids=cache["ids"][indices],
        feature_fingerprints=cache["fingerprints"][indices],
        labels=cache["labels"][indices],
        model_probabilities=cache["probabilities"][indices],
        models=np.asarray(MODELS),
        analysis_only_phase_ids=phase_ids,
        windows=np.int64(500),
        samples_per_window=np.int64(100),
    )


def main() -> None:
    if OUT.exists():
        raise FileExistsError(f"refusing to overwrite {OUT}")
    OUT.mkdir(parents=True)
    folder = BASE / "ton_iot"
    train_x = np.load(folder / "train_X.npy", mmap_mode="r")
    train_pool = np.load(folder / "train_pool.npz", allow_pickle=False)
    train_probabilities = predict_all(folder, train_x)
    train_cache = {
        "probabilities": train_probabilities,
        "labels": train_pool["y"],
        "ids": train_pool["ids"],
        "fingerprints": train_pool["fingerprints"],
    }
    validation_npz = np.load(folder / "validation_predictions.npz", allow_pickle=False)
    if tuple(validation_npz["models"].tolist()) != MODELS:
        raise RuntimeError("validation model order mismatch")
    validation_cache = {key: validation_npz[key] for key in ("probabilities", "labels", "ids", "fingerprints")}
    np.savez_compressed(OUT / "ton_iot_train_predictions.npz", models=np.asarray(MODELS), **train_cache)
    for seed in TRAIN_SEEDS:
        save_trace(OUT / f"train_drift_{seed}.npz", train_cache, seed)
    for seed in VALIDATION_SEEDS:
        save_trace(OUT / f"validation_drift_{seed}.npz", validation_cache, seed)
    sources = [
        folder / "train_X.npy", folder / "train_pool.npz", folder / "validation_predictions.npz",
        *(folder / f"{name}.joblib" for name in MODELS[:-1]), folder / "HeavyMLP.pt",
        folder / "preprocessor.joblib", folder / "split_manifest.json",
    ]
    report = {
        "status": "PASS",
        "scope": "policy train/validation preparation only; held-out test files not opened",
        "classifier_threshold": 0.5,
        "split_seed_unchanged": 11,
        "train_trace_seeds": list(TRAIN_SEEDS),
        "validation_trace_seeds": list(VALIDATION_SEEDS),
        "rows_per_trace": 50000,
        "source_sha256": {str(path.relative_to(ROOT.parent)): digest(path) for path in sources},
        "output_sha256": {
            path.name: digest(path) for path in sorted(OUT.glob("*.npz"))
        },
        "phase_id_capability": "stored only for post-hoc diagnostics; forbidden to policy state",
    }
    (OUT / "manifest.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"event": "policy_inputs_ready", "outputs": len(report["output_sha256"])}))


if __name__ == "__main__":
    main()
