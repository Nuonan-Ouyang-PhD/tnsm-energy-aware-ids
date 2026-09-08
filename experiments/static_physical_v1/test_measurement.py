import struct
import unittest
from unittest.mock import patch
import measurement
import profile_worker


def frame(v=5400000,i=-400000,sequence=42):
    raw=bytearray(64);struct.pack_into('<II',raw,0,65|(sequence<<8),1)
    struct.pack_into('<ii',raw,16,v,i);return bytes(raw)


class MeasurementTests(unittest.TestCase):
    def test_read_only_command(self):
        packet=measurement.request(42)
        self.assertEqual(len(packet),65)
        self.assertEqual(struct.unpack_from('<I',packet,1)[0],12|(42<<8)|(1<<17))
        self.assertEqual(packet[5:],bytes(60))

    def test_signed_units(self):
        value=measurement.decode(frame(),42)
        self.assertAlmostEqual(value['watts'],2.16)
        self.assertEqual(value['signed_amps'],-.4)

    def test_reject_corrupt_or_stale_reply(self):
        for raw in (frame()[:32],frame(sequence=43),bytes(64)):
            with self.assertRaises(ValueError):measurement.decode(raw,42)

    def test_voltage_current_guards(self):
        for v,i in ((5600000,-400000),(4700000,-400000),(5400000,400000),(5400000,-3100000),(5400000,0)):
            with self.assertRaises(ValueError):measurement.decode(frame(v,i),42)
        with self.assertRaises(ValueError):measurement.decode(frame(v=4900000),42,baseline=5.4)

    def test_energy_actual_interval(self):
        samples=[{'sample_monotonic':t,'watts':w} for t,w in ((10,1),(11,3),(12,5))]
        self.assertEqual(measurement.integrate(samples),(6.,2))

    def test_energy_does_not_fill_gaps(self):
        for times in ((10,12),(10,10),(10,9)):
            with self.assertRaises(ValueError):measurement.integrate([{'sample_monotonic':t,'watts':2} for t in times])

    def test_remote_watchdog(self):
        profile_worker.control_closed.clear()
        with patch.object(profile_worker.time,'monotonic',return_value=100),patch.object(profile_worker,'last_heartbeat',94):
            with self.assertRaises(RuntimeError):profile_worker.watch_guard()
        profile_worker.control_closed.set()
        with self.assertRaises(RuntimeError):profile_worker.watch_guard()
        profile_worker.control_closed.clear()


if __name__=='__main__':unittest.main()
