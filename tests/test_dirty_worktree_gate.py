import subprocess
import tempfile
import unittest
from pathlib import Path

from tnsm_exp.dataset_registry import DirtyWorktreeError
from tnsm_exp.util import worktree_is_dirty


def git(root: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True)


class DirtyWorktreeGateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "config", "user.name", "Test")
        (self.root / "tracked.txt").write_text("committed\n", encoding="utf-8")
        git(self.root, "add", "tracked.txt")
        git(self.root, "commit", "-q", "-m", "initial")

    def tearDown(self):
        self.temporary.cleanup()

    def test_clean_worktree_passes(self):
        self.assertFalse(worktree_is_dirty(self.root))

    def test_untracked_file_is_dirty(self):
        (self.root / "untracked.txt").write_text("x\n", encoding="utf-8")
        self.assertTrue(worktree_is_dirty(self.root))

    def test_modified_file_is_dirty(self):
        (self.root / "tracked.txt").write_text("changed\n", encoding="utf-8")
        self.assertTrue(worktree_is_dirty(self.root))

    def test_temp_script_does_not_block(self):
        # Agent scratch space: untracked .temp/ files must never block evidence
        # generation, regardless of location inside .temp/.
        (self.root / ".temp").mkdir()
        (self.root / ".temp" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (self.root / ".temp" / "nested").mkdir()
        (self.root / ".temp" / "nested" / "draft.py").write_text("x = 1\n", encoding="utf-8")
        self.assertFalse(worktree_is_dirty(self.root))

    def test_untracked_docs_must_block(self):
        (self.root / "docs").mkdir()
        (self.root / "docs" / "test.md").write_text("protocol change\n", encoding="utf-8")
        self.assertTrue(worktree_is_dirty(self.root))

    def test_untracked_source_must_block(self):
        (self.root / "src").mkdir()
        (self.root / "src" / "test.py").write_text("print('unreviewed')\n", encoding="utf-8")
        self.assertTrue(worktree_is_dirty(self.root))

    def test_untracked_artifacts_manifest_does_not_block(self):
        # Evidence manifests are the output of these very commands; a fresh
        # acquisition manifest must not block the immediately following
        # inventory run.
        manifest_dir = self.root / "artifacts" / "datasets" / "acquisitions"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "ton_iot_20260904T000000Z.json").write_text("{}\n", encoding="utf-8")
        self.assertFalse(worktree_is_dirty(self.root))

    def test_untracked_artifacts_alongside_dirty_source_still_blocks(self):
        # The artifacts exemption must not mask genuine dirty state.
        manifest_dir = self.root / "artifacts" / "datasets" / "acquisitions"
        manifest_dir.mkdir(parents=True)
        (manifest_dir / "ton_iot_20260904T000000Z.json").write_text("{}\n", encoding="utf-8")
        (self.root / "src").mkdir()
        (self.root / "src" / "test.py").write_text("print('unreviewed')\n", encoding="utf-8")
        self.assertTrue(worktree_is_dirty(self.root))

    def test_evidence_command_fails_closed_on_dirty_worktree(self):
        # Import here to avoid a repo-root dependency in setUp
        from tnsm_exp.dataset_registry import register_acquisition

        (self.root / "untracked.txt").write_text("x\n", encoding="utf-8")
        incoming = self.root / "incoming"
        incoming.mkdir()
        (incoming / "data.zip").write_bytes(b"bytes\n")
        with self.assertRaises(DirtyWorktreeError):
            register_acquisition(self.root, "ton_iot", incoming)
        # No manifest output should exist after the refusal
        artifacts = self.root / "artifacts" / "datasets" / "acquisitions"
        self.assertFalse(artifacts.exists())

    def test_gitignored_temp_file_does_not_block(self):
        # .temp/ lives in .gitignore; git status does not even report it.
        gitignore = self.root / ".gitignore"
        gitignore.write_text(".temp/\n", encoding="utf-8")
        git(self.root, "add", ".gitignore")
        git(self.root, "commit", "-q", "-m", "ignore temp")
        (self.root / ".temp").mkdir()
        (self.root / ".temp" / "test.sh").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        self.assertFalse(worktree_is_dirty(self.root))


class SequentialEvidenceRunTests(unittest.TestCase):
    """Integration: acquisition -> inventory on a clean repo.

    The second command must not be rejected merely because the first command
    wrote a new (untracked) evidence manifest into artifacts/.
    """

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "test@example.invalid")
        git(self.root, "config", "user.name", "Test")
        # Minimal repo layout the code under test expects. incoming/ mirrors
        # the real repo, where raw dataset directories are gitignored.
        config_dir = self.root / "config"
        config_dir.mkdir()
        (config_dir / "datasets.json").write_text(
            '{"datasets": {"ton_iot": {'
            '"display_name": "TON-IoT", '
            '"official_page": "https://example.invalid/ton-iot", '
            '"access_method": "download", '
            '"selected_scope": "train_test", '
            '"license_note": "test", '
            '"label_source": "label column"}}}',
            encoding="utf-8",
        )
        (self.root / ".gitignore").write_text("incoming/\n", encoding="utf-8")
        git(self.root, "add", ".gitignore", "config")
        git(self.root, "commit", "-q", "-m", "initial")

        incoming = self.root / "incoming" / "ton_iot"
        incoming.mkdir(parents=True)
        (incoming / "train.csv").write_text(
            "a,b,label\n1,2,normal\n3,4,attack\n",
            encoding="utf-8",
        )
        self.incoming = incoming

    def tearDown(self):
        self.temporary.cleanup()

    def test_inventory_after_acquisition_is_not_rejected(self):
        from tnsm_exp.dataset_registry import inventory_csv_tree, register_acquisition

        acquisition_path, _ = register_acquisition(self.root, "ton_iot", self.incoming)
        self.assertTrue(acquisition_path.exists())
        inventory_path, result = inventory_csv_tree(self.root, "ton_iot", self.incoming)
        self.assertTrue(inventory_path.exists())
        self.assertEqual(result["total_rows"], 2)

    def test_untracked_protocol_doc_still_blocks_inventory(self):
        from tnsm_exp.dataset_registry import inventory_csv_tree, register_acquisition

        register_acquisition(self.root, "ton_iot", self.incoming)
        docs = self.root / "docs"
        docs.mkdir()
        (docs / "DATASET_ACQUISITION.md").write_text("uncommitted protocol\n", encoding="utf-8")
        with self.assertRaises(DirtyWorktreeError):
            inventory_csv_tree(self.root, "ton_iot", self.incoming)


if __name__ == "__main__":
    unittest.main()
