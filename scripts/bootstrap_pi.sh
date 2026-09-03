#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

if ! command -v python3 >/dev/null 2>&1; then
  echo "python3 is missing. Install it, then rerun this script." >&2
  exit 2
fi

python3 - <<'PY'
import sys
if sys.version_info < (3, 11):
    raise SystemExit("Python 3.11 or newer is required")
print("Python:", sys.version.split()[0])
PY

if [[ ! -x .venv/bin/python ]]; then
  if ! python3 -m venv .venv; then
    echo "Could not create a venv. On Debian/Raspberry Pi OS, run:" >&2
    echo "  sudo apt update && sudo apt install -y python3-venv" >&2
    exit 2
  fi
fi

PYTHONPATH=src .venv/bin/python -m compileall -q src tests
PYTHONPATH=src .venv/bin/python -m unittest discover -s tests -v
echo "Pi-side bootstrap passed. No system settings were changed."

