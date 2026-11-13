"""Synthetic compatibility/isolation tests, not scientific policy training."""
import json
from pathlib import Path
import sys
import unittest

import torch

from core import Observation, STATE_COUNT

ORIGINAL = Path(__file__).resolve().parents[1] / "adaptive_scheduler_v1"
sys.path.insert(0, str(ORIGINAL))
from scheduler.dqn import DQNPolicy, DQNTransition
from scheduler.isolation import Partition
from scheduler.state import ACTION_ORDER
from scheduler.tabular_q import PolicyStateError


class DQNCompatibilityTests(unittest.TestCase):
    def test_new_state_training_freeze_and_all_state_evaluation(self):
        torch.set_num_threads(1)
        config = json.loads((ORIGINAL / "config/scheduler_experiment_v1.json").read_text())
        config["online_state"]["discrete_state_cardinality"] = STATE_COUNT
        policy = DQNPolicy(config, seed=2003)
        before = policy.copy_online_state()
        for i in range(400):
            state = Observation((50, 100, 4000)[i % 3], (0, 50, 4000)[(i//3) % 3], .5, i % 4).index
            transition = DQNTransition(state, ACTION_ORDER[i % 4], .1, state, False, Partition.TRAIN)
            policy.observe(transition)
            policy.optimize()
        self.assertEqual(policy.optimizer_steps, 81)
        self.assertTrue(any(not torch.equal(before[k], v) for k, v in policy.online.state_dict().items()))
        policy.freeze()
        frozen = policy.copy_online_state()
        for state in range(STATE_COUNT):
            self.assertIn(policy.select_action(state, training=False), ACTION_ORDER)
        self.assertTrue(all(torch.equal(frozen[k], v) for k, v in policy.online.state_dict().items()))
        with self.assertRaises(PolicyStateError):
            policy.optimize()
        with self.assertRaises(PolicyStateError):
            policy.observe(transition)


if __name__ == "__main__":
    unittest.main()
