"""Read-only TON-IoT `proto` value census (#23 pre-condition audit).

Authorized by the user as a one-off, explicitly-scoped audit exception
(DECISIONS.md #23 will record it). This script ONLY:
  - opens the frozen-inventory-registered TON-IoT CSV,
  - parses the header and the `proto` column (read-only),
  - counts raw proto values verbatim (no strip/lowercase/merge),
  - records anomalies (empty/whitespace/placeholder/parse errors),
  - reconciles counts against the frozen inventory row count,
  - verifies the two live config files remain byte-identical.

It MUST NOT: export row-level data, build feature matrices, fit
encoders, split data, or train models. No data copy is created.

Layout of outputs (artifacts/datasets/proto_census/):
  ton_iot_proto_20260905THHMMSSZ.json   machine-readable census
  ton_iot_proto_20260905THHMMSSZ.log    run log (same content, plain text)
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
OUT_DIR = REPO / "artifacts/datasets/proto_census"

FEATURE_POLICY_SHA = "2a903a4a0dd54e4307b7dce24599c39ce62b378b4cd8a95f8a633ffedb321b47"
LABEL_ONTOLOGY_SHA = "8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab"

SCRIPT_VERSION = "ton_iot_proto_census v1 (2026-09-05, #23 audit exception)"


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    log_lines = []

    def log(msg):
        print(msg)
        log_lines.append(msg)

    log(f"[script] {SCRIPT_VERSION}")
    log(f"[argv] {' '.join(sys.argv)}")
    log(f"[git-head] {subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=REPO, capture_output=True, text=True).stdout.strip()}")
    log(f"[git-clean] {subprocess.run(['git', 'status', '--porcelain'], cwd=REPO, capture_output=True, text=True).stdout.strip()!r}")

    # ---- 1) input identity ------------------------------------------------
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    entry = inventory["files"][0]
    assert entry["relative_path"] == "train_test_network.csv"
    expected_sha = entry["sha256"]
    expected_rows = entry["row_count"]
    expected_header_sha = entry["header_sha256"]
    expected_cols = entry["columns"]

    actual_sha = sha256_file(CSV_PATH)
    assert actual_sha == expected_sha, f"CSV SHA mismatch: {actual_sha}"
    log(f"[input] {CSV_PATH}")
    log(f"[inventory] {INVENTORY_PATH.name} (ton_iot_20260903T113048Z frozen inventory)")
    log(f"[csv-sha256] {actual_sha} == inventory ({expected_sha})")
    log(f"[expected-rows] {expected_rows}")

    # ---- 2) read-only parse ------------------------------------------------
    proto_counts = Counter()          # raw verbatim values
    row_field_count_mismatch = 0
    parse_errors = 0
    total_rows = 0
    header_seen = None
    proto_idx = None

    with open(CSV_PATH, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header_seen = next(reader)
        if header_seen != expected_cols:
            raise SystemExit(f"header mismatch vs frozen inventory: {header_seen}")
        proto_idx = header_seen.index("proto")
        log(f"[header] 44 columns match frozen inventory; proto at index {proto_idx}")
        header_sha = hashlib.sha256(
            (",".join(expected_cols)).encode("utf-8")
        ).hexdigest()
        # inventory header_sha256 was computed on the BOM-less joined header
        log(f"[header-sha256-recomputed] {header_sha}")

        for fields in reader:
            total_rows += 1
            if len(fields) != len(expected_cols):
                row_field_count_mismatch += 1
                continue
            raw = fields[proto_idx]
            proto_counts[raw] += 1

    log(f"[rows] parsed {total_rows} data rows")

    # ---- 3) anomaly accounting (verbatim, no silent fixes) -----------------
    empty_string = proto_counts.get("", 0)
    whitespace_only = sum(
        n for v, n in proto_counts.items() if v != "" and v.strip() == ""
    )
    placeholders = {
        v: n
        for v, n in proto_counts.items()
        if v.strip().lower() in {"-", "--", "n/a", "na", "null", "none", "unknown", ""}
    }
    parse_anomalies = {
        "row_field_count_mismatch": row_field_count_mismatch,
        "parse_errors": parse_errors,
    }

    # ---- 4) value profiles (normalization-candidate checks only) ----------
    value_profiles = {}
    for value, count in sorted(proto_counts.items()):
        value_profiles[value] = {
            "count": count,
            "has_leading_or_trailing_whitespace": value != value.strip(),
            "is_empty_after_strip": value.strip() == "",
            "lowercase_variant_differs": value != value.lower(),
            "stripped_variant_differs": value != value.strip(),
        }

    # reconciliation vs frozen inventory
    reconciliation = {
        "inventory_row_count": expected_rows,
        "census_row_count": total_rows,
        "row_count_match": total_rows == expected_rows,
        "field_mismatch_rows": row_field_count_mismatch,
        "sum_of_value_counts": sum(proto_counts.values()),
        "sum_equals_row_count": sum(proto_counts.values()) == total_rows,
        "distinct_raw_values": len(proto_counts),
    }

    # ---- 5) config invariance ---------------------------------------------
    fp_sha = sha256_file(REPO / "config/feature_policy.json")
    lo_sha = sha256_file(REPO / "config/label_ontology.json")
    assert fp_sha == FEATURE_POLICY_SHA, "feature_policy.json changed!"
    assert lo_sha == LABEL_ONTOLOGY_SHA, "label_ontology.json changed!"
    log("[invariance] feature_policy.json SHA unchanged (2a903a4a...)")
    log("[invariance] label_ontology.json SHA unchanged (8a055e2e...)")
    csv_sha_after = sha256_file(CSV_PATH)
    assert csv_sha_after == expected_sha, "CSV changed during census!"

    # ---- 6) write artifact --------------------------------------------------
    created = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    artifact = {
        "schema_version": 1,
        "kind": "proto_value_census",
        "dataset_id": "ton_iot",
        "created_at_utc": created,
        "authorization": (
            "One-off read-only audit exception authorized by the user on "
            "2026-09-05 for the #23 proposal pre-condition; NOT a lift of "
            "the materialization/splitting/training gates"
        ),
        "source": {
            "inventory": "artifacts/datasets/inventories/ton_iot_20260903T113048Z.json",
            "relative_path": "train_test_network.csv",
            "sha256": actual_sha,
            "column": "proto",
            "column_index": proto_idx,
            "column_count": len(expected_cols),
        },
        "script": {
            "version": SCRIPT_VERSION,
            "mode": "read-only single-column census; csv module, "
                    "utf-8-sig, no row export, no encoder, no split, no training",
            "repo_head": subprocess.run(
                ["git", "rev-parse", "HEAD"], cwd=REPO,
                capture_output=True, text=True
            ).stdout.strip(),
        },
        "total_rows": total_rows,
        "proto_value_counts": dict(sorted(proto_counts.items())),
        "value_profiles": value_profiles,
        "anomalies": {
            "empty_string": empty_string,
            "whitespace_only": whitespace_only,
            "placeholder_like_values": placeholders,
            **parse_anomalies,
        },
        "reconciliation": reconciliation,
        "normalization_candidates": {
            v: {
                "strip_needed": v != v.strip(),
                "lowercase_needed": v != v.lower(),
            }
            for v in sorted(proto_counts)
        },
        "normalization_status": "proposed",
        "notes": [
            "Raw observed values are recorded verbatim; no strip/lowercase/"
            "merge was applied.",
            "This census is audit evidence for the #23 proposal only; it "
            "must NOT be used as an all-data encoder vocabulary. The "
            "existing rule (category encoders fitted on the training split "
            "only) stands unchanged.",
            "All normalization mappings remain proposals until the "
            "feature/label protocol freeze.",
        ],
        "paper_eligible": False,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    base = f"ton_iot_proto_{stamp}"
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
    print("anomalies:", artifact["anomalies"])
    print("reconciliation:", reconciliation)
    print("\n[artifact]", art_path)
    print("[artifact sha256]", sha256_file(art_path))
    print("[log]", log_path)


if __name__ == "__main__":
    main()
