from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def compact_utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        json.dump(value, handle, indent=2, sort_keys=True)
        handle.write("\n")
    temporary.replace(path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run_text(command: list[str], timeout: float = 10.0) -> str | None:
    try:
        result = subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (FileNotFoundError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None
    return result.stdout.strip()


def repo_root_from_module() -> Path:
    return Path(__file__).resolve().parents[2]


def git_commit(repo_root: Path) -> str | None:
    revision = run_text(["git", "-C", str(repo_root), "rev-parse", "HEAD"])
    if revision:
        return revision
    source_commit = repo_root / "SOURCE_COMMIT"
    if source_commit.exists():
        return source_commit.read_text(encoding="utf-8").strip() or None
    return None


def worktree_is_dirty(repo_root: Path) -> bool:
    """True when tracked files are staged/modified or non-artifact files are untracked.

    Evidence manifests record source_commit, so they must only be generated
    when the commit being referenced actually contains the protocol text and
    code in use; a dirty worktree means that guarantee cannot hold.

    Untracked files under artifacts/ are exempt: evidence manifests are the
    output of these very commands, so an acquisition run producing a new
    untracked manifest must not block the immediately following inventory
    run. Untracked .temp/ scratch files are likewise exempt. Everything else
    (staged changes, modifications or deletions of tracked files, untracked
    sources/docs/config) still fails closed.
    """
    status = run_text(["git", "-C", str(repo_root), "status", "--porcelain"])
    if not status:
        return False
    for line in status.splitlines():
        if not line.strip():
            continue
        # "XY path" or "XY path -> path"; XY is the two-letter status code.
        path = line[3:].strip()
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if line[:2] == "??":
            # Untracked evidence manifests are command output, not source.
            if path == "artifacts/" or path.startswith("artifacts/"):
                continue
            # Agent scratch space; never a provenance concern.
            if path == ".temp/" or path.startswith(".temp/"):
                continue
            return True
        # Staged, modified, or deleted tracked files always block.
        return True
    return False

