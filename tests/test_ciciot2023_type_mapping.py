import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LABEL_ONTOLOGY_PATH = REPO_ROOT / "config" / "label_ontology.json"

# The 34 CICIoT2023 category directory names, from frozen inventory
# ciciot2023_20260903T142539Z.json (label_source: Directory and filename).
EXPECTED_DIRECTORIES = [
    "Backdoor_Malware",
    "Benign_Final",
    "BrowserHijacking",
    "CommandInjection",
    "DDoS-ACK_Fragmentation",
    "DDoS-HTTP_Flood",
    "DDoS-ICMP_Flood",
    "DDoS-ICMP_Fragmentation",
    "DDoS-PSHACK_FLOOD",
    "DDoS-RSTFINFLOOD",
    "DDoS-SYN_Flood",
    "DDoS-SlowLoris",
    "DDoS-SynonymousIP_Flood",
    "DDoS-TCP_Flood",
    "DDoS-UDP_Flood",
    "DDoS-UDP_Fragmentation",
    "DNS_Spoofing",
    "DictionaryBruteForce",
    "DoS-HTTP_Flood",
    "DoS-SYN_Flood",
    "DoS-TCP_Flood",
    "DoS-UDP_Flood",
    "MITM-ArpSpoofing",
    "Mirai-greeth_flood",
    "Mirai-greip_flood",
    "Mirai-udpplain",
    "Recon-HostDiscovery",
    "Recon-OSScan",
    "Recon-PingSweep",
    "Recon-PortScan",
    "SqlInjection",
    "Uploading_Attack",
    "VulnerabilityScan",
    "XSS",
]

# Complete expected mapping table: directory -> (official_category,
# canonical_family, semantic_disposition). Locks the entire proposal so a
# wrong assignment (e.g. Backdoor_Malware -> backdoor) fails even though
# both names are individually valid families.
EXPECTED_MAPPING = {
    "Benign_Final":            ("benign",      "benign",     "exact"),
    "DDoS-ACK_Fragmentation":  ("DDoS",        "ddos",       "exact"),
    "DDoS-HTTP_Flood":         ("DDoS",        "ddos",       "exact"),
    "DDoS-ICMP_Flood":         ("DDoS",        "ddos",       "exact"),
    "DDoS-ICMP_Fragmentation": ("DDoS",        "ddos",       "exact"),
    "DDoS-PSHACK_FLOOD":       ("DDoS",        "ddos",       "exact"),
    "DDoS-RSTFINFLOOD":        ("DDoS",        "ddos",       "exact"),
    "DDoS-SYN_Flood":          ("DDoS",        "ddos",       "exact"),
    "DDoS-SlowLoris":          ("DDoS",        "ddos",       "exact"),
    "DDoS-SynonymousIP_Flood": ("DDoS",        "ddos",       "exact"),
    "DDoS-TCP_Flood":          ("DDoS",        "ddos",       "exact"),
    "DDoS-UDP_Flood":          ("DDoS",        "ddos",       "exact"),
    "DDoS-UDP_Fragmentation":  ("DDoS",        "ddos",       "exact"),
    "DNS_Spoofing":            ("Spoofing",    "spoofing",   "exact"),
    "DictionaryBruteForce":    ("Brute Force", "brute_force", "exact"),
    "DoS-HTTP_Flood":          ("DoS",         "dos",        "exact"),
    "DoS-SYN_Flood":           ("DoS",         "dos",        "exact"),
    "DoS-TCP_Flood":           ("DoS",         "dos",        "exact"),
    "DoS-UDP_Flood":           ("DoS",         "dos",        "exact"),
    "MITM-ArpSpoofing":        ("Spoofing",    "spoofing",   "exact"),
    "Mirai-greeth_flood":      ("Mirai",       "mirai",      "exact"),
    "Mirai-greip_flood":       ("Mirai",       "mirai",      "exact"),
    "Mirai-udpplain":          ("Mirai",       "mirai",      "exact"),
    "Recon-HostDiscovery":     ("Recon",       "recon",      "exact"),
    "Recon-OSScan":            ("Recon",       "recon",      "exact"),
    "Recon-PingSweep":         ("Recon",       "recon",      "exact"),
    "Recon-PortScan":          ("Recon",       "recon",      "exact"),
    "SqlInjection":            ("Web-based",   "web_attack", "exact"),
    "Uploading_Attack":        ("Web-based",   "web_attack", "exact"),
    "VulnerabilityScan":       ("Recon",       "recon",      "exact"),
    "XSS":                     ("Web-based",   "web_attack", "exact"),
    "Backdoor_Malware":        ("Web-based",   "web_attack", "exact"),
    "BrowserHijacking":        ("Web-based",   "web_attack", "exact"),
    "CommandInjection":        ("Web-based",   "web_attack", "exact"),
}

VALID_DISPOSITIONS = ["exact", "derived", "unresolved", "rejected"]
VALID_DECISION_STATUSES = ["proposed", "frozen"]
README_SHA = "0f48daba395be03985f612ce706d33f1a25e4008cb94c3ad7b6f6332fbdbee92"
INVENTORY_NAME = "ciciot2023_20260903T142539Z.json"


def load_label_ontology():
    with LABEL_ONTOLOGY_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


class Ciciot2023TypeMappingTests(unittest.TestCase):
    """Tests for the CICIoT2023 34 category directories ->
    canonical_family mapping PROPOSAL (nothing frozen yet)."""

    def setUp(self):
        self.ontology = load_label_ontology()
        self.mapping = self.ontology["canonical_family"]["ciciot2023_type_mapping"]
        self.entries = {
            e["source_type"]: e for e in self.mapping["entries"]
        }

    def test_full_expected_mapping_table(self):
        """Every directory must map to exactly the expected official
        category, family, and disposition; all 34 entries now carry
        decision_status == frozen (CICIOT2023-TYPE-MAPPING-20260904-V1-FROZEN)."""
        self.assertEqual(
            set(self.entries.keys()), set(EXPECTED_MAPPING.keys()),
            "entry set differs from the expected 34-directory table",
        )
        for source_type, (cat, family, disposition) in EXPECTED_MAPPING.items():
            entry = self.entries[source_type]
            self.assertEqual(
                entry["official_category"], cat,
                f"{source_type}: official_category is {entry.get('official_category')}, expected {cat}",
            )
            self.assertEqual(
                entry["canonical_family"], family,
                f"{source_type}: family is {entry['canonical_family']}, expected {family}",
            )
            self.assertEqual(
                entry["semantic_disposition"], disposition,
                f"{source_type}: disposition is {entry['semantic_disposition']}, expected {disposition}",
            )
            self.assertEqual(
                entry["decision_status"], "frozen",
                f"{source_type}: decision_status is not frozen",
            )

    def test_all_34_directories_present(self):
        self.assertEqual(len(EXPECTED_DIRECTORIES), 34)
        for name in EXPECTED_DIRECTORIES:
            self.assertIn(name, self.entries, f"missing directory {name}")

    def test_exactly_zero_derived_entries(self):
        dispositions = [e["semantic_disposition"] for e in self.mapping["entries"]]
        self.assertEqual(dispositions.count("derived"), 0)
        self.assertEqual(dispositions.count("exact"), 34)

    def test_dictionarybruteforce_is_brute_force_exact(self):
        entry = self.entries["DictionaryBruteForce"]
        self.assertEqual(entry["canonical_family"], "brute_force")
        self.assertEqual(entry["semantic_disposition"], "exact")
        rationale = entry["rationale"]
        self.assertIn("REJECTED by the reviewer", rationale)
        self.assertIn("NOT equated with CICIoT2023 brute_force", rationale)
        self.assertIn("DECISIONS.md #17", rationale)

    def test_ton_iot_password_not_equated_with_ciciot_brute_force(self):
        """Guard: no CICIoT2023 entry may claim equivalence between the
        TON-IoT password family and the CICIoT2023 brute_force family;
        the comparison-candidate phrase in the frozen TON-IoT password
        rationale is superseded by DECISIONS.md #17 and NOT established."""
        for entry in self.mapping["entries"]:
            rationale = entry["rationale"]
            if "brute_force" in rationale:
                self.assertIn(
                    "NOT equated with CICIoT2023 brute_force", rationale,
                    f"{entry['source_type']}: brute_force mentioned without the "
                    "non-equivalence statement",
                )
                self.assertNotIn(
                    "genuine cross-dataset comparison", rationale,
                    f"{entry['source_type']} claims genuine cross-dataset comparison",
                )

    def test_unb_page_inconsistency_disclosed(self):
        """The UNB page states 33 attacks but its detail lists enumerate
        32 (DDoS omits DDoS-ICMP_Fragmentation); the enumeration baseline
        must be the frozen directories + README.pdf, and the
        DDoS-ICMP_Fragmentation entry must still be present."""
        desc = self.mapping["description"]
        self.assertIn("32", desc)
        self.assertIn("DDoS-ICMP_Fragmentation", desc)
        self.assertIn("frozen inventory directories plus README.pdf", desc)
        self.assertIn("DDoS-ICMP_Fragmentation", self.entries)
        self.assertEqual(
            self.entries["DDoS-ICMP_Fragmentation"]["canonical_family"], "ddos",
        )

    def test_description_cites_unb_snapshot_and_panels(self):
        desc = self.mapping["description"]
        self.assertIn(
            "99ae08c233d26aaa1c6cc5baa9eb6860587077cc2bc1097c63457bface422852", desc,
            "description lacks the UNB page snapshot SHA-256",
        )
        self.assertIn("readme_p2_panels", desc)
        self.assertIn("registry.json", desc)

    def test_benign_final_is_the_only_benign_source(self):
        benign_entries = [
            name for name, e in self.entries.items()
            if e["canonical_family"] == "benign"
        ]
        self.assertEqual(benign_entries, ["Benign_Final"])

    def test_benign_final_coverage_invariant_text(self):
        entry = self.entries["Benign_Final"]
        self.assertIn("coverage invariant", entry["rationale"].lower())
        self.assertIn("1,098,191", entry["rationale"])

    def test_backdoor_malware_discloses_name_conflict(self):
        rationale = self.entries["Backdoor_Malware"]["rationale"]
        self.assertIn("Web-based", rationale)
        self.assertIn("NOT the backdoor family", rationale)

    def test_mitm_arp_spoofing_discloses_alternative(self):
        rationale = self.entries["MITM-ArpSpoofing"]["rationale"]
        self.assertIn("Spoofing", rationale)
        self.assertIn("mitm family", rationale, "alternative not disclosed")
        self.assertIn("no CICIoT2023 member", rationale)

    def test_vulnerability_scan_discloses_missing_prefix(self):
        rationale = self.entries["VulnerabilityScan"]["rationale"]
        self.assertIn("Recon", rationale)
        self.assertIn("prefix", rationale)

    def test_dos_udp_flood_records_quality_exceptions(self):
        rationale = self.entries["DoS-UDP_Flood"]["rationale"]
        self.assertIn("DoS-UDP_Flood7/8/9", rationale)
        self.assertIn("ciciot2023_20260903T142232Z", rationale)

    def test_mirai_entries_record_n_baiot_family_presence(self):
        for name in ("Mirai-greeth_flood", "Mirai-greip_flood", "Mirai-udpplain"):
            rationale = self.entries[name]["rationale"]
            self.assertIn("mirai_attacks_extracted", rationale)
            self.assertIn(
                "subject to separate mapping freezes", rationale,
                f"{name}: N-BaIoT family presence not conditional",
            )

    def test_every_entry_has_required_fields(self):
        required = [
            "source_type", "official_category", "canonical_family",
            "semantic_disposition", "decision_status", "evidence_source",
            "rationale",
        ]
        for entry in self.mapping["entries"]:
            for field in required:
                self.assertIn(field, entry, f"missing {field} in {entry['source_type']}")

    def test_evidence_and_rationale_nonempty(self):
        for entry in self.mapping["entries"]:
            self.assertTrue(entry["evidence_source"].strip())
            self.assertTrue(entry["rationale"].strip())

    def test_evidence_cites_readme_and_inventory(self):
        for entry in self.mapping["entries"]:
            self.assertIn(
                README_SHA, entry["evidence_source"],
                f"{entry['source_type']} evidence lacks the README.pdf SHA-256",
            )
            self.assertIn(
                INVENTORY_NAME, entry["evidence_source"],
                f"{entry['source_type']} evidence lacks the frozen inventory",
            )

    def test_description_declares_freeze_stage(self):
        """The mapping-level description must record the freeze metadata
        (V2R2 evidence ZIP hash, source commit, freeze id)."""
        desc = self.mapping["description"]
        self.assertIn("CICIOT2023-TYPE-MAPPING-20260904-V1-FROZEN", desc)
        self.assertIn("f8529ea2c721057ce205b862ff37bb3a4cbcb1c8d5524d30cc0b28f93f3d447b", desc)
        self.assertIn("93e8350", desc)
        self.assertIn("DECISIONS.md #18", desc)
        self.assertIn("13 -> 14", desc)
        self.assertIn(README_SHA, desc)
        self.assertIn("0 derived", desc)
        self.assertIn("no mapping, semantic_disposition, evidence, or rationale", desc)

    def test_mapping_decision_status_root_remains_proposed(self):
        """The ontology root and canonical_family.decision_status stay
        proposed until the N-BaIoT mapping is frozen."""
        self.assertEqual(self.mapping.get("decision_status", "proposed"), "proposed")

    def test_ton_iot_freeze_untouched_by_ciciot_stage(self):
        ton = self.ontology["canonical_family"]["ton_iot_type_mapping"]
        self.assertEqual(len(ton["entries"]), 10)
        for entry in ton["entries"]:
            self.assertEqual(
                entry["decision_status"], "frozen",
                f"TON-IoT freeze regression at {entry['source_type']}",
            )

    def test_candidate_families_extended_to_fourteen(self):
        candidates = self.ontology["canonical_family"]["candidate_families"]
        self.assertEqual(len(candidates), 14)
        self.assertIn("spoofing", candidates)
        self.assertIn("brute_force", candidates)

    def test_mapped_families_subset_of_candidates(self):
        candidates = set(self.ontology["canonical_family"]["candidate_families"])
        for entry in self.mapping["entries"]:
            self.assertIn(
                entry["canonical_family"], candidates,
                f"family {entry['canonical_family']} not in candidate_families",
            )

    def test_coverage_invariant_recorded(self):
        inv = self.mapping["coverage_invariant"]
        self.assertIn("rule", inv)
        self.assertIn("evidence_source", inv)
        self.assertIn(INVENTORY_NAME, inv["evidence_source"])
        self.assertIn("no label column", inv["evidence_source"])

    def test_cross_dataset_claims_are_conditional(self):
        for entry in self.mapping["entries"]:
            rationale = entry["rationale"]
            if "cross-dataset family comparison" in rationale:
                self.assertIn(
                    "subject to separate", rationale,
                    f"{entry['source_type']} cross-dataset claim is not conditional",
                )
            self.assertNotIn(
                "genuine cross-dataset comparison", rationale,
                f"{entry['source_type']} claims genuine cross-dataset comparison",
            )

    def test_official_category_axis_beats_directory_name(self):
        """The four name-vs-category conflicts must all resolve to the
        official category axis (v2: DictionaryBruteForce -> brute_force
        per user verification of v1)."""
        self.assertEqual(self.entries["Backdoor_Malware"]["canonical_family"], "web_attack")
        self.assertEqual(self.entries["VulnerabilityScan"]["canonical_family"], "recon")
        self.assertEqual(self.entries["MITM-ArpSpoofing"]["canonical_family"], "spoofing")
        self.assertEqual(self.entries["DictionaryBruteForce"]["canonical_family"], "brute_force")
    # ----- v2 evidence-package revision (Rev 1) guard tests -----

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

    def test_dictionary_brute_force_is_single_attack_name(self):
        """The README Brute Force item is ONE attack name rendered across
        three lines by the PDF page layout, not two attack names; the
        old split wording must be gone from every published surface."""
        desc = self.mapping["description"]
        rationale = self.entries["DictionaryBruteForce"]["rationale"]
        md = (REPO_ROOT / "docs" / "LABEL_ONTOLOGY.md").read_text(encoding="utf-8")
        registry = json.loads(
            (REPO_ROOT / "references" / "dataset_docs" / "registry.json").read_text(encoding="utf-8")
        )
        reg_text = json.dumps(registry)

        new_markers = [
            ("description", "single attack name 'Dictionary Brute Force'" in desc),
            ("description", "rendered across three lines" in desc),
            ("description", "PDF page layout" in desc),
            ("rationale", "single attack name 'Dictionary Brute Force'" in rationale),
            ("rationale", "rendered across three lines" in rationale),
            ("LABEL_ONTOLOGY.md", "single attack name" in md),
            ("LABEL_ONTOLOGY.md", "rendered across three lines" in md),
        ]
        for surface, ok in new_markers:
            self.assertTrue(ok, f"{surface}: single-name wording missing")
        old_markers = [
            ("description", "names 'Dictionary' and 'Brute Force'" in desc),
            ("description", "two attack names" in desc),
            ("rationale", "two attack names" in rationale),
            ("LABEL_ONTOLOGY.md", "two attack names" in md),
            ("LABEL_ONTOLOGY.md", "are both carried by the single" in md),
            ("LABEL_ONTOLOGY.md", "wrapped across two lines" in md),
            ("registry.json", "(Dictionary, Brute Force)" in reg_text),
        ]
        for surface, present in old_markers:
            self.assertFalse(present, f"{surface}: old split wording still present")
        # the mapping result itself is unchanged
        self.assertEqual(self.entries["DictionaryBruteForce"]["canonical_family"], "brute_force")
        self.assertEqual(self.entries["DictionaryBruteForce"]["semantic_disposition"], "exact")

    def test_mitm_alternative_recorded_as_rejected(self):
        """The mitm family alternative was considered and rejected under
        DECISIONS.md #17; it must no longer be described as open."""
        rationale = self.entries["MITM-ArpSpoofing"]["rationale"]
        self.assertIn("considered and rejected", rationale)
        self.assertIn("#17", rationale)
        self.assertNotIn("remains open", rationale)
        md = (REPO_ROOT / "docs" / "LABEL_ONTOLOGY.md").read_text(encoding="utf-8")
        self.assertNotIn("stays open", md)
        self.assertIn("considered and rejected", md)
        # mapping result unchanged
        self.assertEqual(self.entries["MITM-ArpSpoofing"]["canonical_family"], "spoofing")
        self.assertEqual(self.entries["MITM-ArpSpoofing"]["semantic_disposition"], "exact")

    def test_registry_panels_carry_sha256_matching_files(self):
        """Each of the 7 README page-2 panel entries in registry.json must
        carry a sha256 equal to the SHA-256 of the actual PNG file."""
        import hashlib
        registry = json.loads(
            (REPO_ROOT / "references" / "dataset_docs" / "registry.json").read_text(encoding="utf-8")
        )
        panels = registry["in_tree_frozen_docs_not_copied"]["ciciot2023_evidence_extraction"]
        panel_entries = [p for p in panels if "readme_p2_panels" in p.get("file", "")]
        self.assertEqual(len(panel_entries), 7)
        for entry in panel_entries:
            self.assertIn("sha256", entry, f"{entry['file']}: sha256 missing")
            png = REPO_ROOT / entry["file"]
            digest = hashlib.sha256(png.read_bytes()).hexdigest()
            self.assertEqual(
                entry["sha256"], digest,
                f"{entry['file']}: registry sha256 does not match the actual file",
            )





class OntologyWideDisciplineTests(unittest.TestCase):
    """Ontology-wide guards extended to the CICIoT2023 stage."""

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

        walk(load_label_ontology())

    def test_ontology_root_and_canonical_family_remain_proposed(self):
        ontology = load_label_ontology()
        self.assertEqual(ontology["status"], "proposed")
        self.assertEqual(ontology["canonical_family"]["decision_status"], "proposed")

    def test_binary_label_derivation_entries_remain_proposed(self):
        derivation = load_label_ontology()["binary_label"]["derivation"]
        for dataset, entry in derivation.items():
            self.assertEqual(
                entry["decision_status"], "proposed",
                f"binary_label.{dataset}: decision_status is not proposed",
            )

    def test_binary_label_ciciot2023_derivation_has_evidence(self):
        entry = load_label_ontology()["binary_label"]["derivation"]["ciciot2023"]
        self.assertIn("evidence_source", entry)
        self.assertIn(INVENTORY_NAME, entry["evidence_source"])
        self.assertIn("no label column", entry["evidence_source"])
        self.assertIn("semantic_disposition", entry)
        self.assertIn("decision_status", entry)
        self.assertEqual(entry["semantic_disposition"], "exact")
        self.assertEqual(entry["decision_status"], "proposed")

if __name__ == "__main__":
    unittest.main()
