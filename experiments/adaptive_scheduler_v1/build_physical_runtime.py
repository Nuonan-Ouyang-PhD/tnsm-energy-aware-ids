"""Create a no-clobber, hash-bound internal runtime and a label-free Pi bundle."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import numpy as np


SOURCE = Path(__file__).resolve().parent
WORK = SOURCE.parent
DEST = Path("/Users/nuonanouyang/Library/Application Support/Codex/TNSM-adaptive-runtime-v1/physical-r3")
SOFTWARE = DEST.parent / "software"
RESULTS = WORK / "tnsm_experiments_v1" / "results" / "ton_iot"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def copy(source: Path, relative: str) -> Path:
    destination = DEST / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)
    return destination


def main() -> None:
    if DEST.exists():
        raise FileExistsError(f"refusing to overwrite {DEST}")
    DEST.mkdir(parents=True)
    for name in ("controller.py", "worker.py", "measurement.py"):
        copy(SOURCE / "physical" / name, name)
    for path in sorted((SOURCE / "scheduler").glob("*.py")):
        if path.name != "test_scheduler.py":
            copy(path, f"scheduler/{path.name}")
    config_path = copy(SOURCE / "config" / "scheduler_experiment_v1.json", "config/scheduler_experiment_v1.json")
    for policy, source_name in (("tabular-frozen", "tabular-frozen"), ("dqn-frozen", "dqn-frozen")):
        source_dir = SOFTWARE / source_name
        metadata = json.loads((source_dir / "metadata.json").read_text())
        copy(source_dir / "metadata.json", f"policies/{policy}/metadata.json")
        copy(source_dir / metadata["weights_file"], f"policies/{policy}/{metadata['weights_file']}")
    for name in ("TinyDT.joblib", "LightLR.joblib", "MedRF.joblib", "HeavyMLP.pt", "validation_X.npy", "test_X.npy"):
        copy(RESULTS / name, f"inputs/{name}")
    train_x = np.load(RESULTS / "train_X.npy", mmap_mode="r")
    np.save(DEST / "inputs" / "warm_X.npy", np.array(train_x[:1000], copy=True), allow_pickle=False)

    traces = {}
    (DEST / "traces").mkdir()
    pilot = np.load(SOURCE / "policy_inputs" / "validation_drift_401.npz", allow_pickle=False)
    np.save(DEST / "traces" / "pilot_validation_401.indices.npy", pilot["indices"], allow_pickle=False)
    np.save(DEST / "traces" / "pilot_validation_401.labels.npy", pilot["labels"], allow_pickle=False)
    traces["pilot_validation_401"] = {
        "partition": "validation", "seed": 401,
        "x_file": "inputs/validation_X.npy",
        "indices_file": "traces/pilot_validation_401.indices.npy",
        "labels_file_local_only": "traces/pilot_validation_401.labels.npy",
    }
    for seed in (11, 23, 37, 53, 71, 89, 107, 131, 157, 191):
        archive = np.load(SOURCE / "test_policy_inputs" / f"test_drift_{seed}.npz", allow_pickle=False)
        key = f"formal_test_{seed}"
        np.save(DEST / "traces" / f"{key}.indices.npy", archive["indices"], allow_pickle=False)
        np.save(DEST / "traces" / f"{key}.labels.npy", archive["labels"], allow_pickle=False)
        traces[key] = {
            "partition": "test", "seed": seed,
            "x_file": "inputs/test_X.npy",
            "indices_file": f"traces/{key}.indices.npy",
            "labels_file_local_only": f"traces/{key}.labels.npy",
        }
    copy(SOURCE / "physical_schedule_v1.json", "bindings/physical_schedule_v1.json")
    copy(SOURCE / "AUTHORIZATION.md", "bindings/AUTHORIZATION.md")
    copy(SOURCE / "PLAN.md", "bindings/PLAN.md")

    local_files = {
        str(path.relative_to(DEST)): digest(path)
        for path in sorted(DEST.rglob("*")) if path.is_file()
    }
    policy_metadata = {
        name: json.loads((DEST / "policies" / folder / "metadata.json").read_text())["policy_identity_sha256"]
        for name, folder in (("Tabular-Q", "tabular-frozen"), ("DQN", "dqn-frozen"))
    }
    runtime = {
        "status": "READY",
        "config_sha256": digest(config_path),
        "authorization_sha256": digest(DEST / "bindings" / "AUTHORIZATION.md"),
        "schedule_sha256": digest(DEST / "bindings" / "physical_schedule_v1.json"),
        "frozen_policy_identities": policy_metadata,
        "files": local_files,
        "local_labels_never_uploaded_to_pi": True,
    }
    (DEST / "runtime_manifest.json").write_text(json.dumps(runtime, indent=2) + "\n")

    remote_excluded = {"controller.py", "measurement.py", "runtime_manifest.json", "controller.lock"}
    remote_files = {
        relative: sha for relative, sha in local_files.items()
        if relative not in remote_excluded and not relative.endswith(".labels.npy") and not relative.startswith("bindings/")
    }
    remote_manifest = {
        "status": "READY",
        "config_sha256": runtime["config_sha256"],
        "frozen_policy_identities": policy_metadata,
        "files": remote_files,
        "traces": {
            key: {name: value for name, value in item.items() if name != "labels_file_local_only"}
            for key, item in traces.items()
        },
        "labels_present_on_pi": False,
    }
    (DEST / "inputs_manifest.json").write_text(json.dumps(remote_manifest, indent=2) + "\n")
    lines = [f"{sha}  {relative}" for relative, sha in sorted(remote_files.items())]
    lines.append(f"{digest(DEST / 'inputs_manifest.json')}  inputs_manifest.json")
    (DEST / "inputs_manifest.sha256").write_text("\n".join(lines) + "\n")
    print(json.dumps({"event": "physical_runtime_ready", "local_files": len(local_files), "remote_files": len(remote_files), "traces": len(traces)}))


if __name__ == "__main__":
    main()
