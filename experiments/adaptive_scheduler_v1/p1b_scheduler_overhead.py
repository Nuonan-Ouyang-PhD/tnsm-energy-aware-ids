from __future__ import annotations
import json, platform, resource, time
from pathlib import Path
import numpy as np

from scheduler.state import EncodedState, Action
from scheduler.tabular_q import TabularQPolicy
from scheduler.dqn import DQNPolicy

ROOT = Path(__file__).resolve().parent
CFG = json.loads((ROOT/'config/scheduler_experiment_v1.json').read_text())
RUNTIME = Path('/Users/nuonanouyang/Library/Application Support/Codex/TNSM-adaptive-runtime-v1/software')
OUT = ROOT/'p1b_scheduler_overhead'

def states_from_log(path: Path, limit=10000):
    vals=[]
    for line in path.read_text().splitlines():
        try:
            x=json.loads(line)
            if x.get('event_type')=='window_decision': vals.append(int(x['encoded_state']['index']))
        except Exception: pass
        if len(vals)>=limit: break
    if not vals: vals=list(range(324))
    return np.asarray(vals,dtype=np.int64)

def main():
    OUT.mkdir(exist_ok=True)
    states={
      'exhaustive_324':np.arange(324,dtype=np.int64),
      'observed_support':states_from_log(RUNTIME/'test-tabular/windows.jsonl',10000),
    }
    tq=TabularQPolicy(CFG); tq.q_values=np.load(RUNTIME/'tabular-frozen/q_values.npy'); tq.freeze()
    dq=DQNPolicy(CFG); import torch; dq.online.load_state_dict(torch.load(RUNTIME/'dqn-frozen/dqn_online_state.pt',map_location='cpu')); dq.target.load_state_dict(dq.online.state_dict()); dq.freeze()
    methods={'Static-LightLR':lambda s:Action.LIGHT_LR,'Tabular-Q':lambda s:tq.select_action(EncodedState(int(s),0,0,0,0,0)),'DQN':lambda s:dq.select_action(EncodedState(int(s),0,0,0,0,0))}
    # CFSM is represented by the fixed action path only for timing isolation; no energy inference.
    methods['CFSM']=lambda s:Action.MED_RF
    rng=np.random.default_rng(20260908); blocks=[]
    for block in range(30):
      order=list(methods); rng.shuffle(order)
      for stream,arr in states.items():
       for method in order:
        seq=np.resize(arr,10000); 
        for s in seq[:1000]: methods[method](int(s))
        t=np.empty(10000,dtype=np.int64); start=time.perf_counter_ns()
        for i,s in enumerate(seq):
          a=time.perf_counter_ns(); methods[method](int(s)); t[i]=time.perf_counter_ns()-a
        np.save(OUT/f'block-{block+1:02d}-{stream}-{method}.npy',t)
        blocks.append({'block':block+1,'stream':stream,'method':method,'n':10000,'mean_ns':float(t.mean()),'median_ns':float(np.median(t)),'p95_ns':float(np.percentile(t,95)),'wall_ns':time.perf_counter_ns()-start})
    (OUT/'registry.json').write_text(json.dumps({'host':platform.platform(),'python':platform.python_version(),'blocks':blocks},indent=2))
    (OUT/'README.md').write_text('Isolated scheduler overhead microbenchmark. Timing covers encoded state to policy action only; no joule or power inference.\n')
if __name__=='__main__': main()
