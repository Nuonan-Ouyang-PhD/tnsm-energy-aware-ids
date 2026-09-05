import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LABEL_ONTOLOGY_PATH = REPO_ROOT / "config" / "label_ontology.json"
INVENTORY_PATH = (
    REPO_ROOT / "artifacts" / "datasets" / "inventories" / "n_baiot_20260903T224404Z.json"
)
DECISIONS_PATH = REPO_ROOT / "docs" / "DECISIONS.md"
LABEL_ONTOLOGY_MD_PATH = REPO_ROOT / "docs" / "LABEL_ONTOLOGY.md"

# The 11 (source_family, source_subtype) pairs from frozen inventory
# n_baiot_20260903T224404Z.json (label_source: Directory and filename):
# 9 benign_traffic.csv files (one per device) + 45 gafgyt files + 35 mirai
# files, with subtype = CSV filename stem.
EXPECTED_PAIRS = [
    ("benign", "benign_traffic"),
    ("gafgyt_attacks_extracted", "combo"),
    ("gafgyt_attacks_extracted", "junk"),
    ("gafgyt_attacks_extracted", "scan"),
    ("gafgyt_attacks_extracted", "tcp"),
    ("gafgyt_attacks_extracted", "udp"),
    ("mirai_attacks_extracted", "ack"),
    ("mirai_attacks_extracted", "scan"),
    ("mirai_attacks_extracted", "syn"),
    ("mirai_attacks_extracted", "udp"),
    ("mirai_attacks_extracted", "udpplain"),
]

# Complete expected mapping table: (source_family, source_subtype) ->
# (canonical_family, semantic_disposition). Locks the entire proposal so a
# wrong assignment (e.g. mirai/udp -> ddos, or gafgyt/scan -> recon) fails
# even though both names are individually valid families.
EXPECTED_MAPPING = {
    ("benign", "benign_traffic"):     ("benign",   "exact"),
    ("gafgyt_attacks_extracted", "combo"):    ("bashlite", "exact"),
    ("gafgyt_attacks_extracted", "junk"):     ("bashlite", "exact"),
    ("gafgyt_attacks_extracted", "scan"):     ("bashlite", "exact"),
    ("gafgyt_attacks_extracted", "tcp"):      ("bashlite", "exact"),
    ("gafgyt_attacks_extracted", "udp"):      ("bashlite", "exact"),
    ("mirai_attacks_extracted", "ack"):       ("mirai",    "exact"),
    ("mirai_attacks_extracted", "scan"):      ("mirai",    "exact"),
    ("mirai_attacks_extracted", "syn"):       ("mirai",    "exact"),
    ("mirai_attacks_extracted", "udp"):       ("mirai",    "exact"),
    ("mirai_attacks_extracted", "udpplain"):  ("mirai",    "exact"),
}

MEIDAN_SHA = "1fa5bc4d4d2a12c2e93b18c4d876bd83ab7f456797934fcc71c92db754811964"
V1R1_ZIP_SHA = "480e15c672d5673f0d4eb82cf9f4da34cf53be9e516737f9981354459b632501"
UCI_SHA = "e0b79978d166b601ce1e8480625d8ad9fe40b328ad92d66f8eebde9730b5d57f"
INVENTORY_NAME = "n_baiot_20260903T224404Z.json"

VALID_DISPOSITIONS = ["exact", "derived", "unresolved", "rejected"]
VALID_DECISION_STATUSES = ["proposed", "frozen"]


def load_label_ontology():
    with LABEL_ONTOLOGY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def load_inventory():
    with INVENTORY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


class NBaiotTypeMappingTests(unittest.TestCase):
    """Tests for the N-BaIoT (source_family, source_subtype) ->
    canonical_family mapping FROZEN as N-BAIOT-TYPE-MAPPING-20260905-V1-FROZEN."""

    def setUp(self):
        self.ontology = load_label_ontology()
        self.mapping = self.ontology["canonical_family"]["n_baiot_type_mapping"]
        self.entries = {
            (e["source_family"], e["source_subtype"]): e
            for e in self.mapping["entries"]
        }

    def test_full_expected_mapping_table(self):
        """Every (family, subtype) pair must map to exactly the expected
        canonical family and disposition; all 11 entries now carry
        decision_status == frozen (N-BAIOT-TYPE-MAPPING-20260905-V1-FROZEN)."""
        self.assertEqual(
            set(self.entries.keys()), set(EXPECTED_MAPPING.keys()),
            "entry set differs from the expected 11-pair table",
        )
        for pair, (family, disposition) in EXPECTED_MAPPING.items():
            entry = self.entries[pair]
            self.assertEqual(
                entry["canonical_family"], family,
                f"{pair}: family is {entry['canonical_family']}, expected {family}",
            )
            self.assertEqual(
                entry["semantic_disposition"], disposition,
                f"{pair}: disposition is {entry['semantic_disposition']}, expected {disposition}",
            )
            self.assertEqual(
                entry["decision_status"], "frozen",
                f"{pair}: decision_status is not frozen",
            )

    def test_all_11_pairs_present(self):
        self.assertEqual(len(EXPECTED_PAIRS), 11)
        for pair in EXPECTED_PAIRS:
            self.assertIn(pair, self.entries, f"missing pair {pair}")

    def test_exactly_zero_derived_entries(self):
        for pair, entry in self.entries.items():
            self.assertEqual(
                entry["semantic_disposition"], "exact",
                f"{pair}: only exact mappings are expected in v1",
            )

    # ----- alignment with the frozen fixed_decision -----------------------

    def test_gafgyt_entries_align_with_frozen_fixed_decision(self):
        """All 5 gafgyt subtypes map to bashlite, aligning with the frozen
        gafgyt->bashlite fixed_decision (family-level, decision_status =
        frozen)."""
        fixed = [
            fd for fd in self.ontology["canonical_family"]["fixed_decisions"]
            if fd.get("source_family") == "gafgyt"
        ]
        self.assertEqual(len(fixed), 1)
        self.assertEqual(fixed[0]["canonical_family"], "bashlite")
        self.assertEqual(fixed[0]["decision_status"], "frozen")
        for sub in ("combo", "junk", "scan", "tcp", "udp"):
            entry = self.entries[("gafgyt_attacks_extracted", sub)]
            self.assertEqual(entry["canonical_family"], "bashlite")
            self.assertIn("frozen fixed_decision", entry["rationale"])

    def test_gafgyt_subtypes_not_relabelled_across_axes(self):
        """Gafgyt tcp/udp are NOT re-labelled ddos; gafgyt scan is NOT
        merged into recon (malware family and behavior type are different
        ontological axes)."""
        self.assertEqual(
            self.entries[("gafgyt_attacks_extracted", "tcp")]["canonical_family"],
            "bashlite",
        )
        self.assertEqual(
            self.entries[("gafgyt_attacks_extracted", "udp")]["canonical_family"],
            "bashlite",
        )
        self.assertEqual(
            self.entries[("gafgyt_attacks_extracted", "scan")]["canonical_family"],
            "bashlite",
        )
        for sub in ("tcp", "udp", "scan"):
            self.assertNotEqual(
                self.entries[("gafgyt_attacks_extracted", sub)]["canonical_family"],
                "ddos",
            )
            self.assertNotEqual(
                self.entries[("gafgyt_attacks_extracted", sub)]["canonical_family"],
                "recon",
            )

    def test_same_subtype_names_in_different_families_are_separate(self):
        """scan and udp appear in BOTH gafgyt and mirai families; they are
        behavior labels of different malware families and must remain
        separate entries mapping to separate canonical families."""
        g_scan = self.entries[("gafgyt_attacks_extracted", "scan")]
        m_scan = self.entries[("mirai_attacks_extracted", "scan")]
        self.assertEqual(g_scan["canonical_family"], "bashlite")
        self.assertEqual(m_scan["canonical_family"], "mirai")
        g_udp = self.entries[("gafgyt_attacks_extracted", "udp")]
        m_udp = self.entries[("mirai_attacks_extracted", "udp")]
        self.assertEqual(g_udp["canonical_family"], "bashlite")
        self.assertEqual(m_udp["canonical_family"], "mirai")

    # ----- evidence discipline ---------------------------------------------

    def test_every_entry_has_required_fields(self):
        required = [
            "source_family", "source_subtype", "canonical_family",
            "semantic_disposition", "decision_status", "evidence_source",
            "rationale",
        ]
        for pair, entry in self.entries.items():
            for key in required:
                self.assertIn(key, entry, f"{pair}: missing key {key}")
            self.assertIn(entry["semantic_disposition"], VALID_DISPOSITIONS)
            self.assertIn(entry["decision_status"], VALID_DECISION_STATUSES)

    def test_evidence_and_rationale_nonempty(self):
        for pair, entry in self.entries.items():
            self.assertGreater(len(entry["evidence_source"].strip()), 0, pair)
            self.assertGreater(len(entry["rationale"].strip()), 0, pair)

    def test_attack_evidence_cites_meidan_and_inventory(self):
        for pair, entry in self.entries.items():
            if pair[0] == "benign":
                continue
            self.assertIn("Meidan et al. 2018 PDF p.", entry["evidence_source"])
            self.assertIn(INVENTORY_NAME, entry["evidence_source"])
            self.assertIn("files,", entry["evidence_source"])
            self.assertIn("rows", entry["evidence_source"])

    def test_benign_evidence_cites_uci_and_inventory(self):
        entry = self.entries[("benign", "benign_traffic")]
        self.assertIn(UCI_SHA, entry["evidence_source"])
        self.assertIn(INVENTORY_NAME, entry["evidence_source"])
        self.assertIn("555,932", entry["evidence_source"])

    def test_evidence_row_counts_match_frozen_inventory(self):
        """The file/row counts cited in each evidence_source must match the
        frozen inventory aggregation exactly."""
        agg = {}
        for f in load_inventory()["files"]:
            parts = f["relative_path"].split("/")
            if len(parts) == 2:
                key = ("benign", parts[1].replace(".csv", ""))
            elif len(parts) == 3:
                key = (parts[1], parts[2].replace(".csv", ""))
            else:
                continue  # demonstrate_structure.csv (root-level, no label)
            files, rows = agg.get(key, (0, 0))
            agg[key] = (files + 1, rows + f["row_count"])
        for pair, entry in self.entries.items():
            files, rows = agg[pair]
            if pair[0] == "benign":
                expected = f"{files} files (one benign_traffic.csv per device), {rows:,} rows"
            else:
                expected = f"{files} files, {rows:,} rows"
            self.assertIn(expected, entry["evidence_source"], pair)

    def test_evidence_row_counts_total_7062606(self):
        total = 0
        for pair, entry in self.entries.items():
            import re
            m = re.search(r"(\d[\d,]*) rows", entry["evidence_source"])
            assert m, f"{pair}: rows pattern missing"
            total += int(m.group(1).replace(",", ""))
        self.assertEqual(total, 7_062_606)

    # ----- cross-dataset discipline ----------------------------------------

    def test_mirai_entries_cross_dataset_claims_are_conditional(self):
        """Mirai entries cite the CICIoT2023 frozen Mirai category as
        presence-only; the comparison claim must be conditional on the
        N-BaIoT mapping freeze and a subtype-coverage audit."""
        for sub in ("ack", "scan", "syn", "udp", "udpplain"):
            rationale = self.entries[("mirai_attacks_extracted", sub)]["rationale"]
            self.assertIn("conditional", rationale)
            self.assertIn("subtype-coverage", rationale)
            self.assertIn("presence-only", rationale)

    def test_cross_dataset_claims_do_not_equal_across_families(self):
        """N-BaIoT bashlite/mirai entries must not equate the families with
        TON-IoT or CICIoT2023 families (no unconditioned cross-dataset
        equivalence)."""
        for pair, entry in self.entries.items():
            if pair[0] == "benign":
                continue
            rationale = entry["rationale"]
            if "CICIoT2023" in rationale:
                self.assertIn("conditional", rationale, pair)

    # ----- description and coverage invariant ------------------------------

    def test_description_declares_freeze_stage(self):
        """The mapping-level description must record the freeze metadata
        (V1R1 evidence ZIP hash, source commit, freeze id)."""
        desc = self.mapping["description"]
        self.assertIn("FROZEN as N-BAIOT-TYPE-MAPPING-20260905-V1-FROZEN", desc)
        self.assertIn("DECISIONS.md #20", desc)
        self.assertIn(V1R1_ZIP_SHA, desc)
        self.assertIn("source commit 33b076c", desc)
        self.assertIn("decision_status=frozen as N-BAIOT-TYPE-MAPPING-20260905-V1-FROZEN", desc)
        self.assertIn("N-BAIOT-TYPE-MAPPING-20260904-V1-PROPOSED", desc)  # provenance
        self.assertIn("Meidan et al. 2018", desc)
        self.assertIn(MEIDAN_SHA, desc)
        self.assertIn(INVENTORY_NAME, desc)
        self.assertIn("115 aggregated statistics columns", desc)
        # the frozen fixed_decision relationship must be declared
        self.assertIn("frozen as a fixed_decision", desc)
        self.assertIn("extends that frozen family decision", desc)
        self.assertIn("no mapping, semantic_disposition, evidence, or rationale", desc)

    def test_coverage_invariant_recorded(self):
        cov = self.mapping["coverage_invariant"]
        self.assertIn("benign_traffic.csv -> benign", cov["rule"])
        self.assertIn("89 data files", cov["rule"])
        self.assertIn("exactly one (source_family, source_subtype) entry", cov["rule"])
        self.assertIn("demonstrate_structure.csv", cov["rule"])
        self.assertIn("no label", cov["rule"])

    def test_coverage_invariant_evidence_cites_device_asymmetry(self):
        ev = self.mapping["coverage_invariant"]["evidence_source"]
        self.assertIn("89 data files", ev)
        self.assertIn("9 benign + 45 gafgyt + 35 mirai", ev)
        self.assertIn("7,062,606 rows", ev)
        self.assertIn("mirai files span 7 devices", ev)
        self.assertIn("Ennio_Doorbell", ev)
        self.assertIn("Samsung_SNH_1011_N_Webcam", ev)

    def test_inventory_all_rows_well_formed(self):
        inv = load_inventory()
        self.assertTrue(inv["all_rows_well_formed"])
        self.assertEqual(inv["file_count"], 90)
        self.assertEqual(inv["total_rows"], 7_062_606)
        self.assertEqual(inv["label_source"], "Directory and filename")

    # ----- registry evidence ------------------------------------------------

    def test_registry_carries_n_baiot_reference_entries(self):
        registry = json.loads(
            (REPO_ROOT / "references" / "dataset_docs" / "registry.json").read_text(encoding="utf-8")
        )
        n_baiot_entries = [
            e for e in registry["entries"]
            if e.get("dataset_id") == "n_baiot"
        ]
        self.assertEqual(len(n_baiot_entries), 2)
        for entry in n_baiot_entries:
            self.assertIn("sha256", entry)
            self.assertIn("file", entry)
        by_file = {e["file"]: e for e in n_baiot_entries}
        self.assertTrue(any("uci_dataset_page" in f for f in by_file), by_file)
        self.assertTrue(any("meidan2018" in f for f in by_file), by_file)
        self.assertEqual(
            by_file["n_baiot/meidan2018_arxiv_v1_2026-09-04.pdf"]["sha256"], MEIDAN_SHA
        )
        self.assertEqual(
            by_file["n_baiot/uci_dataset_page_2026-09-04.html"]["sha256"], UCI_SHA
        )

    # ----- documentation surfaces -------------------------------------------

    def test_label_ontology_md_declares_n_baiot_frozen(self):
        md = LABEL_ONTOLOGY_MD_PATH.read_text(encoding="utf-8")
        self.assertIn("N-BAIOT-TYPE-MAPPING-20260905-V1-FROZEN", md)
        self.assertIn("N-BaIoT family/subtype → canonical_family mapping table (FROZEN)", md)
        # the proposal id survives only as provenance in the stage paragraph
        self.assertIn(
            "proposed as `N-BAIOT-TYPE-MAPPING-20260904-V1-PROPOSED`", md
        )
        # 11 data rows in the MD table (1 header + 1 separator + 11 rows)
        self.assertIn("| `gafgyt_attacks_extracted` | `combo` | `bashlite` | exact |", md)
        self.assertIn("| `mirai_attacks_extracted` | `udpplain` | `mirai` | exact |", md)
        self.assertIn(V1R1_ZIP_SHA, md)
        self.assertIn("source commit `33b076c`", md)

    def test_decisions_md_records_decision_19(self):
        """#19 and its Rev 1 record stay untouched as history; the live
        freeze record is #20."""
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn("19. N-BaIoT family/subtype mapping proposed as", md)
        self.assertIn("N-BAIOT-TYPE-MAPPING-20260904-V1-PROPOSED", md)
        self.assertIn("11 exact / 0 derived", md)
        self.assertIn("Nothing is frozen in this record", md)
        self.assertIn("18. CICIoT2023 type mapping FROZEN as", md)

    def test_decisions_md_records_decision_20_freeze(self):
        md = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn("20. N-BaIoT family/subtype mapping FROZEN as", md)
        self.assertIn("N-BAIOT-TYPE-MAPPING-20260905-V1-FROZEN", md)
        self.assertIn(V1R1_ZIP_SHA, md)
        self.assertIn("2,531,489 bytes, 31 entries", md)
        self.assertIn("source commit `33b076c`", md)
        self.assertIn("On explicit user authorization", md)
        self.assertIn("11 exact /\n    0 derived", md)
        self.assertIn("Mirai coverage is recorded as 7/9 devices", md)
        self.assertIn("not an unconditional\n    paper-vs-data-tree contradiction", md)
        self.assertIn("no\n    mapping, semantic_disposition, evidence, or rationale was altered", md)
        self.assertIn("canonical_family.decision_status all remain `proposed`", md)
        self.assertIn("forbidden until the\n    root-level ontology freeze", md)

    def test_label_ontology_md_section5_has_no_stale_proposal_residue(self):
        """Freeze Rev 1 guard: the section-5 historical proposal-stage
        opener (written before any dataset-level table was frozen) must
        not contradict the frozen tables declared in the same section."""
        md = LABEL_ONTOLOGY_MD_PATH.read_text(encoding="utf-8")
        self.assertNotIn(
            "The family mapping table is NOT frozen yet.", md,
            "stale proposal-stage sentence still present in section 5",
        )
        self.assertIn(
            "All three dataset-level family mapping tables are now frozen.", md
        )
        self.assertIn(
            "The\nroot-level freeze "
            "`LABEL-ONTOLOGY-ROOT-20260905-V1-FROZEN` (DECISIONS.md\n"
            "#22) is applied", md
        )
        # the condition history list and closing ban survive
        self.assertIn("All three freeze conditions are satisfied.", md)
        self.assertIn("Data materialization, splitting, and training remain forbidden.", md)

    # ----- published-surface hygiene ---------------------------------------

    def test_no_aigc_watermarks_in_published_docs(self):
        """The published docs and config must not carry AIGC watermark
        blocks or trailing generated-content markers (workspace-injection
        artifacts are not evidence content)."""
        for rel in ("docs/DECISIONS.md", "docs/LABEL_ONTOLOGY.md"):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("AIGC:", text, f"{rel}: AIGC watermark block present")
            self.assertNotIn("AI生成", text, f"{rel}: generated-content marker present")
        for rel in ("config/label_ontology.json", "references/dataset_docs/registry.json"):
            text = (REPO_ROOT / rel).read_text(encoding="utf-8")
            self.assertNotIn("AI生成", text, f"{rel}: generated-content marker present")
            self.assertNotIn("AIGC:", text, f"{rel}: AIGC watermark present")


class OntologyWideNBaiotDisciplineTests(unittest.TestCase):
    """Ontology-wide guards extended to the N-BaIoT stage."""

    def setUp(self):
        self.ontology = load_label_ontology()

    def test_no_mapping_status_key_anywhere(self):
        def walk(node, path=""):
            if isinstance(node, dict):
                for key, value in node.items():
                    location = f"{path}.{key}" if path else key
                    self.assertNotEqual(
                        key, "mapping_status",
                        f"legacy key mapping_status found at {location}",
                    )
                    walk(value, location)
            elif isinstance(node, list):
                for index, item in enumerate(node):
                    walk(item, f"{path}[{index}]")

        walk(self.ontology)

    def test_ontology_root_and_canonical_family_frozen(self):
        self.assertEqual(self.ontology["status"], "frozen")
        self.assertEqual(
            self.ontology["canonical_family"]["decision_status"], "frozen"
        )

    def test_ton_and_ciciot_frozen_entries_untouched_by_n_baiot_stage(self):
        ton = self.ontology["canonical_family"]["ton_iot_type_mapping"]["entries"]
        ciciot = self.ontology["canonical_family"]["ciciot2023_type_mapping"]["entries"]
        self.assertEqual(len(ton), 10)
        self.assertEqual(len(ciciot), 34)
        for e in ton:
            self.assertEqual(e["decision_status"], "frozen")
        for e in ciciot:
            self.assertEqual(e["decision_status"], "frozen")

    def test_status_partition_after_root_freeze(self):
        """After #22: the ontology root and canonical_family and the
        three binary_label.derivation entries are frozen on top of the
        frozen dataset-level tables (10 TON + 34 CIC + 11 N-BaIoT
        entries)."""
        ont = self.ontology
        for block, count in (
            ("ton_iot_type_mapping", 10),
            ("ciciot2023_type_mapping", 34),
            ("n_baiot_type_mapping", 11),
        ):
            entries = ont["canonical_family"][block]["entries"]
            self.assertEqual(len(entries), count)
            self.assertTrue(all(e["decision_status"] == "frozen" for e in entries), block)
        self.assertEqual(ont["status"], "frozen")
        self.assertEqual(ont["canonical_family"]["decision_status"], "frozen")
        for dataset, entry in ont["binary_label"]["derivation"].items():
            self.assertEqual(entry["decision_status"], "frozen", dataset)

    def test_n_baiot_freeze_metadata_declared(self):
        """The freeze id, V1R1 ZIP hash, and source commit must be
        declared on all three published surfaces."""
        desc = self.ontology["canonical_family"]["n_baiot_type_mapping"]["description"]
        self.assertIn("N-BAIOT-TYPE-MAPPING-20260905-V1-FROZEN", desc)
        self.assertIn(V1R1_ZIP_SHA, desc)
        md = LABEL_ONTOLOGY_MD_PATH.read_text(encoding="utf-8")
        self.assertIn("N-BAIOT-TYPE-MAPPING-20260905-V1-FROZEN", md)
        self.assertIn(V1R1_ZIP_SHA, md)
        dec = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn("N-BAIOT-TYPE-MAPPING-20260905-V1-FROZEN", dec)
        self.assertIn(V1R1_ZIP_SHA, dec)

    def test_mapped_families_subset_of_candidates(self):
        families = {e["canonical_family"] for e in
                    self.ontology["canonical_family"]["n_baiot_type_mapping"]["entries"]}
        candidates = set(self.ontology["canonical_family"]["candidate_families"])
        self.assertTrue(families.issubset(candidates), families - candidates)

    def test_binary_label_n_baiot_derivation_has_evidence(self):
        entry = self.ontology["binary_label"]["derivation"]["n_baiot"]
        self.assertIn("evidence_source", entry)
        self.assertIn("semantic_disposition", entry)
        self.assertIn("decision_status", entry)
        self.assertEqual(entry["semantic_disposition"], "exact")
        self.assertEqual(entry["decision_status"], "frozen")

    def test_binary_label_derivation_entries_frozen(self):
        derivation = self.ontology["binary_label"]["derivation"]
        for dataset, entry in derivation.items():
            self.assertEqual(
                entry["decision_status"], "frozen",
                f"binary_label.{dataset}: decision_status is not frozen",
            )

    def test_source_subtype_definition_uses_actual_directory_names(self):
        """v1 Rev 1 guard: the `source_subtype` definition section in
        LABEL_ONTOLOGY.md must cite the ACTUAL family directory names from
        the frozen inventory (mirai_attacks_extracted /
        gafgyt_attacks_extracted); the v1 package wrongly cited
        mirai_attacks / gafgyt_attacks, contradicting the verbatim claim."""
        md = LABEL_ONTOLOGY_MD_PATH.read_text(encoding="utf-8")
        # the correct names in the definition section
        self.assertIn(
            "(`mirai_attacks_extracted`/`gafgyt_attacks_extracted`)",
            md,
        )
        # the old wrong names must be gone from the definition section
        self.assertNotIn("(`mirai_attacks`/`gafgyt_attacks`)", md)

    def test_config_source_subtype_definition_consistent_with_inventory(self):
        """The config source_subtype role and the frozen inventory family
        directories must agree: the mapping keys use the extracted-tree
        directory names, and the definition section describes verbatim
        carry-over."""
        ontology = load_label_ontology()
        definition = ontology["source_subtype"]["per_dataset"]["n_baiot"]
        self.assertIn("family directory", definition)
        self.assertIn("verbatim", definition)
        # every mapping entry source_family must be an actual directory
        # name present in the frozen inventory
        fams_in_inv = set()
        for f in load_inventory()["files"]:
            parts = f["relative_path"].split("/")
            if len(parts) == 3:
                fams_in_inv.add(parts[1])
        for pair in EXPECTED_PAIRS:
            if pair[0] == "benign":
                continue
            self.assertIn(pair[0], fams_in_inv, pair)

    def test_package_counting_facts_v1r1(self):
        """v1 Rev 1 recorded counting facts: MANIFEST verifies 18/18 (the
        19 ordinary files include the MANIFEST itself, which does not hash
        itself), and the registry carried 3 source entries + 7 panels at
        that revision. The registry is append-only: the two CICIoT2023
        README page-1 feature-table entries added by the #23 Rev 1
        zero-admission revision (DECISIONS.md #23 Rev 1) come ON TOP of
        the historical three source entries, which are still present
        unchanged."""
        decisions = DECISIONS_PATH.read_text(encoding="utf-8")
        self.assertIn("18/18", decisions)
        self.assertIn("3 source entries + 7 panels", decisions)
        registry = json.loads(
            (REPO_ROOT / "references" / "dataset_docs" / "registry.json").read_text(encoding="utf-8")
        )
        # historical three source entries still present (append-only)
        files = [e["file"] for e in registry["entries"]]
        for historical in (
            "n_baiot/uci_dataset_page_2026-09-04.html",
            "n_baiot/meidan2018_arxiv_v1_2026-09-04.pdf",
            "ciciot2023/unb_iotdataset_page_2026-09-04.html",
        ):
            self.assertIn(historical, files)
        # the two #23 Rev 1 page-1 feature-table additions
        p1_tables = [
            f for f in files
            if f.startswith("ciciot2023/readme_p1_feature_table/")
        ]
        self.assertEqual(len(p1_tables), 2)
        self.assertEqual(len(registry["entries"]), 5)
        panels = registry["in_tree_frozen_docs_not_copied"]["ciciot2023_evidence_extraction"]
        self.assertEqual(len(panels), 9)

    def test_n_baiot_mapped_families_do_not_equal_ton_families(self):
        """N-BaIoT maps only to benign/bashlite/mirai; TON-IoT has no
        bashlite or mirai family, so no unconditioned cross-dataset family
        equivalence is created by this proposal."""
        n_baiot_families = {
            e["canonical_family"] for e in
            self.ontology["canonical_family"]["n_baiot_type_mapping"]["entries"]
        }
        self.assertEqual(n_baiot_families, {"benign", "bashlite", "mirai"})
        ton_families = {
            e["canonical_family"] for e in
            self.ontology["canonical_family"]["ton_iot_type_mapping"]["entries"]
        }
        self.assertNotIn("bashlite", ton_families)
        self.assertNotIn("mirai", ton_families)
        ciciot_families = {
            e["canonical_family"] for e in
            self.ontology["canonical_family"]["ciciot2023_type_mapping"]["entries"]
        }
        self.assertIn("mirai", ciciot_families)  # presence-only, conditional claims
        self.assertNotIn("bashlite", ciciot_families)


if __name__ == "__main__":
    unittest.main()
