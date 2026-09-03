import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tnsm_exp.preflight import run_primary_preflight


GOOD_SNAPSHOT = {
    "hostname": "pi4b8g",
    "hardware_model": "Raspberry Pi 4 Model B Rev 1.5",
    "memory_total_bytes": 8 * 1024**3,
    "architecture": "aarch64",
    "ntp_synchronized": True,
    "temperature_c": 40.0,
    "throttled_hex": "0x0",
    "disk_free_bytes": 10 * 1024**3,
    "cpu_governors": {"cpu0": "ondemand", "cpu1": "ondemand"},
}


class PreflightTests(unittest.TestCase):
    def test_good_primary_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("tnsm_exp.preflight.snapshot", return_value=GOOD_SNAPSHOT):
                result = run_primary_preflight(root, root / "preflight.json")
        self.assertTrue(result["passed"])

    def test_throttle_blocks_run(self):
        bad = dict(GOOD_SNAPSHOT, throttled_hex="0x50005")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch("tnsm_exp.preflight.snapshot", return_value=bad):
                result = run_primary_preflight(root, root / "preflight.json")
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()

