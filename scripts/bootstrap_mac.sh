#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is required on the Mac mini." >&2
  exit 2
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required")
print("Python:", sys.version.split()[0])
PY

if [[ ! -x .venv/bin/python ]]; then
  python3 -m venv .venv
fi

PYTHONPATH=src .venv/bin/python -m compileall -q src tests
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
echo "Mac-side bootstrap passed."

