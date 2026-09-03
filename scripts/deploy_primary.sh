#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pi_host="${PI_HOST:-pi4b8g.local}"
pi_user="${PI_USER:-pi}"
remote_dir="${PI_REMOTE_DIR:-tnsm-energy-aware-ids}"
target="${pi_user}@${pi_host}"

"$repo_root/scripts/bootstrap_mac.sh"

source_commit="$(git -C "$repo_root" rev-parse --verify HEAD)"
if [[ ! "$source_commit" =~ ^[0-9a-f]{40}$ ]]; then
  echo "Could not resolve a 40-character Git source revision." >&2
  exit 2
fi

if ! command -v rsync >/dev/null 2>&1; then
  echo "rsync is required on the Mac mini." >&2
  exit 2
fi

echo "Deploying to ${target}:${remote_dir}"
ssh -o ConnectTimeout=8 "$target" "mkdir -p '$remote_dir'"
if ! rsync -az \
  --exclude '.venv/' \
  --exclude '__pycache__/' \
  --exclude 'data/raw/' \
  --exclude 'artifacts/preflight/' \
  --exclude 'artifacts/reports/' \
  "$repo_root/" "$target:$remote_dir/"; then
  echo "Deployment failed. Confirm that rsync is installed on the Pi:" >&2
  echo "  sudo apt update && sudo apt install -y rsync" >&2
  exit 2
fi

printf '%s\n' "$source_commit" | \
  ssh "$target" "cd '$remote_dir' && tee SOURCE_COMMIT >/dev/null"

ssh "$target" "cd '$remote_dir' && ./scripts/bootstrap_pi.sh"
ssh "$target" "cd '$remote_dir' && PYTHONPATH=src .venv/bin/python -m tnsm_exp preflight"

echo "Preflight passed; starting the 30-second ineligible diagnostic smoke."
ssh "$target" "cd '$remote_dir' && PYTHONPATH=src .venv/bin/python -m tnsm_exp smoke"
"$repo_root/scripts/collect_primary.sh"
echo "Smoke complete and copied back to the Mac."
