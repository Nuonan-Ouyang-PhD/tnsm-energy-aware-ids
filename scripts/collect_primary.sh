#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
pi_host="${PI_HOST:-pi4b8g.local}"
pi_user="${PI_USER:-pi}"
remote_dir="${PI_REMOTE_DIR:-tnsm-energy-aware-ids}"
target="${pi_user}@${pi_host}"
destination="$repo_root/collected/pi4b8g"

mkdir -p "$destination/data/raw/smoke" "$destination/artifacts/preflight"
rsync -az "$target:$remote_dir/data/raw/smoke/" "$destination/data/raw/smoke/"
rsync -az "$target:$remote_dir/artifacts/preflight/" "$destination/artifacts/preflight/"
echo "Collected evidence under: $destination"

