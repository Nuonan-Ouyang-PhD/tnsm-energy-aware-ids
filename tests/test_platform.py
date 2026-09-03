import unittest

from tnsm_exp.platform_info import decode_throttled


class ThrottleDecodeTests(unittest.TestCase):
    def test_zero_is_clean(self):
        self.assertTrue(all(value is False for value in decode_throttled(0).values()))

    def test_current_and_historical_bits(self):
        flags = decode_throttled(0x50005)
        self.assertTrue(flags["undervoltage_now"])
        self.assertTrue(flags["throttled_now"])
        self.assertTrue(flags["undervoltage_occurred"])
        self.assertTrue(flags["throttled_occurred"])
        self.assertFalse(flags["arm_frequency_capped_now"])

    def test_unavailable_remains_unknown(self):
        self.assertTrue(all(value is None for value in decode_throttled(None).values()))


if __name__ == "__main__":
    unittest.main()

