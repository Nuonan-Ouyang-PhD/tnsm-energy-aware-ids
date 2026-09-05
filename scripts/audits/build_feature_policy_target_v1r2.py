#!/usr/bin/env python3
"""Generator for the Rev 2 would-be-effective target config
(artifacts/proposals/feature_policy_freeze_target_v1r2.json).

Re-derives the target bytes from the live baseline config using the
same text-level replacements the application script will apply, then
validates the result and writes the target artifact. The live config
is NEVER modified. Re-runnable with a stable output (deterministic).
"""

import hashlib
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BASELINE = REPO / "config" / "feature_policy.json"
TARGET = REPO / "artifacts" / "proposals" / \
    "feature_policy_freeze_target_v1r2.json"

BASELINE_SHA = (
    "2a903a4a0dd54e4307b7dce24599c39ce62b378b4cd8a95f8a633ffedb321b47"
)

# MI_dir: existing evidence_source string (kept byte-equal as [0])
MI_DIR_ORIGINAL = (
    "references/dataset_docs/n_baiot/meidan2018_arxiv_v1_2026-09-04.pdf"
    " (SHA-256 1fa5bc4d4d2a12c2e93b18c4d876bd83ab7f456797934fcc71c92d"
    "b754811964)"
)

# protocol_indicators: new complete string (Rev 1 zero-admission)
PI_TARGET = (
    "semantic_disposition=unresolved, decision_status=proposed; "
    "REVISED 2026-09-05 (#23 Rev 1) after independent review F23-01: "
    "dataset-native is the mainline this version and NOTHING is "
    "admitted to the pairwise core - the core stays EMPTY. tcp and "
    "udp remain CANDIDATES for a future evidence-complete review "
    "(both sides' official docs describe transport-layer protocol "
    "semantics for them, and the observed TON-IoT proto value set is "
    "tcp 168747 / udp 42015 / icmp 281 per proto census v1+v2), but "
    "the admission claim is WITHDRAWN: the official CICIoT2023 "
    "page-1 documentation is internally inconsistent about the "
    "protocol columns (47-row indicator-style table vs 39-row "
    "'Average no. of ... packets in the window' table), so gates 3, "
    "4, and 7 are unconfirmed for the released CSV; 'per-record "
    "aggregation' and 'whole-record window' phrasing is container "
    "language, not a definition of the measured object. icmp "
    "likewise stays unresolved: the earlier transport-vs-network-"
    "layer wording difference is NOT a proven semantic "
    "incompatibility (Zeek conn logs cover TCP/UDP/ICMP in one "
    "record type); the correct statement is that current evidence "
    "is insufficient for admission, not that incompatibility is "
    "proven. Evidence: datasets/incoming/ton_iot/Network "
    "Features-Description.pdf p.1 row 6; "
    "datasets/incoming/ciciot2023/README.pdf p.1 47-row table rows "
    "28/29/32 and 39-row table rows 23/24/27 (archived PNGs in "
    "references/dataset_docs/ciciot2023/readme_p1_feature_table/). "
    "The remaining CICIoT2023 protocol columns (DHCP/ARP/IGMP/IPv/"
    "LLC and the application-layer set) still have no proposed "
    "TON-IoT counterpart; no correspondence is invented and no "
    "unknown value is interpreted as all-zero indicators. Excluding "
    "ICMP from cross-dataset MAPPING does not delete the 281 ICMP "
    "samples or the native proto feature."
)

# packet_count: new complete string (Rev 1 wording)
PC_TARGET = (
    "semantic_disposition=unresolved, decision_status=proposed; "
    "connection vs flow aggregation object still unconfirmed for the "
    "released CSV; not admitted this version. Evidence: "
    "datasets/incoming/ton_iot/Network Features-Description.pdf p.1 "
    "rows 13/15 (per-connection directional packet counts) vs "
    "datasets/incoming/ciciot2023/README.pdf p.1 row 42 ('Number: "
    "The number of packets in the flow'); the README's two "
    "conflicting page-1 tables leave the released column's "
    "semantics undocumented."
)

# policy root: new admission_set_this_version object
ADMISSION_SET = {
    "three_way_core": "EMPTY",
    "pairwise_cores": {
        "ton_iot__ciciot2023": (
            "EMPTY (protocol_indicators unresolved/candidate; "
            "packet_count unresolved)"
        ),
        "ton_iot__n_baiot": "EMPTY (structural)",
        "ciciot2023__n_baiot": "EMPTY (structural)",
    },
    "admitted_mapping_count": 0,
    "admitted_mapping_note": (
        "ZERO ADMISSIONS is the deliberate Rev 1 outcome per the "
        "user's Rev-1 verdict: dataset-native is the mainline; "
        "tcp/udp are retained candidates; an empty pairwise core is "
        "reported honestly and no alignment is forced. The freeze "
        "(decision_status=frozen) locks THIS review decision; frozen "
        "never means admitted."
    ),
    "future_admission_path": (
        "A future version may admit specific mappings only with: "
        "(1) a complete seven-gate audit record per mapping "
        "including aggregation_level, time_window, directionality, "
        "missing_value_policy, both-side formulas, and per-gate "
        "anchored evidence; (2) resolution of the official-source "
        "internal inconsistency (which README table corresponds to "
        "the released 39-column CSV), or a documented decision on "
        "which description governs with justification; (3) separate "
        "explicit user authorization."
    ),
}

# policy root: new freeze_metadata object
FREEZE_METADATA = {
    "freeze_id": "FEATURE-POLICY-20260905-V1-FROZEN",
    "applied_by": (
        "#24 only, under its own separate explicit user authorization"
    ),
    "proposal_id": (
        "FEATURE-POLICY-20260905-V1-PROPOSED (DECISIONS.md #23, "
        "superseded in part by #23 Rev 1)"
    ),
    "frozen_semantics": (
        "decision_status=frozen locks the review decision of this "
        "version; it does not assert any mapping holds, does not "
        "resolve the unresolved, does not bar a future evidence-based "
        "version, and does not lift the materialization/splitting/"
        "training gates by itself (the gate target values take effect "
        "only as part of the same #24 change, each individually "
        "authorized)"
    ),
    "out_of_scope": [
        "config/label_ontology.json (frozen, byte-identical "
        "8a055e2e...)",
        "frozen dataset-level mapping tables and fixed_decisions",
        "audit_gates, mapping_record_fields, and policy texts "
        "(direction/paper_positioning/empty-core honesty)",
        "proto census artifacts (audit evidence, immutable; v1+v2)",
        "ton_iot_exclusions and primary_native_feature_sets (native "
        "sets unchanged; only status and evidence fields change)",
    ],
}

GATE_TARGET = (
    "permitted after protocol freeze (#24), subject to the "
    "label-ontology chain, the feature/label protocol freeze, and "
    "the standing experimental discipline (no split changes after "
    "formal experiments start; encoder fitting on the training split "
    "only; deterministic rotation and order-invariance gates)"
)

GATE_AUTH = (
    "individually authorized at #24 only; stays forbidden until then"
)

GATE_PRE = [
    "feature_policy.json root status is frozen AND freeze_metadata "
    "is present in the same applied config",
    "label_ontology.json is frozen (SHA-256 8a055e2e...6fab class) "
    "and byte-identical to its frozen state",
    "config matches the recorded target SHA for this exact freeze "
    "(feature_policy_freeze_target_v1r2.json)",
    "the four structured flips and all per-record evidence targets "
    "applied exactly (application verification script green)",
    "zero actual admissions this version "
    "(admission_set_this_version.admitted_mapping_count == 0)",
    "separate explicit user authorization for THIS gate obtained "
    "and recorded in DECISIONS.md",
]

# The seven replacement operations (order matters: byte offsets shift,
# so replacements run bottom-up in the builder).
REPLACEMENTS = [
    # (id, old, new) - old must occur exactly once in the baseline
    {
        "id": "op7_root_additions",
        "old": (
            '    "disk_budget_note": "design work reads inventory '
            'JSONs and small documents only; no data copies are '
            'created"\n  }\n}'
        ),
        "new": (
            '    "disk_budget_note": "design work reads inventory '
            'JSONs and small documents only; no data copies are '
            'created"\n  },\n'
            '  "admission_set_this_version": '
            + json.dumps(ADMISSION_SET, indent=2, ensure_ascii=False)
            .replace("\n", "\n  ")
            + ',\n'
            '  "freeze_metadata": '
            + json.dumps(FREEZE_METADATA, indent=2, ensure_ascii=False)
            .replace("\n", "\n  ")
            + '\n}'
        ),
    },
    {
        "id": "op6_gate_targets",
        "old": (
            '    "materialization": "forbidden before protocol freeze",'
            '\n    "splitting": "forbidden before protocol freeze",'
            '\n    "training": "forbidden before protocol freeze",'
        ),
        "new": (
            '    "materialization": {\n'
            '      "current": "forbidden before protocol freeze",\n'
            '      "target": "' + GATE_TARGET + '",\n'
            '      "preconditions": [\n'
            + "".join(
                '        "' + p + '"' + (",\n" if i < 5 else "\n")
                for i, p in enumerate(GATE_PRE)
            )
            + '      ],\n'
            '      "authorization": "' + GATE_AUTH + '"\n'
            '    },\n'
            '    "splitting": {\n'
            '      "current": "forbidden before protocol freeze",\n'
            '      "target": "' + GATE_TARGET + '",\n'
            '      "preconditions": [\n'
            + "".join(
                '        "' + p + '"' + (",\n" if i < 5 else "\n")
                for i, p in enumerate(GATE_PRE)
            )
            + '      ],\n'
            '      "authorization": "' + GATE_AUTH + '"\n'
            '    },\n'
            '    "training": {\n'
            '      "current": "forbidden before protocol freeze",\n'
            '      "target": "' + GATE_TARGET + '",\n'
            '      "preconditions": [\n'
            + "".join(
                '        "' + p + '"' + (",\n" if i < 5 else "\n")
                for i, p in enumerate(GATE_PRE)
            )
            + '      ],\n'
            '      "authorization": "' + GATE_AUTH + '"\n'
            '    },'
        ),
    },
    {
        "id": "op5_status_flip_4",
        "old": (
            '          "semantic_disposition": "derived",\n'
            '          "decision_status": "proposed",\n'
            '          "evidence_source": "' + MI_DIR_ORIGINAL + '"'
        ),
        "new": (
            '          "semantic_disposition": "derived",\n'
            '          "decision_status": "frozen",\n'
            '          "evidence_source": [\n'
            '            "' + MI_DIR_ORIGINAL + '",\n'
            '            "Table 2 and the \'Feature extraction\' '
            'section of the same PDF: 23 features per time scale '
            'over the four aggregation objects (Source IP, Source '
            'MAC-IP, Channel, Socket); MI_dir attributed to Source '
            'MAC-IP by elimination from the frozen 115-column group '
            'widths",\n'
            '            "references/dataset_docs/n_baiot/'
            'uci_dataset_page_2026-09-04.html (SHA-256 e0b79978d166b'
            '601ce1e8480625d8ad9fe40b328ad92d66f8eebde9730b5d57f) '
            'variable information section: defines the stream '
            'aggregation prefixes and decay factors L5/L3/L1/L0.1/'
            'L0.01 but NOT MI_dir (the gap this resolution fills)"\n'
            '          ]'
        ),
    },
    {
        "id": "op4_pi_pc_wording",
        "old": (
            '          "protocol_indicators": "semantic_disposition='
            'derived, decision_status=proposed; requires TON-IoT '
            'proto value enumeration first",\n'
            '          "packet_count": "semantic_disposition='
            'unresolved, decision_status=proposed; connection vs '
            'flow aggregation object unconfirmed"'
        ),
        "new": (
            '          "protocol_indicators": "' + PI_TARGET + '",\n'
            '          "packet_count": "' + PC_TARGET + '"'
        ),
    },
    {
        "id": "op3_flip3_decay",
        "old": (
            '        "semantic_disposition": "rejected",\n'
            '        "decision_status": "proposed",\n'
            '        "gate_note": "REVIEW OUTCOME 2026-09-04: '
            'damped-window stream statistics'
        ),
        "new": (
            '        "semantic_disposition": "rejected",\n'
            '        "decision_status": "frozen",\n'
            '        "evidence_source": [\n'
            '          "references/dataset_docs/n_baiot/'
            'meidan2018_arxiv_v1_2026-09-04.pdf (SHA-256 1fa5bc4d4d2a'
            '12c2e93b18c4d876bd83ab7f456797934fcc71c92db754811964) '
            'Table 2 + \'Feature extraction\' section: 23 features '
            'per time scale over four aggregation objects (Source '
            'IP, Source MAC-IP, Channel, Socket) with decay factors '
            'L5/L3/L1/L0.1/L0.01",\n'
            '          "references/dataset_docs/n_baiot/'
            'uci_dataset_page_2026-09-04.html (SHA-256 e0b79978d166b'
            '601ce1e8480625d8ad9fe40b328ad92d66f8eebde9730b5d57f) '
            'variable information: same decay/statistics scheme; the '
            'released CSVs of TON-IoT and CICIoT2023 contain no '
            'damped-window stream statistics columns"\n'
            '        ],\n'
            '        "gate_note": "REVIEW OUTCOME 2026-09-04: '
            'damped-window stream statistics'
        ),
    },
    {
        "id": "op2_flip2_bytes",
        "old": (
            '        "semantic_disposition": "unresolved",\n'
            '        "decision_status": "proposed",\n'
            '        "gate_note": "REVIEW OUTCOME 2026-09-04: '
            'different physical quantities'
        ),
        "new": (
            '        "semantic_disposition": "unresolved",\n'
            '        "decision_status": "frozen",\n'
            '        "evidence_source": [\n'
            '          "datasets/incoming/ton_iot/Network '
            'Features-Description.pdf (SHA-256 b1f63453029855e084290'
            'a2f79554eaa7e3b85f8d53fb0ea4605966ef25ebe3b) p.1 rows '
            '9-10: src_bytes/dst_bytes are payload bytes of TCP '
            'sequence numbers (per-connection quantities); consulted '
            'as the TON-IoT side definition",\n'
            '          "datasets/incoming/ciciot2023/README.pdf '
            '(SHA-256 0f48daba395be03985f612ce706d33f1a25e4008cb94c3'
            'ad7b6f6332fbdbee92) p.1 47-row table row 35 \'Tot sum: '
            'Summation of packets lengths in flow\' and p.1 39-row '
            'window table row 30 \'Tot Sum: Total packet length '
            'within the aggregated packets (window)\'; consulted as '
            'the CICIoT2023 side definition; the two tables also '
            'differ from each other (flow vs window)"\n'
            '        ],\n'
            '        "gate_note": "REVIEW OUTCOME 2026-09-04: '
            'different physical quantities'
        ),
    },
    {
        "id": "op1_root_flip",
        "old": '"kind": "feature_policy",\n  "status": "proposed",',
        "new": '"kind": "feature_policy",\n  "status": "frozen",',
    },
]


def build_target_text(baseline_text):
    text = baseline_text
    applied = []
    for op in REPLACEMENTS:
        n = text.count(op["old"])
        if n != 1:
            raise SystemExit(
                f"op {op['id']}: anchor count {n} != 1; aborting"
            )
        text = text.replace(op["old"], op["new"])
        applied.append(op["id"])
    return text, applied


def main():
    raw = BASELINE.read_bytes()
    baseline_text = raw.decode("utf-8")
    baseline_sha = hashlib.sha256(raw).hexdigest()
    if baseline_sha != BASELINE_SHA:
        raise SystemExit(
            f"baseline drift: {baseline_sha} != {BASELINE_SHA}"
        )

    target_text, applied = build_target_text(baseline_text)

    # validate target: JSON parse + structural checks
    target_obj = json.loads(target_text)
    assert target_obj["status"] == "frozen"
    examples = target_obj["semantic_core"]["candidate_examples"]
    assert examples[0]["decision_status"] == "frozen"
    assert examples[1]["decision_status"] == "frozen"
    assert examples[0]["evidence_source"][0].startswith(
        "datasets/incoming/ton_iot/"
    )
    resolved = target_obj["semantic_core"][
        "review_outcome_2026_09_04"]["resolved_points"][0]
    assert resolved["decision_status"] == "frozen"
    assert resolved["evidence_source"][0] == MI_DIR_ORIGINAL, (
        "MI_dir first element must be byte-equal to the original"
    )
    pc = target_obj["semantic_core"]["review_outcome_2026_09_04"][
        "pairwise_cores"]["ton_iot__ciciot2023"]
    assert pc["protocol_indicators"] == PI_TARGET
    assert pc["packet_count"] == PC_TARGET
    dh = target_obj["data_handling"]
    for gate in ("materialization", "splitting", "training"):
        assert dh[gate]["preconditions"][0].startswith(
            "feature_policy.json root status is frozen"
        )
    assert target_obj["admission_set_this_version"][
        "admitted_mapping_count"] == 0
    assert target_obj["freeze_metadata"]["freeze_id"] == (
        "FEATURE-POLICY-20260905-V1-FROZEN"
    )

    TARGET.write_text(target_text, encoding="utf-8", newline="")
    target_sha = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    summary = {
        "baseline_sha256": baseline_sha,
        "target_sha256": target_sha,
        "applied_operations": applied,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    sys.exit(main())
