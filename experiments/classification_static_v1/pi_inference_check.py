"""Pi CPU inference parity/readiness only; no meter or energy claim."""
import os
os.environ['OMP_NUM_THREADS']='2'
os.environ['OPENBLAS_NUM_THREADS']='2'
import hashlib
import json
import subprocess
import time
from pathlib import Path
import joblib
import numpy as np
import torch

ROOT=Path(__file__).resolve().parent
NAMES=['TinyDT','LightLR','MedRF','HeavyMLP']


def temperature():return float(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000


def guard():
    status=subprocess.check_output(['vcgencmd','get_throttled'],text=True).strip()
    if status!='throttled=0x0' or temperature()>60:
        raise RuntimeError('Pi readiness failed: '+status+' temperature='+str(temperature()))


def main():
    assert 'Raspberry Pi 4 Model B' in Path('/proc/device-tree/model').read_text()
    guard();torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    expected=json.loads((ROOT/'inputs_manifest.json').read_text())
    for relative,h in expected.items():
        p=ROOT/relative;assert hashlib.sha256(p.read_bytes()).hexdigest()==h,relative
    report={'scope':'encoded in-memory inference parity and timing readiness; not whole-device power or end-to-end IDS latency',
            'meter_used':False,'paper_energy_result':False,'temperature_start':temperature(),
            'torch':torch.__version__,'numpy':np.__version__,'datasets':{}}
    for dataset in ('ton_iot','ciciot2023','n_baiot'):
        folder=ROOT/'inputs'/dataset
        x=np.load(folder/'check_X.npy',allow_pickle=False);reference=np.load(folder/'check_predictions.npy',allow_pickle=False)
        result={}
        for n,name in enumerate(NAMES):
            guard()
            if name!='HeavyMLP':
                model=joblib.load(folder/(name+'.joblib'))
                if hasattr(model,'n_jobs'):model.n_jobs=2
                predict=lambda batch:model.predict_proba(batch)[:,1]
            else:
                state=torch.load(folder/'HeavyMLP.pt',map_location='cpu',weights_only=True)
                model=torch.nn.Sequential(torch.nn.Linear(state['input_dim'],64),torch.nn.ReLU(),torch.nn.Dropout(.2),
                    torch.nn.Linear(64,32),torch.nn.ReLU(),torch.nn.Dropout(.2),torch.nn.Linear(32,16),torch.nn.ReLU(),
                    torch.nn.Dropout(.2),torch.nn.Linear(16,1))
                model.load_state_dict(state['state_dict']);model.eval()
                def predict(batch):
                    with torch.no_grad():return torch.sigmoid(model(torch.from_numpy(batch))).numpy().ravel()
            observed=np.concatenate([predict(x[b:b+100]) for b in range(0,len(x),100)])
            max_abs=float(np.max(np.abs(observed-reference[:,n])))
            disagreement=int(np.count_nonzero((observed>=.5)!=(reference[:,n]>=.5)))
            assert max_abs<=1e-4 and disagreement==0,(dataset,name,max_abs,disagreement)
            for _ in range(20):predict(x[:100])
            duration=[]
            for step in range(1000):
                if step%100==0:guard()
                begin=time.perf_counter_ns();predict(x[(step*100)%(len(x)-100+1):(step*100)%(len(x)-100+1)+100]);duration.append(time.perf_counter_ns()-begin)
            result[name]={'rows_checked':len(x),'maximum_probability_error':max_abs,'label_disagreements':disagreement,
                'batch_size':100,'timing_loops':1000,'warmup_loops':20,'batch_ms_median':float(np.median(duration)/1e6),
                'batch_ms_p95':float(np.quantile(duration,.95)/1e6),'durations_ns':duration,'temperature_after':temperature()}
            print(json.dumps({'dataset':dataset,'model':name,'max_abs_error':max_abs,'disagreements':disagreement,'median_batch_ms':result[name]['batch_ms_median']}),flush=True)
        report['datasets'][dataset]=result
    guard();report['temperature_end']=temperature();report['status']='PASS'
    with (ROOT/'pi_inference_report.json').open('x') as f:json.dump(report,f,indent=2)


if __name__=='__main__':main()
