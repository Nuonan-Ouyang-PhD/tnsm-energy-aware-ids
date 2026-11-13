import tempfile
import unittest
from pathlib import Path
import numpy as np
from core import Observation
from train_formal import encode, prepare


class TrainingTests(unittest.TestCase):
    def test_projection_cardinalities(self):
        views=[Observation(n,q,h,a) for n in (50,100,4000) for q in (0,50,4000)
               for h in (.1,.5,.9) for a in range(4)]
        for variant,count in (("full",108),("minus_arrival",36),("minus_threat",36),("minus_previous_action",27)):
            self.assertEqual(set(encode(v,variant) for v in views),set(range(count)))

    def test_workload_size_and_confusion(self):
        labels=np.array([0,1]*50)
        probs=np.repeat(labels[:,None],4,axis=1).astype(np.float32)
        with tempfile.TemporaryDirectory() as d:
            data=prepare((probs,labels,"synthetic"),211,[(i+1,.001) for i in range(4)],Path(d))
        self.assertEqual(len(data["arrivals"]),500)
        self.assertEqual(int(data["arrivals"].sum()),627500)
        self.assertEqual(set(data["arrivals"]),{50,100,4000})
        self.assertTrue(np.all(data["confusion"][:,:,1:3]==0))
        self.assertTrue(np.all(data["confusion"].sum(axis=2)==data["arrivals"][:,None]))


if __name__=="__main__":unittest.main()
