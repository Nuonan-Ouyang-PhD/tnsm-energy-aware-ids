#!/usr/bin/env python3
"""Application verification for the Rev 2 would-be-effective target
config (artifact feature_policy_freeze_target_v1r2.json).

Applies the seven text-level operations to the live baseline in
memory, byte-compares the result against the committed target
artifact, runs the machine checks demanded by the independent review
(exactly 4 structured status flips, semantic_disposition boundaries,
MI_dir type/preservation rules, zero actual admissions, unique
binding points for admission_set/freeze_metadata, gate preconditions
as standalone structured fields), accounts for every changed byte,
and writes two artifacts into artifacts/proposals/:

  - feature_policy_target_v1r2_diff.json   (machine-readable)
  - feature_policy_target_v1r2_verify.log  (human-readable log)

The live config is NEVER modified. Exit code 0 = all checks green.
"""

import difflib
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASELINE = REPO / "config" / "feature_policy.json"
TARGET = (REPO / "artifacts" / "proposals"
          / "feature_policy_freeze_target_v1r2.json")
DIFF_OUT = (REPO / "artifacts" / "proposals"
            / "feature_policy_target_v1r2_diff.json")
LOG_OUT = (REPO / "artifacts" / "proposals"
           / "feature_policy_target_v1r2_verify.log")
GENERATOR = (REPO / "scripts" / "audits"
             / "build_feature_policy_target_v1r2.py")

BASELINE_SHA = (
    "2a903a4a0dd54e4307b7dce24599c39ce62b378b4cd8a95f8a633ffedb321b47"
)
TARGET_SHA = (
    "e81a55c16f9439b0356295353e8b342de19d5c5606d868952592f913beda714b"
)
LABEL_ONTOLOGY_SHA = (
    "8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab"
)

FLIP_PATHS = [
    "status",
    "semantic_core.candidate_examples[0].decision_status",
    "semantic_core.candidate_examples[1].decision_status",
    "semantic_core.review_outcome_2026_09_04.resolved_points[0]"
    ".decision_status",
]

MI_DIR_ORIGINAL = (
    "references/dataset_docs/n_baiot/meidan2018_arxiv_v1_2026-09-04.pdf"
    " (SHA-256 1fa5bc4d4d2a12c2e93b18c4d876bd83ab7f456797934fcc71c92d"
    "b754811964)"
)


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def load_generator():
    spec = importlib.util.spec_from_file_location(
        "fp_target_builder", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def dig(obj, path):
    """Resolve a dotted path with [index] suffixes, e.g.
    semantic_core.candidate_examples[0].decision_status."""
    import re
    cur = obj
    for part in path.split("."):
        m = re.match(r"^([^\[\]]*)((?:\[\d+\])*)$", part)
        name, brackets = m.group(1), m.group(2)
        if name:
            cur = cur[name]
        for idx in re.findall(r"\[(\d+)\]", brackets):
            cur = cur[int(idx)]
    return cur


def enumerate_leaves(node, path=""):
    """All leaf (path, value) pairs; lists enumerate indices."""
    out = []
    if isinstance(node, dict):
        for k, v in node.items():
            p = f"{path}.{k}" if path else k
            out.extend(enumerate_leaves(v, p))
    elif isinstance(node, list):
        for i, v in enumerate(node):
            out.extend(enumerate_leaves(v, f"{path}[{i}]"))
    else:
        out.append((path, node))
    return out


def main():
    log_lines = []

    def log(msg):
        log_lines.append(msg)

    checks = {}
    failures = []

    def check(name, ok, detail=""):
        checks[name] = {"pass": bool(ok), "detail": detail}
        log(f"[{'PASS' if ok else 'FAIL'}] {name}" +
            (f" - {detail}" if detail else ""))
        if not ok:
            failures.append(name)

    baseline_raw = BASELINE.read_bytes()
    baseline_sha = sha256_bytes(baseline_raw)
    check("baseline_unchanged", baseline_sha == BASELINE_SHA,
          baseline_sha)
    target_raw = TARGET.read_bytes()
    target_sha = sha256_bytes(target_raw)
    check("target_artifact_sha", target_sha == TARGET_SHA, target_sha)

    builder = load_generator()
    rebuilt, applied_ops = builder.build_target_text(
        baseline_raw.decode("utf-8"))
    rebuilt_raw = rebuilt.encode("utf-8")
    check("rebuild_from_generator_byte_identical",
          rebuilt_raw == target_raw,
          f"ops={applied_ops}")

    base_obj = json.loads(baseline_raw.decode("utf-8"))
    tgt_obj = json.loads(target_raw.decode("utf-8"))

    # 1. exactly 4 structured status flips, dispositions unchanged
    flip_report = []
    for path in FLIP_PATHS:
        cur = dig(base_obj, path)
        new = dig(tgt_obj, path)
        flip_report.append({"path": path, "before": cur, "after": new})
        check(f"flip::{path}", cur == "proposed" and new == "frozen",
              f"{cur} -> {new}")

    def status_census(node, path=""):
        hits = []
        if isinstance(node, dict):
            for k, v in node.items():
                child = f"{path}.{k}" if path else k
                if k in ("status", "decision_status") and isinstance(
                        v, str):
                    hits.append((child, v))
                hits.extend(status_census(v, child))
        elif isinstance(node, list):
            for i, v in enumerate(node):
                hits.extend(status_census(v, f"{path}[{i}]"))
        return hits

    after_census = status_census(tgt_obj)
    after_set = set(after_census)
    expected_after = {("status", "frozen"),
                      ("semantic_core.candidate_examples[0]"
                       ".decision_status", "frozen"),
                      ("semantic_core.candidate_examples[1]"
                       ".decision_status", "frozen"),
                      ("semantic_core.review_outcome_2026_09_04"
                       ".resolved_points[0].decision_status", "frozen")}
    check("status_census_exactly_four_frozen_no_proposed",
          len(after_census) == 4 and set(after_census) == expected_after,
          f"census={sorted(after_census)}")

    disp_base = {
        "semantic_core.candidate_examples[0].semantic_disposition":
            "unresolved",
        "semantic_core.candidate_examples[1].semantic_disposition":
            "rejected",
        "semantic_core.review_outcome_2026_09_04.resolved_points[0]"
        ".semantic_disposition": "derived",
    }
    for path, want in disp_base.items():
        check(f"disposition_unchanged::{path}",
              dig(tgt_obj, path) == want, dig(tgt_obj, path))

    # 2. MI_dir type/preservation rules
    mi_old = dig(base_obj, "semantic_core.review_outcome_2026_09_04"
                 ".resolved_points[0].evidence_source")
    mi_new = dig(tgt_obj, "semantic_core.review_outcome_2026_09_04"
                 ".resolved_points[0].evidence_source")
    check("mi_dir_type_string_to_array",
          isinstance(mi_old, str) and isinstance(mi_new, list)
          and all(isinstance(x, str) for x in mi_new),
          f"str -> list[{len(mi_new)}]")
    check("mi_dir_first_element_byte_equal_original",
          mi_new[0] == MI_DIR_ORIGINAL and mi_new[0] == mi_old,
          "byte-equal")
    check("mi_dir_array_has_three_elements", len(mi_new) == 3,
          f"len={len(mi_new)}")
    res_old = dig(base_obj, "semantic_core.review_outcome_2026_09_04"
                  ".resolved_points[0].resolution")
    res_new = dig(tgt_obj, "semantic_core.review_outcome_2026_09_04"
                  ".resolved_points[0].resolution")
    check("mi_dir_resolution_text_unchanged", res_old == res_new,
          f"{len(res_old)} chars")

    # 3. zero actual admissions + unique binding points
    adm = tgt_obj["admission_set_this_version"]
    check("admission_set_zero", adm["admitted_mapping_count"] == 0
          and adm["three_way_core"] == "EMPTY"
          and all("EMPTY" in v for v in adm["pairwise_cores"].values()),
          "count=0, all cores EMPTY")
    check("admission_set_bound_in_target_config",
          "admission_set_this_version" in tgt_obj
          and "admission_set_this_version" not in base_obj,
          "root-level key added by the target bytes")
    fm = tgt_obj["freeze_metadata"]
    check("freeze_metadata_bound_in_target_config",
          fm["freeze_id"] == "FEATURE-POLICY-20260905-V1-FROZEN"
          and "freeze_metadata" not in base_obj,
          fm["freeze_id"])
    pi_str = dig(tgt_obj, "semantic_core.review_outcome_2026_09_04"
                 ".pairwise_cores.ton_iot__ciciot2023"
                 ".protocol_indicators")
    pc_str = dig(tgt_obj, "semantic_core.review_outcome_2026_09_04"
                 ".pairwise_cores.ton_iot__ciciot2023.packet_count")
    check("protocol_indicators_string_unresolved_no_derived",
          isinstance(pi_str, str)
          and "semantic_disposition=unresolved" in pi_str
          and "semantic_disposition=derived" not in pi_str
          and "decision_status=proposed" in pi_str
          and "NOTHING is admitted" in pi_str,
          "string retained, unresolved/proposed, zero admission")
    check("packet_count_string_unresolved",
          isinstance(pc_str, str)
          and "semantic_disposition=unresolved" in pc_str
          and "not admitted this version" in pc_str,
          "string retained, unresolved")
    no_new_status_key = (
        "decision_status" not in dig(
            tgt_obj,
            "semantic_core.review_outcome_2026_09_04.pairwise_cores"
            ".ton_iot__ciciot2023")
    )
    check("pi_pc_gain_no_new_status_fields", no_new_status_key,
          "final 4-path enumeration stays final")

    # 4. gates: object targets with standalone structured preconditions
    for gate in ("materialization", "splitting", "training"):
        old = dig(base_obj, f"data_handling.{gate}")
        new = dig(tgt_obj, f"data_handling.{gate}")
        ok = (isinstance(old, str) and isinstance(new, dict)
              and new["current"] == "forbidden before protocol freeze"
              and new["target"].startswith("permitted after")
              and isinstance(new["preconditions"], list)
              and len(new["preconditions"]) >= 5
              and all(isinstance(p, str) and p.strip()
                      for p in new["preconditions"])
              and new["preconditions"][0].startswith(
                  "feature_policy.json root status is frozen")
              and new["preconditions"][-1].startswith(
                  "separate explicit user authorization")
              and isinstance(new["authorization"], str)
              and new["authorization"].strip())
        check(f"gate_structured::{gate}", ok,
              f"str -> dict with {len(new['preconditions'])} "
              "precondition fields")
    gates_same = all(
        dig(tgt_obj, f"data_handling.{a}") == dig(tgt_obj,
                                                  f"data_handling.{b}")
        for a, b in (("materialization", "splitting"),
                     ("splitting", "training")))
    check("gate_targets_deterministic_and_identical", gates_same,
          "materialization == splitting == training")

    # 5. untouched-policy byte accounting (key order + untouched leaves)
    base_leaves = dict(enumerate_leaves(base_obj))
    tgt_leaves = dict(enumerate_leaves(tgt_obj))
    removed = sorted(set(base_leaves) - set(tgt_leaves))
    added = sorted(set(tgt_leaves) - set(base_leaves))
    changed = sorted(
        p for p in (set(base_leaves) & set(tgt_leaves))
        if base_leaves[p] != tgt_leaves[p])
    # type-conversion artifacts: these 4 leaf paths disappear because
    # their value changed type (string -> object / string -> array);
    # every replacement leaf is accounted in `added` above
    type_conversions = sorted([
        "data_handling.materialization",
        "data_handling.splitting",
        "data_handling.training",
        "semantic_core.review_outcome_2026_09_04.resolved_points[0]"
        ".evidence_source",
    ])
    unexpected_removed = sorted(set(removed) - set(type_conversions))
    check("removed_leaves_only_the_4_type_conversions",
          not unexpected_removed,
          f"removed={removed} unexpected={unexpected_removed}")

    pi_leaf = ("semantic_core.review_outcome_2026_09_04.pairwise_cores"
               ".ton_iot__ciciot2023.protocol_indicators")
    pc_leaf = ("semantic_core.review_outcome_2026_09_04.pairwise_cores"
               ".ton_iot__ciciot2023.packet_count")
    expected_added = sorted(
        p for p in added
        if (p.startswith("semantic_core.candidate_examples[0]"
                         ".evidence_source[")
            or p.startswith("semantic_core.candidate_examples[1]"
                            ".evidence_source[")
            or p.startswith("semantic_core.review_outcome_2026_09_04"
                            ".resolved_points[0].evidence_source[")
            or p.startswith("data_handling.materialization."
                            "preconditions[")
            or p.startswith("data_handling.splitting.preconditions[")
            or p.startswith("data_handling.training.preconditions[")
            or p.startswith("admission_set_this_version.")
            or p.startswith("freeze_metadata.")
            or p in ("data_handling.materialization.current",
                     "data_handling.materialization.target",
                     "data_handling.materialization.authorization",
                     "data_handling.splitting.current",
                     "data_handling.splitting.target",
                     "data_handling.splitting.authorization",
                     "data_handling.training.current",
                     "data_handling.training.target",
                     "data_handling.training.authorization")
            or p == pi_leaf
            or p == pc_leaf)
    )
    unexpected_added = sorted(set(added) - set(expected_added))
    check("added_leaves_exactly_as_enumerated", not unexpected_added,
          f"unexpected={unexpected_added}")
    expected_changed = sorted(
        ["status",
         "semantic_core.candidate_examples[0].decision_status",
         "semantic_core.candidate_examples[1].decision_status",
         "semantic_core.review_outcome_2026_09_04.resolved_points[0]"
         ".decision_status",
         pi_leaf,
         pc_leaf])
    unexpected_changed = sorted(set(changed) - set(expected_changed))
    check("changed_leaves_exactly_the_6_expected",
          not unexpected_changed,
          f"changed={changed} unexpected={unexpected_changed}")
    check("changed_leaves_complete",
          set(changed) == set(expected_changed),
          "4 flips + 2 string rewordings")

    # 6. textual diff (unified, 3-line context) as evidence artifact
    diff_lines = list(difflib.unified_diff(
        baseline_raw.decode("utf-8").splitlines(keepends=True),
        target_raw.decode("utf-8").splitlines(keepends=True),
        fromfile="config/feature_policy.json (baseline 2a903a4a)",
        tofile="target (feature_policy_freeze_target_v1r2.json)",
        n=3))
    log("")
    log("unified diff hunk headers:")
    for line in diff_lines:
        if line.startswith("@@"):
            log("  " + line.rstrip())

    # unchanged sanity: label_ontology untouched on disk
    lo_sha = sha256_bytes((REPO / "config" / "label_ontology.json")
                          .read_bytes())
    check("label_ontology_still_frozen", lo_sha == LABEL_ONTOLOGY_SHA,
          lo_sha)

    result = {
        "kind": "feature_policy_target_v1r2_application_verification",
        "baseline_sha256": baseline_sha,
        "target_artifact_sha256": target_sha,
        "generator_script": "scripts/audits/"
            "build_feature_policy_target_v1r2.py",
        "application_operations_in_order": applied_ops,
        "status_flip_report": flip_report,
        "leaf_accounting": {
            "removed": removed,
            "added": added,
            "value_changed": changed,
        },
        "checks": checks,
        "all_pass": not failures,
    }
    DIFF_OUT.write_text(json.dumps(result, indent=2, ensure_ascii=False)
                        + "\n", encoding="utf-8", newline="")
    LOG_OUT.write_text("\n".join(log_lines) + "\n", encoding="utf-8",
                       newline="")

    print(json.dumps({
        "all_pass": not failures,
        "checks_total": len(checks),
        "checks_failed": failures,
        "diff_artifact": str(DIFF_OUT.relative_to(REPO)),
        "log_artifact": str(LOG_OUT.relative_to(REPO)),
    }, indent=2))
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
