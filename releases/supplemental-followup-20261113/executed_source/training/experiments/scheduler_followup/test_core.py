"""Synthetic regression tests; not physical or scientific results."""
import unittest
from core import Observation, deadline_guard, external_busy_fraction, reward
from cpu_guard import interval


class SharedObservationTests(unittest.TestCase):
    def test_nominal_arrivals_do_not_create_backlog(self):
        view = Observation(100, 0, 0.5, 1)
        self.assertEqual(view.work_rows, 100)
        self.assertEqual((view.index // 12) % 3, 0)

    def test_current_arrivals_change_rl_state_immediately(self):
        self.assertEqual(len({Observation(n, 0, .5, 1).index for n in (50, 100, 4000)}), 3)

    def test_backlog_changes_state_independently(self):
        self.assertEqual(len({Observation(100, q, .5, 1).index for q in (0, 50, 200)}), 3)

    def test_guard_uses_same_backlog_and_current_arrivals(self):
        self.assertEqual(deadline_guard(Observation(100, 0, .5, 1), .03), 2)
        self.assertEqual(deadline_guard(Observation(4000, 0, .5, 1), .03), 1)
        self.assertEqual(deadline_guard(Observation(100, 3900, .5, 1), .03), 1)

    def test_no_temperature_in_observation(self):
        self.assertNotIn("temperature", str(Observation.__annotations__))


class RewardTests(unittest.TestCase):
    def score(self, ba=1, power=0, duration=0, backlog=0):
        return reward(balanced_accuracy=ba, normalized_power=power,
                      completion_seconds=duration, backlog_rows=backlog, work_rows=100)

    def test_miss_has_explicit_penalty(self):
        score, parts = self.score(duration=1.01)
        self.assertEqual(parts["deadline"], -1)
        self.assertLess(score, self.score(ba=0, power=1, duration=1)[0])

    def test_backlog_has_explicit_penalty(self):
        _, parts = self.score(backlog=50)
        self.assertEqual(parts["deadline"], -1)
        self.assertEqual(parts["backlog"], -.5)

    def test_no_thermal_component(self):
        self.assertNotIn("thermal", str(self.score()[1]))

    def test_nonfinite_completion_rejected(self):
        with self.assertRaises(ValueError):
            self.score(duration=float("nan"))


class CpuGuardTests(unittest.TestCase):
    def bounded_pair(self, busy_end=200):
        proc = {1: {"starttime": 10, "ppid": 0, "cpu_ticks": 0, "comm": "worker"}}
        left = {"processes": proc, "accounting": {
            "begin": {"total": 1000, "idle": 800},
            "end": {"total": 1002, "idle": 801},
            "roots": {1: {"starttime": 10, "cpu_ticks": 100}}}}
        right = {"processes": proc, "accounting": {
            "begin": {"total": 1400, "idle": 1400-busy_end},
            "end": {"total": 1402, "idle": 1401-busy_end},
            "roots": {1: {"starttime": 10, "cpu_ticks": 100}}}}
        return left, right

    def test_bounded_read_passes_quiet_interval(self):
        left, right = self.bounded_pair()
        result = interval(left, right, {1})
        self.assertTrue(result["pass"])
        self.assertEqual(result["busy_ticks_upper_bound"], 1)

    def test_bounded_read_detects_external_load(self):
        left, right = self.bounded_pair(busy_end=300)
        self.assertFalse(interval(left, right, {1})["pass"])

    def test_bounded_read_subtracts_only_bound_worker_time(self):
        left, right = self.bounded_pair(busy_end=300)
        right["accounting"]["roots"][1]["cpu_ticks"] = 200
        self.assertTrue(interval(left, right, {1})["pass"])

    def test_bounded_read_rejects_unknown_roots(self):
        left, right = self.bounded_pair()
        with self.assertRaises(ValueError):
            interval(left, right, {1, 2})

    def test_bounded_read_rejects_reused_pid(self):
        left, right = self.bounded_pair()
        right["accounting"]["roots"][1]["starttime"] = 11
        with self.assertRaises(ValueError):
            interval(left, right, {1})

    def test_bounded_read_rejects_overlapping_snapshots(self):
        left, right = self.bounded_pair()
        right["accounting"]["begin"]["total"] = 1001
        with self.assertRaises(ValueError):
            interval(left, right, {1})

    def test_unrelated_cpu_is_visible(self):
        self.assertEqual(external_busy_fraction(total_ticks=400, idle_ticks=200,
                                               allowed_process_ticks=20), .45)

    def test_worker_cpu_not_external(self):
        self.assertEqual(external_busy_fraction(total_ticks=400, idle_ticks=200,
                                               allowed_process_ticks=200), 0)

    def test_missing_interval_rejected(self):
        with self.assertRaises(ValueError):
            external_busy_fraction(total_ticks=0, idle_ticks=0, allowed_process_ticks=0)

    def test_pid_reuse_not_attributed_to_allowed_process(self):
        left = {"total": 0, "idle": 0, "processes": {
            1: {"starttime": 10, "ppid": 0, "cpu_ticks": 0, "comm": "worker"}}}
        right = {"total": 400, "idle": 0, "processes": {
            1: {"starttime": 20, "ppid": 0, "cpu_ticks": 400, "comm": "compiler"}}}
        with self.assertRaises(ValueError):
            interval(left, right, {1})

    def test_external_compiler_fails_interval(self):
        left = {"total": 1000, "idle": 500, "processes": {
            1: {"starttime": 10, "ppid": 0, "cpu_ticks": 100, "comm": "worker"},
            2: {"starttime": 20, "ppid": 0, "cpu_ticks": 100, "comm": "cc1plus"}}}
        right = {"total": 1400, "idle": 700, "processes": {
            1: {"starttime": 10, "ppid": 0, "cpu_ticks": 120, "comm": "worker"},
            2: {"starttime": 20, "ppid": 0, "cpu_ticks": 280, "comm": "cc1plus"}}}
        result = interval(left, right, {1})
        self.assertFalse(result["pass"])
        self.assertEqual(result["unrelated_cpu"][0]["comm"], "cc1plus")


if __name__ == "__main__":
    unittest.main()
