"""Bounded Pi workload; loss of coordinator heartbeats stops inference."""
import os
os.environ['OMP_NUM_THREADS']='2';os.environ['OPENBLAS_NUM_THREADS']='2'
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT=Path(__file__).resolve().parent
last_heartbeat=time.monotonic()
control_closed=threading.Event()
NAMES=['TinyDT','LightLR','MedRF','HeavyMLP']


def emit(event,**fields):
    print(json.dumps({'event':event,'utc_epoch':time.time(),**fields}),flush=True)


def watch_control():
    global last_heartbeat
    for line in sys.stdin:
        if line.strip()=='heartbeat':last_heartbeat=time.monotonic()
        else:break
    control_closed.set()


def watch_guard():
    if control_closed.is_set() or time.monotonic()-last_heartbeat>5:
        raise RuntimeError('coordinator heartbeat lost')


def telemetry():
    temp=int(Path('/sys/class/thermal/thermal_zone0/temp').read_text())/1000
    throttled=subprocess.check_output(['vcgencmd','get_throttled'],text=True).strip()
    if temp>=70 or throttled!='throttled=0x0':raise RuntimeError(f'thermal/throttle guard: {temp}, {throttled}')
    return {'temperature_c':temp,'throttled':throttled,'load_1m':os.getloadavg()[0],
            'frequencies_khz':[int(p.read_text()) for p in sorted(Path('/sys/devices/system/cpu').glob('cpu[0-9]/cpufreq/scaling_cur_freq'))]}


def main():
    global last_heartbeat
    parser=argparse.ArgumentParser();parser.add_argument('--model',choices=['idle']+NAMES,required=True)
    parser.add_argument('--seconds',type=int,default=1800);args=parser.parse_args()
    assert args.seconds==1800
    assert 'Raspberry Pi 4 Model B' in Path('/proc/device-tree/model').read_text()
    assert shutil.disk_usage(ROOT).free>=1073741824
    assert subprocess.check_output(['timedatectl','show','-p','NTPSynchronized','--value'],text=True).strip()=='yes'
    manifest=json.loads((ROOT/'inputs_manifest.json').read_bytes())
    for relative,h in manifest.items():assert hashlib.sha256((ROOT/relative).read_bytes()).hexdigest()==h,relative
    import fcntl
    lock=(ROOT/'worker.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    import joblib
    import numpy as np
    import torch
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    x=np.load(ROOT/'inputs/train_X.npy');reference=np.load(ROOT/'inputs/train_predictions.npy')
    assert len(x)==10000 and reference.shape==(10000,4)
    models={name:joblib.load(ROOT/'inputs'/(name+'.joblib')) for name in NAMES[:-1]}
    state=torch.load(ROOT/'inputs/HeavyMLP.pt',map_location='cpu',weights_only=True)
    net=torch.nn.Sequential(torch.nn.Linear(state['input_dim'],64),torch.nn.ReLU(),torch.nn.Dropout(.2),
        torch.nn.Linear(64,32),torch.nn.ReLU(),torch.nn.Dropout(.2),torch.nn.Linear(32,16),torch.nn.ReLU(),
        torch.nn.Dropout(.2),torch.nn.Linear(16,1))
    net.load_state_dict(state['state_dict']);net.eval();models['HeavyMLP']=net
    def predict(name,batch):
        if name!='HeavyMLP':return models[name].predict_proba(batch)[:,1]
        with torch.no_grad():return torch.sigmoid(net(torch.from_numpy(batch))).numpy().ravel()
    for n,name in enumerate(NAMES):
        got=np.concatenate([predict(name,x[k:k+100]) for k in range(0,len(x),100)])
        assert np.max(np.abs(got-reference[:,n]))<=1e-4
        assert np.array_equal(got>=.5,reference[:,n]>=.5)
        for _ in range(20):predict(name,x[:100])
    deadline=time.monotonic()+1800
    while True:
        t=telemetry()
        if t['temperature_c']<=45:break
        if time.monotonic()>deadline:raise RuntimeError('cooldown timeout')
        emit('cooldown',**t);time.sleep(5)
    governors={p.read_text().strip() for p in Path('/sys/devices/system/cpu').glob('cpu[0-9]/cpufreq/scaling_governor')}
    assert len(governors)==1
    emit('ready',model=args.model,governors=sorted(governors),**t)
    command=json.loads(sys.stdin.readline());start_utc=command['start_utc']
    assert 1<start_utc-time.time()<30
    start_mono=time.monotonic()+start_utc-time.time()
    last_heartbeat=time.monotonic();threading.Thread(target=watch_control,daemon=True).start()
    for index in range(args.seconds):
        watch_guard();delay=start_mono+index-time.monotonic()
        if delay>0:time.sleep(delay)
        watch_guard();lateness=time.monotonic()-(start_mono+index)
        if lateness>.25:raise RuntimeError('Pi workload deadline missed')
        offset=(index*100)%len(x);begin=time.perf_counter_ns()
        probabilities=[] if args.model=='idle' else predict(args.model,x[offset:offset+100]).tolist()
        elapsed=time.perf_counter_ns()-begin
        if elapsed>=250000000:raise RuntimeError('inference batch over budget')
        emit('window',index=index,model=args.model,source_offset=offset,rows=len(probabilities),
             probabilities=probabilities,inference_ns=elapsed,lateness_seconds=lateness,**telemetry())
    delay=start_mono+args.seconds-time.monotonic()
    if delay>0:time.sleep(delay)
    watch_guard();emit('complete',windows=args.seconds,model=args.model,**telemetry())


if __name__=='__main__':
    try:main()
    except BaseException as error:
        emit('failed',reason=repr(error));raise
