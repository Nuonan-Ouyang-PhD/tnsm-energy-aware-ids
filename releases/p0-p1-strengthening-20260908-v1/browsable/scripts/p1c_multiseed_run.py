from __future__ import annotations
import json,time
from pathlib import Path
from scheduler.config import load_config
from scheduler.trace_io import load_npz_episode
from scheduler.isolation import Partition
from scheduler.tabular_q import TabularQPolicy
from scheduler.dqn import DQNPolicy
from scheduler.training import train_and_select

ROOT=Path(__file__).resolve().parent; CFG=load_config(ROOT/'config/scheduler_experiment_v1.json'); OUT=ROOT/'p1c_multiseed'; OUT.mkdir(exist_ok=True)
manifest=json.loads((ROOT/'policy_inputs/manifest.json').read_text())
def load_many(prefix,seeds,part):
 return [load_npz_episode(ROOT/'policy_inputs'/f'{prefix}_{s}.npz',partition=part,config=CFG.data,expected_sha256=manifest['output_sha256'][f'{prefix}_{s}.npz'],load_labels=True) for s in seeds]
def main():
 tr=load_many('train_drift',[211,223,227,229,233,239,241,251,257,263],Partition.TRAIN); va=load_many('validation_drift',[401,409,419,421,431],Partition.VALIDATION)
 rows=[]
 for algorithm,seeds in [('Tabular-Q',[1009,1013,1019,1021,1031,1033,1039,1049,1051,1061]),('DQN',[1009,1013,1019,1021,1031,1033,1039,1049,1051,1061])]:
  for seed in seeds:
   d=OUT/f'{algorithm.lower().replace("-","")}-{seed}'
   if (d/'metadata.json').exists():
    continue
   d.mkdir(exist_ok=True); p=TabularQPolicy(CFG.data,seed=seed) if algorithm=='Tabular-Q' else DQNPolicy(CFG.data,seed=seed)
   frozen,meta=train_and_select(p,train_episodes=tr,validation_episodes=va,config=CFG.data,progress_path=d/'training.jsonl'); frozen.freeze()
   if algorithm=='Tabular-Q': import numpy as np; np.save(d/'q_values.npy',frozen.q_values)
   else:
    import torch; torch.save(frozen.copy_online_state(),d/'dqn_online_state.pt')
   (d/'metadata.json').write_text(json.dumps({'algorithm':algorithm,'seed':seed,'config_sha256':CFG.sha256,'selection':meta,'test_data_accessed':False},indent=2)+'\n'); rows.append({'algorithm':algorithm,'seed':seed,'status':'PASS','selection':meta['selection']})
   (OUT/'registry.json').write_text(json.dumps(rows,indent=2)+'\n')
if __name__=='__main__': main()
