#!/usr/bin/env python3
"""Read-only post-install verification for the Rev 2 target config.

This verifier is deliberately separate from
``verify_feature_policy_target_v1r2.py``.  The original verifier is a
PRE-INSTALL reproducibility check: it reads the old live baseline and rebuilds
the target in memory.  This verifier runs only AFTER installation and keeps
three inputs distinct:

* ``--baseline``: a preserved copy of the old pre-freeze baseline;
* ``--target``: the immutable complete target artifact; and
* ``--applied``: the actual installed ``config/feature_policy.json``.

It does not install a config, invoke the generator, read dataset CSVs, or write
any input or evidence artifact.  Its JSON report is written to stdout only.
Exit 0 means the installed bytes and state match the reviewed target; it does
not authorize #24 or unlock materialization, splitting, or training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any


BASELINE_SHA = (
    "2a903a4a0dd54e4307b7dce24599c39ce62b378b4cd8a95f8a633ffedb321b47"
)
TARGET_SHA = (
    "e81a55c16f9439b0356295353e8b342de19d5c5606d868952592f913beda714b"
)
LABEL_ONTOLOGY_SHA = (
    "8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab"
)
FLIP_PATHS = {
    "status",
    "semantic_core.candidate_examples[0].decision_status",
    "semantic_core.candidate_examples[1].decision_status",
    "semantic_core.review_outcome_2026_09_04.resolved_points[0]"
    ".decision_status",
}
GATES = ("materialization", "splitting", "training")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON keys instead of silently accepting the last."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def parse_json_object(data: bytes) -> dict[str, Any]:
    result = json.loads(
        data.decode("utf-8"), object_pairs_hook=unique_object
    )
    if not isinstance(result, dict):
        raise ValueError("expected a JSON object at the document root")
    return result


def dig(obj: Any, path: str) -> Any:
    """Resolve a dotted path containing optional list indexes."""
    for key, index in re.findall(r"([^\.\[\]]+)|\[(\d+)\]", path):
        obj = obj[key] if key else obj[int(index)]
    return obj


def status_census(obj: Any, prefix: str = "") -> dict[str, str]:
    """Return every structured status/decision_status string by path."""
    result: dict[str, str] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else key
            if key in ("status", "decision_status") and isinstance(
                value, str
            ):
                result[path] = value
            result.update(status_census(value, path))
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            result.update(status_census(value, f"{prefix}[{index}]"))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--baseline",
        required=True,
        type=Path,
        help="preserved pre-freeze baseline; never the installed path",
    )
    parser.add_argument(
        "--target",
        required=True,
        type=Path,
        help="immutable complete target artifact",
    )
    parser.add_argument(
        "--applied",
        required=True,
        type=Path,
        help="actual config/feature_policy.json after installation",
    )
    parser.add_argument(
        "--label-ontology",
        required=True,
        type=Path,
        help="actual config/label_ontology.json",
    )
    parser.add_argument(
        "--spec",
        required=True,
        type=Path,
        help="target specification containing the reviewed bindings",
    )
    args = parser.parse_args()

    paths = {name: path.resolve() for name, path in vars(args).items()}
    checks: dict[str, bool] = {}
    errors: list[str] = []
    snapshots: dict[str, bytes] = {}

    def check(name: str, value: bool) -> None:
        checks[name] = bool(value)

    try:
        snapshots = {
            name: path.read_bytes() for name, path in paths.items()
        }
        check(
            "baseline_sha256",
            sha256_bytes(snapshots["baseline"]) == BASELINE_SHA,
        )
        check(
            "target_sha256",
            sha256_bytes(snapshots["target"]) == TARGET_SHA,
        )
        check(
            "applied_sha256",
            sha256_bytes(snapshots["applied"]) == TARGET_SHA,
        )
        check(
            "baseline_target_applied_are_distinct_paths",
            len(
                {
                    paths["baseline"],
                    paths["target"],
                    paths["applied"],
                }
            )
            == 3,
        )
        check(
            "applied_byte_equal_target",
            snapshots["applied"] == snapshots["target"],
        )
        check(
            "label_ontology_sha256",
            sha256_bytes(snapshots["label_ontology"])
            == LABEL_ONTOLOGY_SHA,
        )

        baseline = parse_json_object(snapshots["baseline"])
        target = parse_json_object(snapshots["target"])
        applied = parse_json_object(snapshots["applied"])
        ontology = parse_json_object(snapshots["label_ontology"])
        spec = parse_json_object(snapshots["spec"])

        check(
            "baseline_exactly_four_proposed",
            status_census(baseline)
            == dict.fromkeys(FLIP_PATHS, "proposed"),
        )
        check(
            "applied_exactly_four_frozen",
            status_census(applied) == dict.fromkeys(FLIP_PATHS, "frozen"),
        )
        ontology_statuses = status_census(ontology)
        check(
            "ontology_exactly_61_frozen",
            len(ontology_statuses) == 61
            and set(ontology_statuses.values()) == {"frozen"},
        )

        review_path = "semantic_core.review_outcome_2026_09_04"
        disposition_paths = (
            "semantic_core.candidate_examples[0]",
            "semantic_core.candidate_examples[1]",
            review_path + ".resolved_points[0]",
        )
        for path in disposition_paths:
            check(
                "disposition_unchanged::" + path,
                dig(applied, path + ".semantic_disposition")
                == dig(baseline, path + ".semantic_disposition"),
            )

        old_mi = dig(baseline, review_path + ".resolved_points[0]")
        new_mi = dig(applied, review_path + ".resolved_points[0]")
        mi_evidence = new_mi["evidence_source"]
        check(
            "mi_array_three_strings",
            isinstance(mi_evidence, list)
            and len(mi_evidence) == 3
            and all(isinstance(value, str) for value in mi_evidence),
        )
        check(
            "mi_original_first_item",
            isinstance(mi_evidence, list)
            and bool(mi_evidence)
            and mi_evidence[0] == old_mi["evidence_source"],
        )
        check(
            "mi_resolution_unchanged",
            new_mi["resolution"] == old_mi["resolution"],
        )

        admission = applied["admission_set_this_version"]
        check(
            "zero_admission_all_cores_empty",
            admission["admitted_mapping_count"] == 0
            and admission["three_way_core"] == "EMPTY"
            and set(admission["pairwise_cores"])
            == {
                "ton_iot__ciciot2023",
                "ton_iot__n_baiot",
                "ciciot2023__n_baiot",
            }
            and all(
                value.startswith("EMPTY")
                for value in admission["pairwise_cores"].values()
            ),
        )

        for key in ("admission_set_this_version", "freeze_metadata"):
            check(
                "spec_binding::" + key,
                applied[key] == target[key] == spec[key],
            )

        target_state = spec["target_config_state"]
        for item in target_state["evidence_source_targets"]:
            path = item["record"].split(" (")[0]
            if path == "status":
                continue
            if "string-embedded" not in item["record"]:
                path += ".evidence_source"
            check(
                "evidence_target::" + path,
                dig(applied, path) == item["target_value"],
            )

        for item in target_state["string_target_wording"]:
            check(
                "candidate_string::" + item["path"],
                dig(applied, item["path"]) == item["exact_target"],
            )

        gate_specs = {
            item["gate"]: item
            for item in target_state["data_handling_gate_targets"]
        }
        for gate in GATES:
            actual = applied["data_handling"][gate]
            expected = {
                key: gate_specs[gate][key]
                for key in (
                    "current",
                    "target",
                    "authorization",
                    "preconditions",
                )
            }
            check("gate_exact_spec_binding::" + gate, actual == expected)
            check(
                "gate_still_requires_authorization::" + gate,
                actual["current"] == "forbidden before protocol freeze"
                and len(actual["preconditions"]) == 6
                and "separate explicit user authorization"
                in actual["preconditions"][-1],
            )
    except (
        OSError,
        UnicodeError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
    ) as exc:
        errors.append(f"{type(exc).__name__}: {exc}")
    finally:
        for name, original in snapshots.items():
            try:
                check(
                    "input_unchanged::" + name,
                    paths[name].read_bytes() == original,
                )
            except OSError as exc:
                errors.append(f"{name}: {exc}")

    failures = [name for name, passed in checks.items() if not passed]
    all_pass = bool(checks) and not failures and not errors
    print(
        json.dumps(
            {
                "kind": "feature_policy_v1r2_postinstall_verification",
                "all_pass": all_pass,
                "checks_total": len(checks),
                "failures": failures,
                "errors": errors,
                "paths": {name: str(path) for name, path in paths.items()},
                "observed_sha256": {
                    name: sha256_bytes(data)
                    for name, data in snapshots.items()
                },
                "checks": checks,
                "authorization_granted": False,
                "data_gates_unlocked": False,
                "scope": (
                    "Read-only installed-configuration verification; "
                    "not execution authorization"
                ),
            },
            indent=2,
            ensure_ascii=False,
        )
    )
    return 0 if all_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
