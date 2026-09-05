"""Read-only TON-IoT `proto` census VERIFICATION PASS v2 (#23 Rev 1).

Background: the v1 census (ton_iot_proto_census.py, archived verbatim at
scripts/audits/ton_iot_proto_census_v1.py) ran as a one-off user-authorized
audit exception and produced ton_iot_proto_20260905T110840Z.json. The
independent review of the #23 V1 evidence package (F23-03) found the
delivered evidence insufficient to independently re-check the run: the v1
script was not committed, its bytes were not hashed anywhere, and the v1
log contains only a single [csv-sha256] line without a separately labelled
after-run digest.

User authorization (2026-09-05, #23 Rev 1 scope): ONE additional read-only
verification pass over the SAME frozen CSV, in the same scope as v1,
producing new timestamped artifacts that explicitly record the before-run
and after-run CSV digests and the exit status. This pass does NOT lift the
materialization/splitting/training gates, does NOT create any data copy,
and must not be used as an encoder vocabulary.

What v2 adds over v1 (everything else is identical scope):
  - [csv-sha256-before] and [csv-sha256-after] logged separately, each
    asserted equal to the frozen inventory digest;
  - both live config files hashed before AND after the scan;
  - the archived v1 script's own SHA-256 recorded as provenance;
  - header digests reported under EXPLICITLY NAMED recipes (raw first
    line bytes / line-stripped / BOM-stripped) so reviewers can recompute
    each value; the inventory's own frozen header_sha256 (024f793b...)
    is NOT reinterpreted - its recipe lives in the inventory generation
    code and is treated as an opaque frozen value;
  - the v1 census artifact is loaded and the observed value counts are
    asserted IDENTICAL (v2 is a verification of the delivered aggregate,
    not a new census definition).

It MUST NOT: export row-level data, build feature matrices, fit
encoders, split data, or train models. No data copy is created.

Outputs (artifacts/datasets/proto_census/):
  ton_iot_proto_v2_<stamp>.json   machine-readable verification record
  ton_iot_proto_v2_<stamp>.log    run log (same content, plain text)
"""

import csv
import hashlib
import json
import subprocess
import sys
import time
from collections import Counter
from pathlib import Path

REPO = Path("/Users/nuonanouyang/Downloads/tnsm-energy-aware-ids")
CSV_PATH = REPO / "datasets/incoming/ton_iot/train_test_network.csv"
INVENTORY_PATH = REPO / "artifacts/datasets/inventories/ton_iot_20260903T113048Z.json"
V1_ARTIFACT_PATH = (
    REPO / "artifacts/datasets/proto_census/ton_iot_proto_20260905T110840Z.json"
)
V1_SCRIPT_ARCHIVED = REPO / "scripts/audits/ton_iot_proto_census_v1.py"
OUT_DIR = REPO / "artifacts/datasets/proto_census"

FEATURE_POLICY_PATH = REPO / "config/feature_policy.json"
LABEL_ONTOLOGY_PATH = REPO / "config/label_ontology.json"
FEATURE_POLICY_SHA = "2a903a4a0dd54e4307b7dce24599c39ce62b378b4cd8a95f8a633ffedb321b47"
LABEL_ONTOLOGY_SHA = "8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab"

SCRIPT_VERSION = "ton_iot_proto_census v2 verification pass (2026-09-05, #23 Rev 1)"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    log_lines = []
    failed = False

    def log(msg):
        print(msg)
        log_lines.append(msg)

    log(f"[script] {SCRIPT_VERSION}")
    log(f"[argv] {' '.join(sys.argv)}")
    log(f"[git-head] {subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip()}")
    log(f"[git-status] {subprocess.run(['git', 'status', '--porcelain'], cwd=REPO, capture_output=True, text=True).stdout.strip()!r}")
    v1_script_sha = sha256_file(V1_SCRIPT_ARCHIVED)
    log(f"[v1-script] {V1_SCRIPT_ARCHIVED.relative_to(REPO)} sha256 {v1_script_sha}")

    # ---- 1) input identity (BEFORE) ---------------------------------------
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    entry = inventory["files"][0]
    assert entry["relative_path"] == "train_test_network.csv"
    expected_sha = entry["sha256"]
    expected_rows = entry["row_count"]
    expected_cols = entry["columns"]

    csv_sha_before = sha256_file(CSV_PATH)
    assert csv_sha_before == expected_sha, f"CSV SHA mismatch before run: {csv_sha_before}"
    log(f"[input] {CSV_PATH}")
    log(f"[inventory] {INVENTORY_PATH.name} (ton_iot_20260903T113048Z frozen inventory)")
    log(f"[csv-sha256-before] {csv_sha_before} == inventory ({expected_sha})")
    log(f"[expected-rows] {expected_rows}")

    fp_sha_before = sha256_file(FEATURE_POLICY_PATH)
    lo_sha_before = sha256_file(LABEL_ONTOLOGY_PATH)
    assert fp_sha_before == FEATURE_POLICY_SHA, "feature_policy.json changed before run!"
    assert lo_sha_before == LABEL_ONTOLOGY_SHA, "label_ontology.json changed before run!"
    log("[config-before] feature_policy.json 2a903a4a... unchanged")
    log("[config-before] label_ontology.json  8a055e2e... unchanged")

    # ---- 2) read-only scan (identical scope to v1) -------------------------
    proto_counts = Counter()          # raw verbatim values
    row_field_count_mismatch = 0
    parse_errors = 0
    total_rows = 0

    header_line_raw = None            # first physical line, verbatim bytes
    with open(CSV_PATH, "rb") as fh:
        header_line_raw = fh.readline()
    header_recipes = {
        # raw bytes of the first physical line exactly as stored (BOM + EOL included)
        "header_first_line_raw_sha256": hashlib.sha256(header_line_raw).hexdigest(),
        # first line with trailing CR/LF removed (BOM retained)
        "header_first_line_eol_stripped_sha256": hashlib.sha256(header_line_raw.rstrip(b"\r\n")).hexdigest(),
        # first line with UTF-8 BOM and trailing CR/LF removed;
        # equals sha256 of the comma-joined inventory column list
        "header_first_line_bom_and_eol_stripped_sha256": hashlib.sha256(header_line_raw.lstrip(b"\xef\xbb\xbf").rstrip(b"\r\n")).hexdigest(),
        # convenience: sha256(",".join(inventory columns)) for cross-reference
        "header_joined_inventory_columns_sha256": hashlib.sha256((",".join(expected_cols)).encode("utf-8")).hexdigest(),
    }
    for name, value in header_recipes.items():
        log(f"[{name}] {value}")
    log(
        "[header-recipe-note] inventory.header_sha256 (024f793b...) is an "
        "opaque frozen value from the inventory generation code; it is NOT "
        "recomputed or reinterpreted in this run."
    )

    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header_seen = next(reader)
        if header_seen != expected_cols:
            raise SystemExit(f"header mismatch vs frozen inventory: {header_seen}")
        proto_idx = header_seen.index("proto")
        log(f"[header] {len(expected_cols)} columns match frozen inventory; proto at index {proto_idx}")
        for fields in reader:
            total_rows += 1
            try:
                if len(fields) != len(expected_cols):
                    row_field_count_mismatch += 1
                    continue
                proto_counts[fields[proto_idx]] += 1
            except Exception:
                parse_errors += 1

    log(f"[rows] parsed {total_rows} data rows")

    # ---- 3) anomaly accounting (verbatim, no silent fixes) -----------------
    empty_string = proto_counts.get("", 0)
    whitespace_only = sum(n for v, n in proto_counts.items() if v != "" and v.strip() == "")
    placeholders = {
        v: n for v, n in proto_counts.items()
        if v.strip().lower() in {"-", "--", "n/a", "na", "null", "none", "unknown", ""}
    }

    value_profiles = {}
    for value, count in sorted(proto_counts.items()):
        value_profiles[value] = {
            "count": count,
            "has_leading_or_trailing_whitespace": value != value.strip(),
            "is_empty_after_strip": value.strip() == "",
            "lowercase_variant_differs": value != value.lower(),
            "stripped_variant_differs": value != value.strip(),
        }

    reconciliation = {
        "inventory_row_count": expected_rows,
        "v2_row_count": total_rows,
        "row_count_match": total_rows == expected_rows,
        "field_mismatch_rows": row_field_count_mismatch,
        "sum_of_value_counts": sum(proto_counts.values()),
        "sum_equals_row_count": sum(proto_counts.values()) == total_rows,
        "distinct_raw_values": len(proto_counts),
    }

    # ---- 4) v1 aggregate identity check ------------------------------------
    v1_artifact = json.loads(V1_ARTIFACT_PATH.read_text(encoding="utf-8"))
    counts_identical_to_v1 = dict(sorted(proto_counts.items())) == {
        k: v for k, v in v1_artifact["proto_value_counts"].items()
    }
    v1_rows_match = v1_artifact["total_rows"] == total_rows
    log(f"[v1-artifact] {V1_ARTIFACT_PATH.name} sha256 {sha256_file(V1_ARTIFACT_PATH)}")
    log(f"[v1-counts-identical] {counts_identical_to_v1}")
    log(f"[v1-rows-identical] {v1_rows_match}")

    # ---- 5) AFTER: input and config invariance -----------------------------
    csv_sha_after = sha256_file(CSV_PATH)
    assert csv_sha_after == expected_sha, f"CSV changed during v2 scan: {csv_sha_after}"
    log(f"[csv-sha256-after] {csv_sha_after} == inventory ({expected_sha})")
    log(
        f"[csv-invariance] before == inventory == after "
        f"({csv_sha_before == expected_sha and csv_sha_after == expected_sha})"
    )

    fp_sha_after = sha256_file(FEATURE_POLICY_PATH)
    lo_sha_after = sha256_file(LABEL_ONTOLOGY_PATH)
    assert fp_sha_after == FEATURE_POLICY_SHA, "feature_policy.json changed during run!"
    assert lo_sha_after == LABEL_ONTOLOGY_SHA, "label_ontology.json changed during run!"
    log("[config-after] feature_policy.json 2a903a4a... unchanged")
    log("[config-after] label_ontology.json  8a055e2e... unchanged")

    exit_status = "OK" if (reconciliation["row_count_match"]
                           and reconciliation["sum_equals_row_count"]
                           and counts_identical_to_v1) else "MISMATCH"
    log(f"[exit-status] {exit_status}")

    # ---- 6) write artifact --------------------------------------------------
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    artifact = {
        "schema_version": 2,
        "kind": "proto_value_census_verification",
        "dataset_id": "ton_iot",
        "created_at_utc": created,
        "authorization": (
            "One additional read-only verification pass over the same frozen "
            "CSV, authorized by the user in the #23 Rev 1 scope (2026-09-05) "
            "following the independent review finding F23-03; NOT a lift of "
            "the materialization/splitting/training gates"
        ),
        "source": {
            "inventory": "artifacts/datasets/inventories/ton_iot_20260903T113048Z.json",
            "relative_path": "train_test_network.csv",
            "sha256_before": csv_sha_before,
            "sha256_after": csv_sha_after,
            "sha256_inventory_expected": expected_sha,
            "invariance_before_inventory_after": (
                csv_sha_before == expected_sha and csv_sha_after == expected_sha
            ),
            "column": "proto",
            "column_index": proto_idx,
            "column_count": len(expected_cols),
        },
        "script": {
            "version": SCRIPT_VERSION,
            "mode": "read-only single-column verification; csv module, "
                    "utf-8-sig, no row export, no encoder, no split, no training",
            "repo_head": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=REPO,
                capture_output=True, text=True
            ).stdout.strip(),
            "v1_script_archived": str(V1_SCRIPT_ARCHIVED.relative_to(REPO)),
            "v1_script_sha256": v1_script_sha,
        },
        "header_digest_recipes": header_recipes,
        "header_recipe_note": (
            "Each digest above is reproducible from the raw first-line bytes "
            "of the CSV under the named recipe. inventory.header_sha256 "
            "(024f793b...) is an opaque frozen value from the inventory "
            "generation code and is deliberately not reinterpreted here."
        ),
        "v1_reference": {
            "artifact": "artifacts/datasets/proto_census/ton_iot_proto_20260905T110840Z.json",
            "sha256": sha256_file(V1_ARTIFACT_PATH),
            "counts_identical_to_v1": counts_identical_to_v1,
            "total_rows_identical_to_v1": v1_rows_match,
        },
        "total_rows": total_rows,
        "proto_value_counts": dict(sorted(proto_counts.items())),
        "value_profiles": value_profiles,
        "anomalies": {
            "empty_string": empty_string,
            "whitespace_only": whitespace_only,
            "placeholder_like_values": placeholders,
            "row_field_count_mismatch": row_field_count_mismatch,
            "parse_errors": parse_errors,
        },
        "reconciliation": reconciliation,
        "exit_status": exit_status,
        "notes": [
            "Raw observed values are recorded verbatim; no strip/lowercase/"
            "merge was applied.",
            "v2 is a verification pass of the v1 delivered aggregate over the "
            "same frozen CSV under the #23 Rev 1 authorization; it is audit "
            "evidence only and must NOT be used as an all-data encoder "
            "vocabulary. The existing rule (category encoders fitted on the "
            "training split only) stands unchanged.",
            "No old artifact or log was modified; v2 artifacts are new "
            "timestamped files alongside the v1 ones.",
        ],
        "paper_eligible": False,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    base = f"ton_iot_proto_v2_{stamp}"
    art_path = OUT_DIR / f"{base}.json"
    log_path = OUT_DIR / f"{base}.log"
    art_path.write_text(
        json.dumps(artifact, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    log_path.write_text("\n".join(log_lines) + "\n", encoding="utf-8")

    print("\n== summary ==")
    print("distinct raw proto values:", len(proto_counts))
    for v, n in sorted(proto_counts.items()):
        print(f"  {v!r}: {n}")
    print("counts identical to v1:", counts_identical_to_v1)
    print("anomalies:", artifact["anomalies"])
    print("reconciliation:", reconciliation)
    print("exit_status:", exit_status)
    print("\n[artifact]", art_path)
    print("[artifact sha256]", sha256_file(art_path))
    print("[log]", log_path)
    print("[log sha256]", sha256_file(log_path))

    if exit_status != "OK":
        sys.exit(1)


if __name__ == "__main__":
    main()
