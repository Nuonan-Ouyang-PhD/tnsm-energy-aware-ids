#!/usr/bin/env python3
"""Package-only verifier for the materialization executor V1R2 evidence."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Tuple


class DuplicateKeyError(ValueError):
    pass


def no_duplicates(pairs: Iterable[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateKeyError("duplicate JSON key: %s" % key)
        result[key] = value
    return result


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"),
                      object_pairs_hook=no_duplicates)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


EXPECTED_INPUT_HASHES = {
    "inputs/censuses/ton_iot_20260903T233742Z.json":
        "128fe883208eef10cd2f41bf8c5ee73bf518cb61b5d95c86cff40214565edfa0",
    "inputs/inventories/ciciot2023_20260903T142539Z.json":
        "d31472b21836eb5a5cfa9535e1f29d58c0a4a1f136586938172a3e77bbe2f45f",
    "inputs/inventories/n_baiot_20260903T224404Z.json":
        "9ffdf7e9245470fc4f066b8fb6d8ebae03e0194e7698e5fde87b13a7f2fe30da",
    "inputs/inventories/ton_iot_20260903T113048Z.json":
        "66179d1ba2601ff3175e90cbfb4ed21d28c859b5780258d5e36dd8bb2303c55a",
    "inputs/protocol/feature_policy.json":
        "e81a55c16f9439b0356295353e8b342de19d5c5606d868952592f913beda714b",
    "inputs/protocol/label_ontology.json":
        "8a055e2e34bc8d70f62909f52441915589c310659d6ce3e427a2704820926fab",
    "inputs/quality_exceptions/ciciot2023_20260903T142617Z.json":
        "36ef134ff6117867c51888749434f2d02efc59ec4ad6e93e94371f08d59e5bae",
    "inputs/request/materialization_execution_request_v1.json":
        "fbfc84dbf700dc4fd8f98ad9e33887fb75eb67cf6a49d9524fa69acbbe38dfcb",
    "inputs/reviews/materialization_request_v1_independent_review.md":
        "5b0e12ce7d61ff485caf447f658542f187ea40bd7749a5d013ec88037f2ff823",
    "inputs/reviews/review_decision.json":
        "112dc2436cb314fa0a434f2886eb188bf7a086ca3238c1adb4e4b72ea76c55a5",
    "inputs/reviews/materialization_executor_v1_independent_review.md":
        "f58d30f8e075bdbf2634661fd23aa8331ff4cf29aea9fbaba821eb2f1a8271bf",
    "inputs/reviews/materialization_executor_v1_review_decision.json":
        "f297365b77a4cc63ad20c7ea17e06860413891d1c303dde065ab9186d255ed4f",
    "inputs/reviews/materialization_executor_v1_boundary_probe_results.json":
        "4b6c60ad1bc0ae191a23034a207b41a0078e59ae58834d483e4cf433d7ed35f8",
}


EXPECTED_FIXTURE_HASHES = {
    "tests/fixtures/expected/cic_attack7_features.csv": "a800aa56b22a2a3f1271534ad2dbb1c151c3b92bc5fb05ef4a6597978928288a",
    "tests/fixtures/expected/cic_attack7_labels.csv": "67137481e074ac6e2c6363005420c50c190f34238e5e4aa953bf271325ced513",
    "tests/fixtures/expected/cic_attack8_features.csv": "4fc66f783e5189c4ef5897f3057e75c363b20195cf8e61ba3c41874aba1a402b",
    "tests/fixtures/expected/cic_attack8_labels.csv": "67137481e074ac6e2c6363005420c50c190f34238e5e4aa953bf271325ced513",
    "tests/fixtures/expected/cic_attack9_features.csv": "19610f7fb6343434218f5bcbdad31fc1bd88e2bcb9f16ee4b4de58d9602eafd0",
    "tests/fixtures/expected/cic_attack9_labels.csv": "67137481e074ac6e2c6363005420c50c190f34238e5e4aa953bf271325ced513",
    "tests/fixtures/expected/cic_benign_features.csv": "4ba0599c16897f072326948f15a257b8110505e72f81dbe630a2f3a204c8563f",
    "tests/fixtures/expected/cic_benign_labels.csv": "7b7c335b0359da26429d0e109abfe95076fe8796740660cf4c1577952aa2fc3a",
    "tests/fixtures/expected/nb_attack_features.csv": "b082ee2ee52aa30d711ec4477def54f6d1f8287123ed61b812a686d1a3828858",
    "tests/fixtures/expected/nb_attack_labels.csv": "0040bf3118efca6b6cc23c08883710ff5b1f0ab8c6dc399076c6a5cf13ef31f0",
    "tests/fixtures/expected/nb_benign_features.csv": "578101e1759d4119502a00a762f6860e459a37ca77ffa4e2c99908bebcd2061a",
    "tests/fixtures/expected/nb_benign_labels.csv": "0dcefaedea9007e3254f077fc7ba9d2d4d3f1fa54bfc341caefb860d5fd461b9",
    "tests/fixtures/expected/ton_features.csv": "e4298ce1d010f37227f11fe576c9277e3673985ddaf4ece9af446fb20592c3e5",
    "tests/fixtures/expected/ton_labels.csv": "028a5b63de6322d79fd33c2ef493d0bdc6967a905530fe6a0eae7862e3e43427",
    "tests/fixtures/source/ciciot2023/CSV/Benign_Final/Benign_Final1.pcap.csv": "4ba0599c16897f072326948f15a257b8110505e72f81dbe630a2f3a204c8563f",
    "tests/fixtures/source/ciciot2023/CSV/DoS-UDP_Flood/DoS-UDP_Flood7.pcap.csv": "9c9353cb814213e6b873c53f8097db9f9a1a1378992a052ce4ba9e0c234267c2",
    "tests/fixtures/source/ciciot2023/CSV/DoS-UDP_Flood/DoS-UDP_Flood8.pcap.csv": "a891d194679f8548b8909447a757dbcdc9f7ced449aabfc6d1e521dbfb6f6b25",
    "tests/fixtures/source/ciciot2023/CSV/DoS-UDP_Flood/DoS-UDP_Flood9.pcap.csv": "6da3f0ef4b8da74594f9e103cacbd3bb846535b63248b3145ecfa76f711bbb48",
    "tests/fixtures/source/n_baiot/CamA/benign_traffic.csv": "578101e1759d4119502a00a762f6860e459a37ca77ffa4e2c99908bebcd2061a",
    "tests/fixtures/source/n_baiot/CamA/mirai_attacks_extracted/ack.csv": "b082ee2ee52aa30d711ec4477def54f6d1f8287123ed61b812a686d1a3828858",
    "tests/fixtures/source/n_baiot/demonstrate_structure.csv": "337d624a545de1d388be6bedaa89fdaf161c1e804b7d4cf21dba6e27f3384cee",
    "tests/fixtures/source/ton_iot/train_test_network.csv": "32191373d2cdc80893e77351c2ca83071389adb86c0abda9ead5b51400586cd7",
}


class Checks:
    def __init__(self) -> None:
        self.results: List[Tuple[bool, str]] = []

    def check(self, condition: bool, detail: str) -> None:
        self.results.append((bool(condition), detail))

    def equal(self, actual: Any, expected: Any, detail: str) -> None:
        self.check(actual == expected,
                   "%s: observed=%r expected=%r" % (detail, actual, expected))

    def report(self) -> int:
        for passed, detail in self.results:
            print("[%s] %s" % ("PASS" if passed else "FAIL", detail))
        passed = sum(1 for ok, _ in self.results if ok)
        total = len(self.results)
        print("SUMMARY %d/%d checks passed" % (passed, total))
        print("authorization_granted = false")
        print("real_csvs_opened      = false")
        print("real_output_created   = false")
        return 0 if passed == total else 1


def verify(root: Path) -> int:
    root = root.resolve()
    checks = Checks()
    for relative, expected in {**EXPECTED_INPUT_HASHES,
                               **EXPECTED_FIXTURE_HASHES}.items():
        path = root / relative
        checks.check(path.is_file(), "required evidence exists: %s" % relative)
        if path.is_file():
            checks.equal(sha256(path), expected, "SHA-256: %s" % relative)

    json_docs: Dict[str, Any] = {}
    for path in sorted(root.rglob("*.json")):
        relative = path.relative_to(root).as_posix()
        try:
            json_docs[relative] = load_json(path)
            checks.check(True, "JSON parses with duplicate-key rejection: %s" % relative)
        except Exception as exc:
            checks.check(False, "JSON parse failed %s: %s" % (relative, exc))

    contract = json_docs["contract/materialization_contract_v1r2.json"]
    request = json_docs["inputs/request/materialization_execution_request_v1.json"]
    policy = json_docs["inputs/protocol/feature_policy.json"]
    ontology = json_docs["inputs/protocol/label_ontology.json"]
    decision = json_docs["inputs/reviews/review_decision.json"]
    revision_decision = json_docs[
        "inputs/reviews/materialization_executor_v1_review_decision.json"]
    inventories = {
        dataset_id: json_docs["inputs/inventories/%s" % filename]
        for dataset_id, filename in {
            "ton_iot": "ton_iot_20260903T113048Z.json",
            "ciciot2023": "ciciot2023_20260903T142539Z.json",
            "n_baiot": "n_baiot_20260903T224404Z.json",
        }.items()
    }
    quality_exceptions = json_docs[
        "inputs/quality_exceptions/ciciot2023_20260903T142617Z.json"]

    checks.equal(contract["kind"], "materialization_executor_contract",
                 "contract kind")
    checks.equal(contract["status"], "implementation_complete_not_authorized",
                 "contract status")
    checks.equal(contract["operation"], "materialization", "single operation")
    checks.equal(contract["contract_id"],
                 "MATERIALIZATION-EXECUTOR-20260906-V1R2-PROPOSED",
                 "V1R2 contract identity")
    checks.equal(contract["authorization"]["granted"], False,
                 "contract does not authorize execution")
    checks.equal(decision["materialization_authorized"], False,
                 "review does not authorize materialization")
    checks.equal(decision["splitting_authorized"], False,
                 "review does not authorize splitting")
    checks.equal(decision["training_authorized"], False,
                 "review does not authorize training")
    checks.equal(revision_decision["verdict"],
                 "REVISION_REQUIRED_BEFORE_EXECUTOR_ACCEPTANCE",
                 "V1 independent-review verdict retained")
    checks.equal(revision_decision["blocking_execution_boundaries"], [
        "E01_runtime_contract_code_evidence_binding",
        "E02_replay_storage_accounting",
        "E03_all_input_validation_and_exact_no_LF_exceptions",
        "E04_no_clobber_publish_and_staging_ownership"],
        "exact E01-E04 revision scope")
    checks.equal((revision_decision["materialization_authorized"],
                  revision_decision["splitting_authorized"],
                  revision_decision["training_authorized"]),
                 (False, False, False), "revision review grants no data operation")
    checks.equal(policy["status"], "frozen", "feature policy stays frozen")
    checks.equal(ontology["status"], "frozen", "label ontology stays frozen")

    baseline = contract["baseline_request"]
    checks.equal(baseline["request_id"], request["request_id"],
                 "baseline request_id binding")
    checks.equal(baseline["request_zip_sha256"],
                 "55c3c6ee9d6e01fb764a650432b379ca41ca52b703dd33c9ec9cf17088271c63",
                 "accepted request ZIP binding")
    checks.equal(baseline["request_json_sha256"], EXPECTED_INPUT_HASHES[
        "inputs/request/materialization_execution_request_v1.json"],
        "accepted request JSON binding")
    review = contract["independent_review"]
    checks.equal(review["review_zip_sha256"],
                 "f62cfc6173039df4383d0697756e6fa630e51dab69967c8c75eafa0fe1bf2838",
                 "independent review ZIP binding")
    checks.equal(review["review_text_sha256"], EXPECTED_INPUT_HASHES[
        "inputs/reviews/materialization_request_v1_independent_review.md"],
        "independent review text binding")
    revision = contract["revision_review"]
    checks.equal((revision["review_zip_bytes"], revision["review_zip_sha256"]),
                 (36784,
                  "c43965bc93d3fee587c03fb0ae94690f6a4562946ed363e8519a178ebbcad361"),
                 "executor V1 independent-review ZIP binding")
    checks.equal(revision["review_text_sha256"], EXPECTED_INPUT_HASHES[
        "inputs/reviews/materialization_executor_v1_independent_review.md"],
        "executor revision review text binding")
    checks.equal(revision["review_decision_sha256"], EXPECTED_INPUT_HASHES[
        "inputs/reviews/materialization_executor_v1_review_decision.json"],
        "executor revision decision binding")
    checks.equal(revision["boundary_results_sha256"], EXPECTED_INPUT_HASHES[
        "inputs/reviews/materialization_executor_v1_boundary_probe_results.json"],
        "executor boundary results binding")

    for dataset_id, binding in contract["input_binding"]["inventories"].items():
        request_binding = request["frozen_inputs"]["datasets"][dataset_id]
        checks.equal(binding["sha256"], request_binding["inventory_sha256"],
                     "%s contract/request inventory hash" % dataset_id)
        checks.equal(sha256(root / binding["file"]), binding["sha256"],
                     "%s contract/actual inventory hash" % dataset_id)
    checks.equal(contract["input_binding"]["feature_policy"]["sha256"],
                 request["accepted_freeze_binding"]["feature_policy"]["sha256"],
                 "feature-policy contract/request binding")
    checks.equal(contract["input_binding"]["label_ontology"]["sha256"],
                 request["accepted_freeze_binding"]["label_ontology"]["sha256"],
                 "ontology contract/request binding")

    output = contract["output_binding"]
    checks.check(Path(output["root"]).is_absolute(), "output root absolute")
    checks.check(Path(output["staging_root"]).is_absolute(), "staging root absolute")
    checks.check(output["root"] != output["staging_root"],
                 "output and staging roots are distinct")
    checks.equal(Path(output["root"]).parent, Path(output["staging_root"]).parent,
                 "output and staging roots share parent")
    checks.equal(Path(output["staging_root"]).name,
                 ".%s.staging" % Path(output["root"]).name,
                 "staging safe sibling name")
    checks.equal(output["root"], request["output"]["root"],
                 "V1R2 retains baseline output root pending new-volume rebind")
    checks.equal(output["staging_root"], request["output"]["staging_root"],
                 "V1R2 retains baseline staging root pending rebind")
    checks.check("rebind" in output["binding_status"],
                 "new-volume path is explicitly pending rebind")
    checks.check("renameatx_np" in output["publish"] and
                 "RENAME_EXCL" in output["publish"],
                 "publication uses explicit atomic no-clobber primitive")
    checks.check("no unsafe fallback" in output["publish"],
                 "no-clobber publication has no replacement fallback")
    checks.check("fail closed" in output["publish_unsupported"],
                 "unsupported target filesystem fails closed")

    runtime = contract["runtime_evidence_binding"]
    checks.equal(runtime["archive_root"],
                 "materialization_executor_evidence_v1r2",
                 "approved evidence archive root")
    checks.equal(runtime["contract_local_path"],
                 "contract/materialization_contract_v1r2.json",
                 "runtime contract member binding")
    checks.equal(runtime["executor_local_path"],
                 "scripts/materialize_dataset_native_v1r2.py",
                 "runtime executor member binding")
    expected_runtime_files = {
        runtime["contract_local_path"], runtime["executor_local_path"],
        contract["input_binding"]["feature_policy"]["file"],
        contract["input_binding"]["label_ontology"]["file"],
        contract["input_binding"]["ton_label_census"]["file"],
        contract["input_binding"]["cic_quality_exceptions"]["file"],
        contract["baseline_request"]["request_json"],
        *(item["file"] for item in
          contract["input_binding"]["inventories"].values()),
    }
    checks.equal(set(runtime["required_local_files"]), expected_runtime_files,
                 "complete runtime local-file binding")
    checks.equal(runtime["local_dependencies"],
                 "none; executor imports only the Python standard library",
                 "no unbound local runtime dependency")
    checks.check("byte-identical" in runtime["source_access_gate"],
                 "contract/code/input binding precedes source access")

    required_auth = set(contract["authorization"]["required_bindings"])
    checks.check({"evidence_archive_root", "evidence_manifest_sha256",
                  "contract_sha256", "executor_sha256"}.issubset(required_auth),
                 "authorization records explicit runtime evidence hashes")

    source_csv = contract["source_csv_reading"]
    checks.equal(source_csv["record_boundary"],
                 "one physical line is one CSV record; normal records are LF-terminated",
                 "source CSV record boundary is explicit")
    checks.check(source_csv["quoted_multiline_fields"].startswith("forbidden"),
                 "quoted multiline source records fail closed")
    checks.equal(source_csv["header_terminal_newline"],
                 "required without exception",
                 "source header LF requirement is explicit")
    checks.check(source_csv["only_terminal_newline_exception"].startswith(
        "exactly the three frozen CIC malformed final physical lines"),
        "only three fully bound CIC final rows may omit LF")
    checks.check(source_csv["unregistered_missing_newline"].startswith("fail"),
                 "unregistered missing LF fails before staging")
    failure = contract["failure_safety"]
    checks.check("forbidden" in failure["automatic_failure_deletion"],
                 "automatic pathname deletion is forbidden")
    checks.check("preserve owned staging" in failure["failure_retention"],
                 "owned failed staging is retained and reported")
    checks.check("do not delete or modify" in failure["foreign_staging"],
                 "foreign replacement is preserved")

    operations = contract["authorization"]["required_operations"]
    checks.equal(operations, {"materialization": True, "splitting": False,
                              "training": False, "encoder_fitting": False,
                              "model_fitting": False},
                 "authorization schema is materialization-only")
    label = contract["label_sidecar"]
    checks.equal(label["columns"], ["binary_label", "canonical_family",
                                    "source_family", "source_subtype"],
                 "complete label sidecar header")
    checks.equal(label["binary_label_values"], ["benign", "attack"],
                 "frozen binary label strings")
    checks.equal(label["ton_iot"]["binary_label_map"],
                 {"0": "benign", "1": "attack"},
                 "TON binary rule direct assertion")
    checks.equal(label["ton_iot"]["source_family"], "",
                 "TON source_family empty CSV cell")
    checks.equal(label["ciciot2023"]["source_family"], "",
                 "CIC source_family empty CSV cell")

    metadata = contract["metadata_representation"]
    checks.equal(metadata["ton_iot"], {"device_id": None, "capture_id": None},
                 "TON unavailable JSON metadata is null")
    checks.equal(metadata["ciciot2023"]["device_id"], None,
                 "CIC unavailable device_id is null")
    capture = metadata["n_baiot"]["capture_id"]
    checks.equal(capture["json_type"], "array", "N-BaIoT capture JSON type")
    checks.equal(capture["length"], 3, "N-BaIoT capture array length")
    checks.equal(capture["element_order"],
                 ["device_id", "source_family", "source_subtype"],
                 "N-BaIoT capture array order")

    ordering = contract["ordering"]
    checks.equal(ordering["shard_ordinal_scope"],
                 "restart independently for each dataset", "per-dataset ordinals")
    checks.equal(ordering["shard_ordinal_start"], 1, "one-based ordinals")
    checks.equal(ordering["shard_ordinal_format"],
                 "four decimal digits, zero padded", "ordinal formatting")
    checks.check("after complete 400-file preflight" in ordering["data_file_filter"],
                 "zero-row file excluded only after complete preflight")
    checks.check("all 400 inventoried CSV files" in ordering["input_preflight"],
                 "all inventoried files receive identity preflight")
    checks.equal(ordering["file_sort"],
                 "ascending lexicographic order of relative_path encoded as UTF-8 bytes",
                 "UTF-8 bytewise source ordering")

    csv_contract = contract["csv_serialization"]
    checks.equal((csv_contract["encoding"], csv_contract["bom"],
                  csv_contract["newline"], csv_contract["quoting"],
                  csv_contract["terminal_newline"]),
                 ("UTF-8", False, "LF", "minimal", True),
                 "canonical CSV serialization")
    checks.equal(csv_contract["empty_not_applicable_cell"],
                 "zero bytes between delimiters", "empty CSV representation")
    json_contract = contract["json_serialization"]
    checks.equal((json_contract["encoding"], json_contract["bom"],
                  json_contract["ensure_ascii"], json_contract["separators"],
                  json_contract["terminal_newline"]),
                 ("UTF-8", False, False, [",", ":"], True),
                 "canonical JSON/JSONL serialization")

    checks.equal(contract["quality_exception_schema"]["fields_in_order"], [
        "physical_line", "source_row", "raw_line_bytes", "raw_line_sha256",
        "observed_column_count", "expected_column_count"],
        "excluded-row schema exact fields")
    checks.equal(contract["quality_exception_schema"]["source_row_rule"],
                 "physical_line - 1 because the header is physical line 1",
                 "excluded source-row rule")
    checks.equal(contract["shard_ledger"]["fields_in_order"], [
        "schema_version", "dataset_id", "shard_ordinal", "shard_id",
        "source_file", "source_file_sha256", "source_file_bytes",
        "source_header_sha256", "source_rows_inventoried",
        "source_rows_excluded", "source_rows_accepted", "excluded_rows",
        "device_id", "capture_id", "features_file", "features_sha256",
        "features_bytes", "labels_file", "labels_sha256", "labels_bytes"],
        "ledger schema exact fields")
    checks.equal(contract["dataset_manifest"]["fields_in_order"], [
        "schema_version", "contract_id", "dataset_id", "shard_count",
        "source_files_inventoried", "source_rows_inventoried",
        "source_rows_excluded", "rows_materialized", "feature_count",
        "feature_columns", "label_columns", "features_total_bytes",
        "labels_total_bytes", "ledger_file", "ledger_sha256", "ledger_bytes"],
        "dataset manifest exact fields")
    root_manifest = contract["root_manifest"]
    checks.equal(root_manifest["self_entry"], False, "root manifest self-exclusion")
    checks.check("every regular file" in root_manifest["coverage"],
                 "root manifest exact coverage rule")
    checks.equal(root_manifest["dependency_order"], [
        "feature and label files", "shard ledger", "dataset manifest",
        "run_identity.json", "root MANIFEST"], "acyclic hash dependency order")

    features = contract["feature_contract"]
    checks.equal((features["ton_iot"]["source_columns"],
                  features["ton_iot"]["output_columns"]), (44, 32),
                 "TON source/output feature counts")
    expected_ton_excluded = set(policy["ton_iot_exclusions"]["permanent"]["columns"] +
                                policy["ton_iot_exclusions"]["port_columns"]["columns"])
    checks.equal(set(features["ton_iot"]["excluded"]), expected_ton_excluded,
                 "TON exact frozen exclusions plus dropped ports")
    checks.equal((features["ciciot2023"]["source_columns"],
                  features["ciciot2023"]["output_columns"],
                  features["n_baiot"]["source_columns"],
                  features["n_baiot"]["output_columns"]),
                 (39, 39, 115, 115), "CIC/N native feature counts")

    expected_output = contract["expected_real_output"]
    checks.equal((expected_output["inventoried_csv_files"],
                  expected_output["feature_shards"],
                  expected_output["label_shards"],
                  expected_output["source_rows"],
                  expected_output["excluded_rows"],
                  expected_output["materialized_rows"]),
                 (400, 399, 399, 54050349, 3, 54050346),
                 "real expected aggregate counts")
    checks.equal(expected_output["per_dataset"]["ton_iot"]["benign"], 50000,
                 "TON benign count")
    checks.equal(expected_output["per_dataset"]["ciciot2023"]["attack"], 45678506,
                 "CIC accepted attack count")
    checks.equal(expected_output["per_dataset"]["n_baiot"]["attack"], 6506674,
                 "N-BaIoT attack count")

    total_files = sum(item["file_count"] for item in inventories.values())
    total_rows = sum(item["total_rows"] for item in inventories.values())
    total_bytes = sum(item["total_bytes"] for item in inventories.values())
    checks.equal((total_files, total_rows, total_bytes),
                 (400, 54050349, 17114499704), "inventories independently reconcile")
    checks.equal(quality_exceptions["exception_count"], 3,
                 "exact frozen exception count")
    checks.equal([item["ends_with_newline"]
                  for item in quality_exceptions["exceptions"]],
                 [False, False, False], "all frozen exceptions are non-LF final rows")
    checks.equal(contract["storage"]["hard_output_cap_bytes"],
                 (3 * total_bytes + 1) // 2, "hard output cap arithmetic")
    checks.equal(contract["storage"]["minimum_free_bytes"],
                 contract["storage"]["hard_output_cap_bytes"] +
                 contract["storage"]["scratch_reserve_bytes"],
                 "minimum free-space arithmetic")
    checks.equal(contract["storage"]["current_location_observation_passes"], False,
                 "known internal location remains blocked")

    csv_paths = [path.relative_to(root).as_posix() for path in root.rglob("*.csv")]
    checks.check(all(path.startswith("tests/fixtures/source/") or
                     path.startswith("tests/fixtures/expected/")
                     for path in csv_paths), "all bundled CSVs are declared synthetic fixtures")
    checks.equal(len(csv_paths), len(EXPECTED_FIXTURE_HASHES),
                 "exact synthetic CSV fixture count")
    checks.check(not any(path.name == "authorization.json" or
                         "authorization_record" in path.name
                         for path in root.rglob("*")),
                 "no execution authorization record bundled")

    materializer_path = root / "scripts/materialize_dataset_native_v1r2.py"
    materializer_source = materializer_path.read_text(encoding="utf-8")
    checks.check("tempfile.TemporaryDirectory" not in materializer_source and
                 'def replay_shard(' in materializer_source and
                 "DigestBinarySink(None)" in materializer_source,
                 "replay is hash-only and creates no replay directory")
    checks.check("shutil.rmtree" not in materializer_source and
                 "os.replace" not in materializer_source,
                 "executor has no pathname recursive cleanup or replacing publish")
    checks.check("renameatx_np" in materializer_source and "0x00000004" in
                 materializer_source, "Darwin atomic no-clobber implementation present")
    checks.check("validate_runtime_archive" in materializer_source and
                 "validate_runtime_files_unchanged" in materializer_source,
                 "runtime evidence ZIP binding implementation present")
    try:
        spec = importlib.util.spec_from_file_location("evidence_materializer", materializer_path)
        if spec is None or spec.loader is None:
            raise RuntimeError("cannot create import spec")
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        module.validate_contract_shape(contract)
        checks.check(True, "executor accepts the exact contract shape")
    except Exception as exc:
        checks.check(False, "executor rejects exact contract shape: %s" % exc)

    return checks.report()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path,
                        default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    return verify(args.root)


if __name__ == "__main__":
    sys.exit(main())
