import json
import tempfile
import unittest
from pathlib import Path

from tnsm_exp.validate import FORMAL_REQUIRED_PATHS, formal_gate


class FormalGateTests(unittest.TestCase):
    def make_repo(self, enabled: bool) -> Path:
        root = Path(self.temporary.name)
        (root / "config").mkdir(parents=True, exist_ok=True)
        (root / "config" / "protocol.json").write_text(
            json.dumps({"formal": {"enabled": enabled}}),
            encoding="utf-8",
        )
        return root

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()

    def tearDown(self):
        self.temporary.cleanup()

    def test_gate_is_locked_by_default(self):
        result = formal_gate(self.make_repo(enabled=False))
        self.assertFalse(result["passed"])

    def test_gate_passes_only_when_enabled_and_complete(self):
        root = self.make_repo(enabled=True)
        (root / "SOURCE_COMMIT").write_text("a" * 40 + "\n", encoding="utf-8")
        for relative in FORMAL_REQUIRED_PATHS:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}\n", encoding="utf-8")
        result = formal_gate(root)
        self.assertTrue(result["passed"])


if __name__ == "__main__":
    unittest.main()
