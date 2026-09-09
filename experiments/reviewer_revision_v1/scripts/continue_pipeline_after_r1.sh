#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
  echo "usage: $0 R1_CONTROLLER_PID" >&2
  exit 2
fi

r1_pid=$1
repo_root='/Volumes/RESEARCH_DATA/10_PROJECTS/COMPLETE_RESEARCH_BY_SOURCE_PATH/Documents/ChatGPT/TNSM - 文章重构'
revision_root="$repo_root/revision_experiments_20260908"
controller_python="$repo_root/adaptive_scheduler_v1/p1a_static_lightlr_physical/.venv/bin/python"
analysis_python="$repo_root/tnsm_experiments_v1/.venv/bin/python"

cd "$repo_root"
while kill -0 "$r1_pid" 2>/dev/null; do
  sleep 30
done

jq -e '.status == "PASS" and .formal_runs == 40' "$revision_root/r1_cascade_physical/campaign_summary.json" >/dev/null
caffeinate -dimsu "$controller_python" "$revision_root/controller.py" --campaign R2
jq -e '.status == "PASS" and .formal_runs == 60' "$revision_root/r2_variable_load/campaign_summary.json" >/dev/null

"$analysis_python" "$revision_root/scripts/record_stage_stops.py"
"$analysis_python" "$revision_root/scripts/r4_tinydt_threshold.py" select
"$analysis_python" "$revision_root/scripts/r4_tinydt_threshold.py" apply
"$analysis_python" "$revision_root/scripts/build_revision_registries.py"
"$analysis_python" "$revision_root/scripts/validate_revision_evidence.py"
"$analysis_python" "$revision_root/scripts/finalize_revision_package.py"
