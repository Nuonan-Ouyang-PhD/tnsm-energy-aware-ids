#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"

for dataset_id in ton_iot ciciot2023 n_baiot; do
  mkdir -p "datasets/incoming/$dataset_id" "datasets/extracted/$dataset_id"
done

cat <<'TEXT'
Dataset staging directories are ready.

Keep original downloaded files unchanged under:
  datasets/incoming/ton_iot/
  datasets/incoming/ciciot2023/
  datasets/incoming/n_baiot/

Extract copies under datasets/extracted/<dataset_id>/, preserving the original
archives. Follow docs/DATASET_ACQUISITION.md before registering any files.
TEXT

