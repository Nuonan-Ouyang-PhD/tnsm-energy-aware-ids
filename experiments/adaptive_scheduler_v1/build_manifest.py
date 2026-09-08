"""Create and verify the incremental SHA-256 manifest for this stage."""
from __future__ import annotations

import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "MANIFEST_SHA256.txt"


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            value.update(block)
    return value.hexdigest()


def included_files() -> list[Path]:
    return sorted(
        path for path in ROOT.rglob("*")
        if path.is_file()
        and path != OUTPUT
        and "__pycache__" not in path.parts
        and path.name != ".DS_Store"
    )


def main() -> None:
    lines = [f"{digest(path)}  {path.relative_to(ROOT).as_posix()}" for path in included_files()]
    temporary = OUTPUT.with_suffix(".tmp")
    temporary.write_text("\n".join(lines) + "\n", encoding="utf-8")
    temporary.replace(OUTPUT)
    for line in OUTPUT.read_text(encoding="utf-8").splitlines():
        expected, relative = line.split("  ", 1)
        if digest(ROOT / relative) != expected:
            raise RuntimeError(f"manifest verification failed: {relative}")
    print(f"PASS: {len(lines)} files; {digest(OUTPUT)}")


if __name__ == "__main__":
    main()
