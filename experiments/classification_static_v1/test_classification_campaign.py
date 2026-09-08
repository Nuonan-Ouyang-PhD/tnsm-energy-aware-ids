import tempfile
import unittest
from pathlib import Path
import numpy as np
import classification_campaign as c
from static_replay import trace_indices, PHASES


class CampaignTests(unittest.TestCase):
    def test_device_groups_do_not_cross_splits(self):
        rows=[{'shard_id':str(i)+'-'+str(j),'source_file':f'device{i}/capture{j}.csv'} for i in range(9) for j in range(3)]
        mapping,uncovered=c.assign_shards('n_baiot',rows)
        self.assertEqual(len(set(mapping.values())),3)
        for i in range(9):self.assertEqual(len({mapping[str(i)+'-'+str(j)] for j in range(3)}),1)
        self.assertEqual([list(mapping.values()).count(s)//3 for s in c.SPLITS],[5,2,2])
        self.assertEqual(mapping,c.assign_shards('n_baiot',list(reversed(rows)))[0])

    def test_capture_group_split_and_singleton_coverage(self):
        rows=[{'shard_id':str(i),'source_file':f'CSV/common/{i}.csv'} for i in range(10)]+[{'shard_id':'rare','source_file':'CSV/rare/1.csv'}]
        mapping,uncovered=c.assign_shards('ciciot2023',rows)
        self.assertEqual(uncovered,['rare']);self.assertEqual(mapping['rare'],'train')
        self.assertEqual([sum(v==s for k,v in mapping.items() if k!='rare') for s in c.SPLITS],[6,2,2])
        self.assertEqual(mapping,c.assign_shards('ciciot2023',list(reversed(rows)))[0])

    def test_numeric_and_train_only_preprocessing(self):
        self.assertEqual(c.numeric('T'),1);self.assertEqual(c.numeric('false'),0)
        self.assertTrue(np.isnan(c.numeric('Infinity')));self.assertTrue(np.isnan(c.numeric('-')))
        pools={'train':{'numeric':np.array([[1.],[3.],[np.nan]]),'categorical':np.empty((3,0),dtype=object)},
               'validation':{'numeric':np.array([[1000.]]),'categorical':np.empty((1,0),dtype=object)},
               'test':{'numeric':np.array([[np.nan]]),'categorical':np.empty((1,0),dtype=object)}}
        with tempfile.TemporaryDirectory() as temp:
            x=c.encode(pools,Path(temp))
        self.assertAlmostEqual(float(x['test'][0,0]),0.)
        self.assertAlmostEqual(float(x['train'].mean()),0.,places=6)
        self.assertGreater(float(x['validation'][0,0]),100)

    def test_metric_cache_uses_fixed_threshold(self):
        m=c.metrics(np.array([0,1,0,1]),np.array([.1,.9,.8,.2]))
        self.assertEqual(m['confusion_matrix'],[[1,1],[1,1]])
        self.assertEqual(m['accuracy'],.5)

    def test_controlled_drift_counts_and_determinism(self):
        labels=np.array([0]*100+[1]*100)
        indices,meta=trace_indices(labels,'drift',11)
        self.assertEqual(len(indices),50000)
        self.assertTrue(np.array_equal(indices,trace_indices(labels,'drift',11)[0]))
        offset=0
        for windows,ratio in PHASES:
            block=labels[indices[offset:offset+windows*100]].reshape(windows,100)
            self.assertTrue((block.sum(axis=1)==round(100*ratio)).all());offset+=windows*100
        self.assertTrue(all(meta['replacement_by_label'].values()))


if __name__=='__main__':unittest.main()
