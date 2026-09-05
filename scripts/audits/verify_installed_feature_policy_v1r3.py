#!/usr/bin/env python3
"""Post-installation verification for the Rev 2 target config
(Rev 3 entry point; remediation of the #23 Rev 2 independent-review
finding that the pre-install verifier cannot be run after the
target bytes are installed).

PHASE SEPARATION (the review's core requirement):

  Pre-install  (BEFORE the target bytes are installed):
    scripts/audits/build_feature_policy_target_v1r2.py
    scripts/audits/verify_feature_policy_target_v1r2.py
    Both operate on the live config/feature_policy.json as the OLD
    baseline and MUST NOT be invoked after installation.

  Post-install (AFTER the target bytes have been installed over
    config/feature_policy.json): THIS script. It NEVER re-applies
    the baseline-to-target replacements; it reads the ACTUAL
    installed file and compares it against the pinned immutable
    target artifact byte-for-byte, then inspects the applied state.

Three strictly distinct inputs, per the review:

  --baseline       preserved pre-freeze baseline snapshot (the old
                   2a903a4a... file; NOT the installed file)
  --target         the immutable committed target artifact
                   (feature_policy_freeze_target_v1r2.json,
                   e81a55c1...714b; byte-compared, never rebuilt)
  --applied        the actual installed config file path
  --label-ontology the frozen label_ontology.json (8a055e2e...)
  --spec           the Rev 2 target specification whose binding
                   values must match the applied config

This script installs nothing, writes nothing, does not read raw
CSV data, and grants no data-handling gate authority. Exit code 0
means the installed bytes/state are verified; it is NOT authority
for running materialization, splitting, or training.
"""

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

BASELINE_SHA = (
    "2a903a4a0dd54e4307b7dce24599c39ce62b378b4cd8a95f8a633ffedb321b47"
)
TARGET_SHA = (
    "e81a55c16f9439b0356295353e8b342de19d5c5606d868952592f913beda714b"
)
ONTOLOGY_SHA = (
    "8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab"
)

FLIPS = (
    "status",
    "semantic_core.candidate_examples[0].decision_status",
    "semantic_core.candidate_examples[1].decision_status",
    "semantic_core.review_outcome_2026_09_04.resolved_points[0]"
    ".decision_status",
)
GATES = ("materialization", "splitting", "training")
PAIRWISE_CORES = (
    "ton_iot__ciciot2023", "ton_iot__n_baiot", "ciciot2023__n_baiot")


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def parse_unique(data):
    """Parse JSON rejecting duplicate object keys (fail-closed)."""
    def hook(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result
    obj = json.loads(data.decode("utf-8"), object_pairs_hook=hook)
    if not isinstance(obj, dict):
        raise ValueError("expected a JSON object at the root")
    return obj


def dig(obj, path):
    """Resolve a dotted path with [index] suffixes."""
    cur = obj
    for part in path.split("."):
        m = re.match(r"^([^\[\]]*)((?:\[\d+\])*)$", part)
        name, brackets = m.group(1), m.group(2)
        if name:
            cur = cur[name]
        for idx in re.findall(r"\[(\d+)\]", brackets):
            cur = cur[int(idx)]
    return cur


def status_census(obj, prefix=""):
    """All (path, value) status/decision_status string leaves."""
    result = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if key in ("status", "decision_status") and isinstance(
                    value, str):
                result[path] = value
            result.update(status_census(value, path))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            result.update(status_census(value, f"{prefix}[{i}]"))
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Post-installation verification of the Rev 2 "
                    "feature-policy freeze target (read-only)")
    parser.add_argument(
        "--baseline", required=True, type=Path,
        help="preserved pre-freeze baseline snapshot "
             "(the old 2a903a4a... file; NOT the installed file)")
    parser.add_argument(
        "--target", required=True, type=Path,
        help="immutable committed target artifact "
             "(feature_policy_freeze_target_v1r2.json)")
    parser.add_argument(
        "--applied", required=True, type=Path,
        help="actual installed config path AFTER installation")
    parser.add_argument(
        "--label-ontology", required=True, type=Path,
        help="frozen label_ontology.json")
    parser.add_argument(
        "--spec", required=True, type=Path,
        help="Rev 2 target specification")
    args = parser.parse_args()

    paths = {name: path.resolve()
             for name, path in vars(args).items()}
    checks = {}
    errors = []

    def check(name, ok, detail=""):
        checks[name] = {"pass": bool(ok), "detail": detail}
        if not ok:
            errors.append(name)

    snapshots = {}
    try:
        for name, path in paths.items():
            snapshots[name] = path.read_bytes()

        # 1) byte-level identity of the three distinct inputs
        check("baseline_sha256_is_preserved_old_baseline",
              sha256_bytes(snapshots["baseline"]) == BASELINE_SHA,
              sha256_bytes(snapshots["baseline"]))
        check("target_sha256_is_pinned_artifact",
              sha256_bytes(snapshots["target"]) == TARGET_SHA,
              sha256_bytes(snapshots["target"]))
        check("applied_sha256_equals_target",
              sha256_bytes(snapshots["applied"]) == TARGET_SHA,
              sha256_bytes(snapshots["applied"]))
        check("applied_is_a_separate_actual_path",
              len({paths["applied"], paths["baseline"],
                   paths["target"]}) == 3,
              "baseline/target/applied paths must be distinct")
        check("applied_byte_equal_target",
              snapshots["applied"] == snapshots["target"],
              f"{len(snapshots['applied'])} bytes")
        check("label_ontology_sha256_frozen",
              sha256_bytes(snapshots["label_ontology"]) == ONTOLOGY_SHA,
              sha256_bytes(snapshots["label_ontology"]))

        baseline = parse_unique(snapshots["baseline"])
        target = parse_unique(snapshots["target"])
        applied = parse_unique(snapshots["applied"])
        ontology = parse_unique(snapshots["label_ontology"])
        spec = parse_unique(snapshots["spec"])

        # 2) phase state: before vs after
        base_census = status_census(baseline)
        appl_census = status_census(applied)
        check("baseline_exactly_four_proposed",
              base_census == dict.fromkeys(FLIPS, "proposed"),
              f"census={sorted(base_census.items())}")
        check("applied_exactly_four_frozen",
              appl_census == dict.fromkeys(FLIPS, "frozen"),
              f"census={sorted(appl_census.items())}")
        onto_census = status_census(ontology)
        check("ontology_exactly_61_frozen",
              len(onto_census) == 61
              and set(onto_census.values()) == {"frozen"},
              f"{len(onto_census)} status leaves")

        # 3) semantic dispositions unchanged by installation
        core = "semantic_core.review_outcome_2026_09_04"
        for path in (
                "semantic_core.candidate_examples[0]",
                "semantic_core.candidate_examples[1]",
                f"{core}.resolved_points[0]"):
            check(
                f"disposition_unchanged::{path}",
                dig(applied, f"{path}.semantic_disposition")
                == dig(baseline, f"{path}.semantic_disposition"),
                dig(applied, f"{path}.semantic_disposition"))

        # 4) MI_dir preservation rules on the applied file
        old_mi = dig(baseline, f"{core}.resolved_points[0]")
        new_mi = dig(applied, f"{core}.resolved_points[0]")
        mi = new_mi["evidence_source"]
        check("mi_dir_array_three_strings",
              isinstance(mi, list) and len(mi) == 3
              and all(isinstance(v, str) for v in mi),
              f"len={len(mi) if isinstance(mi, list) else type(mi)}")
        check("mi_dir_first_element_byte_equal_original",
              isinstance(mi, list) and len(mi) > 0
              and mi[0] == old_mi["evidence_source"],
              "element [0] byte-equal")
        check("mi_dir_resolution_unchanged",
              new_mi["resolution"] == old_mi["resolution"],
              f"{len(new_mi['resolution'])} chars")

        # 5) zero admissions on the applied file
        admission = applied["admission_set_this_version"]
        check(
            "zero_admission_all_cores_empty",
            admission["admitted_mapping_count"] == 0
            and admission["three_way_core"] == "EMPTY"
            and set(admission["pairwise_cores"])
            == set(PAIRWISE_CORES)
            and all(v.startswith("EMPTY")
                    for v in admission["pairwise_cores"].values()),
            "count=0, all cores EMPTY")

        # 6) spec bindings verbatim on the applied file
        for key in ("admission_set_this_version", "freeze_metadata"):
            check(f"spec_binding::{key}",
                  applied[key] == target[key] == spec[key],
                  "applied == target == spec")

        # 7) evidence targets and string wording per the spec
        tcs = spec["target_config_state"]
        for item in tcs["evidence_source_targets"]:
            path = item["record"].split(" (")[0]
            if path == "status":
                continue  # root attribution lives in spec/DECISIONS
            if "string-embedded" not in item["record"]:
                path += ".evidence_source"
            check(f"evidence_target::{path}",
                  dig(applied, path) == item["target_value"],
                  "byte-equal to spec target_value")
        for item in tcs["string_target_wording"]:
            check(f"candidate_string::{item['path']}",
                  dig(applied, item["path"]) == item["exact_target"],
                  "byte-equal to spec exact_target")

        # 8) gates still fail-closed on the applied file
        gate_specs = {item["gate"]: item
                      for item in tcs["data_handling_gate_targets"]}
        for gate in GATES:
            actual = applied["data_handling"][gate]
            expected = {key: gate_specs[gate][key] for key in
                        ("current", "target", "authorization",
                         "preconditions")}
            check(f"gate_exact_spec_binding::{gate}",
                  actual == expected,
                  "applied gate object == spec gate object")
            check(
                f"gate_still_requires_authorization::{gate}",
                actual["current"] == "forbidden before protocol freeze"
                and len(actual["preconditions"]) == 6
                and actual["preconditions"][-1].startswith(
                    "separate explicit user authorization"),
                "no gate is unlocked by installation alone")
    except (OSError, UnicodeError, ValueError, KeyError, TypeError,
            IndexError) as exc:
        errors.append(f"{type(exc).__name__}: {exc}")

    # finally: prove the run was read-only (inputs unchanged)
    unchanged = True
    for name, path in paths.items():
        try:
            if path.read_bytes() != snapshots.get(name):
                unchanged = False
                errors.append(f"input_mutated::{name}")
        except OSError as exc:
            unchanged = False
            errors.append(f"{name}: {exc}")
    check("all_inputs_unchanged_by_this_run", unchanged,
          "read-only verification")

    result = {
        "kind": ("feature_policy_target_v1r2_"
                 "post_install_verification"),
        "revision": "#23 Rev 3 entry point (Rev 2 target bytes)",
        "phase": "post-installation",
        "pre_install_tools_not_reinvoked": [
            "scripts/audits/build_feature_policy_target_v1r2.py",
            "scripts/audits/verify_feature_policy_target_v1r2.py",
        ],
        "observed_sha256": {name: sha256_bytes(data)
                            for name, data in snapshots.items()},
        "checks_total": len(checks),
        "failures": errors,
        "all_pass": not errors and bool(checks),
        "authorization_granted": False,
        "data_gates_unlocked": False,
        "scope": ("read-only post-install configuration "
                  "verification; NOT experimental execution "
                  "authorization"),
    }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result["all_pass"] else 1


if __name__ == "__main__":
    sys.exit(main())
