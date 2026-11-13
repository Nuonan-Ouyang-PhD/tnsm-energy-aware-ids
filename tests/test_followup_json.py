"""No training, hardware or file mutation: frozen derived-table checks only."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/scheduler_followup'))
from reanalyse_json import recompute


class FollowupJSONTests(unittest.TestCase):
    def setUp(self):
        self.rows=json.loads((ROOT/'releases/supplemental-followup-20261113/analysis/RUN_METRICS.json').read_text())

    def test_all_sets_and_pairs(self):
        result=recompute(self.rows)
        self.assertEqual(len(result),540)
        self.assertEqual({x['n'] for x in result},{8,9,10})
        self.assertEqual({x['set'] for x in result},{'all_valid','exclude_block1','exclude_all_recovered'})

    def test_missing_run_rejected(self):
        with self.assertRaises(ValueError):recompute(self.rows[:-1])

    def test_duplicate_run_rejected(self):
        rows=copy.deepcopy(self.rows);rows[-1]=rows[0]
        with self.assertRaises(ValueError):recompute(rows)


if __name__=='__main__':unittest.main()
