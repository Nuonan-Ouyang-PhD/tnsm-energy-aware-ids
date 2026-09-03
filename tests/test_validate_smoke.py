import csv
import json
import tempfile
import unittest
from pathlib import Path

from tnsm_exp.validate import validate_smoke


class SmokeValidationTests(unittest.TestCase):
    def create_run(self, root: Path, second_temperature: float = 42.0) -> Path:
        run_dir = root / "run"
        run_dir.mkdir()
        with (run_dir / "events.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["sequence", "window_start_monotonic_ns"],
            )
            writer.writeheader()
            writer.writerows(
                [
                    {"sequence": 0, "window_start_monotonic_ns": 100},
                    {"sequence": 1, "window_start_monotonic_ns": 200},
                ]
            )
        fields = [
            "monotonic_ns",
            "temperature_c",
            "throttled_hex",
            "undervoltage_now",
            "arm_frequency_capped_now",
            "throttled_now",
            "soft_temperature_limit_now",
        ]
        with (run_dir / "telemetry.csv").open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for timestamp, temperature in [(110, 40.0), (210, second_temperature)]:
                writer.writerow(
                    {
                        "monotonic_ns": timestamp,
                        "temperature_c": temperature,
                        "throttled_hex": "0x0",
                        "undervoltage_now": False,
                        "arm_frequency_capped_now": False,
                        "throttled_now": False,
                        "soft_temperature_limit_now": False,
                    }
                )
        (run_dir / "manifest.json").write_text(
            json.dumps(
                {
                    "run_id": "fixture",
                    "paper_eligible": False,
                    "start_host_snapshot": {"throttled_hex": "0x0"},
                    "end_host_snapshot": {"throttled_hex": "0x0"},
                }
            ),
            encoding="utf-8",
        )
        return run_dir

    def test_complete_clean_run_passes(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = validate_smoke(self.create_run(Path(temporary)), 2, 60.0)
        self.assertTrue(result["passed"])

    def test_temperature_violation_fails(self):
        with tempfile.TemporaryDirectory() as temporary:
            result = validate_smoke(self.create_run(Path(temporary), 61.0), 2, 60.0)
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()

