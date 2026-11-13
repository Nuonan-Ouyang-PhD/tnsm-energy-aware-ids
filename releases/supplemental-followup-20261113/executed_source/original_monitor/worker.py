"""New supplemental worker. Historical worker is used only for model/IO helpers."""
import os
os.environ['OMP_NUM_THREADS'] = '2'
os.environ['OPENBLAS_NUM_THREADS'] = '2'
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import socket
import subprocess
import threading
import time

import numpy as np
import torch
import legacy_worker as legacy
from core import ACTIONS, Observation
from cpu_guard import snapshot, interval
from frozen_selector import METHODS, load_selector
from service_loop import run_windows

HERE = Path(__file__).resolve().parent
OLD = Path('/home/pi/tnsm-reviewer-revision-v1')
legacy.ROOT = OLD
output_lock = threading.Lock()


def emit(event, **fields):
    with output_lock:
        print(json.dumps(dict(event=event, utc_epoch=time.time(), **fields), allow_nan=False), flush=True)


legacy.emit = emit


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Monitor:
    def __init__(self):
        self.stop = threading.Event()
        self.failure = None
        self.count = 0
        self.heartbeat = False
        self.thread = threading.Thread(target=self.run, daemon=True)

    def check(self):
        if self.failure:
            raise RuntimeError(self.failure)
        if self.heartbeat:
            legacy.watch_guard()

    def run(self):
        try:
            left = snapshot()
            while True:
                ending = self.stop.wait(1)
                right = snapshot()
                if right['monotonic']-left['monotonic']>1.5:
                    raise RuntimeError('continuous CPU monitor gap exceeds 1.5 seconds')
                if right['total'] > left['total']:
                    result = interval(left, right, {os.getpid()})
                    telem = legacy.telemetry()
                    emit('cpu_interval', **result, left=left, right=right,
                         final=ending, **telem)
                    self.count += 1
                    if not result['pass']:
                        raise RuntimeError('external CPU exceeds fixed 5 percent gate')
                elif not ending:
                    raise RuntimeError('CPU counters stalled')
                if self.heartbeat:
                    legacy.watch_guard()
                if shutil.disk_usage(HERE).free < 1 << 30:
                    raise RuntimeError('disk below fixed 1 GiB gate')
                if ending:
                    return
                left = right
        except BaseException as error:
            self.failure = repr(error)
            emit('monitor_failed', error=self.failure)

    def finish(self):
        self.stop.set()
        self.thread.join(5)
        if self.thread.is_alive():
            raise RuntimeError('monitor join timeout')
        self.check()


def selectors(lock):
    output = {}
    for method in METHODS:
        args = dict(medrf_p95=lock['medrf_p95'])
        if method in ('Tabular-Q', 'DQN'):
            item = lock['policies'][method]
            args.update(config_path=HERE/item['config'], config_sha=item['config_sha256'],
                        weights_path=HERE/item['weights'], weights_sha=item['weights_sha256'])
        output[method] = load_selector(method, **args)
    # Same all-state frozen decisions as on the host; no test data needed.
    for method in ('Tabular-Q','DQN'):
        decisions = []
        for n in (50,100,4000):
            for q in (0,100,101):
                for threat in (.1,.5,.9):
                    for previous in range(4):
                        decisions.append(output[method](Observation(n,q,threat,previous)))
        if decisions != lock['policies'][method]['all_state_actions']:
            raise RuntimeError('host/Pi policy parity mismatch: '+method)
    emit('policy_parity', status='PASS', states=108, policies=2)
    return output


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--stage', choices=['idle','r2'], required=True)
    parser.add_argument('--method', choices=METHODS, required=True)
    parser.add_argument('--block', type=int, required=True)
    parser.add_argument('--seconds', type=int, required=True)
    args = parser.parse_args()
    probe = args.block == 0
    if (probe and (args.stage != 'idle' or args.seconds != 18)) or (not probe and
            (not 1 <= args.block <= 10 or args.seconds != (60 if args.stage=='idle' else 500))):
        raise ValueError('segment does not match frozen design')
    lock = json.loads((HERE/'PHYSICAL_LOCK.json').read_text())
    for relative, expected in lock['runtime_sha256'].items():
        if sha(HERE/relative) != expected:
            raise RuntimeError('runtime drift: '+relative)
    serial = next(x.split(':',1)[1].strip() for x in Path('/proc/cpuinfo').read_text().splitlines() if x.startswith('Serial'))
    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    ntp = subprocess.check_output(['timedatectl','show','-p','NTPSynchronized','--value'],text=True).strip()
    governors = sorted({p.read_text().strip() for p in Path('/sys/devices/system/cpu').glob('cpu[0-9]/cpufreq/scaling_governor')})
    links = subprocess.check_output(['ip','-brief','address'],text=True)
    if serial != lock['pi_serial'] or boot != lock['boot_id'] or socket.gethostname() != 'pi4b8g' or ntp != 'yes':
        raise RuntimeError('identity/boot/NTP gate failed')
    if governors != ['performance'] or '10.10.10.31/24' not in links or '192.168.0.154/24' not in links:
        raise RuntimeError('governor/network platform drift')
    torch.set_num_threads(2)
    monitor = Monitor()
    monitor.thread.start()
    try:
        for relative, expected in lock['input_sha256'].items():
            # Probe does not read any test input or workload.
            if probe and not (relative.startswith('inputs/') and 'test_' not in relative):
                continue
            monitor.check()
            if sha(OLD/relative) != expected:
                raise RuntimeError('frozen input drift: '+relative)
        choices = selectors(lock)
        models = legacy.load_models()
        warm = np.load(OLD/'inputs/warm_X.npy',allow_pickle=False)
        for action in legacy.Action:
            for _ in range(20):
                monitor.check()
                legacy.predict(models, action, np.array(warm[:100],copy=True))
        initial = legacy.wait_cool()
        monitor.check()
        x = warm if probe else np.load(OLD/'inputs/test_X.npy',mmap_mode='r',allow_pickle=False)
        if probe:
            arrivals = np.array([50,100,4000]*6)
            offsets = np.concatenate(([0],np.cumsum(arrivals)))
            indices = np.arange(int(offsets[-1])) % 100
        elif args.stage == 'r2':
            prefix = OLD/f'r2_workloads/block_{args.block:02d}'
            arrivals = np.load(str(prefix)+'.arrivals.npy',allow_pickle=False)
            offsets = np.load(str(prefix)+'.offsets.npy',allow_pickle=False)
            indices = np.load(str(prefix)+'.indices.npy',allow_pickle=False)
            if arrivals.shape != (500,):
                raise RuntimeError('expected 500 windows')
        start = legacy.start_barrier(args.stage,args.method,args.seconds,
            dict(cpu_serial=serial,boot_id=boot,hostname=socket.gethostname(),links=links,
                 physical_lock_sha256=sha(HERE/'PHYSICAL_LOCK.json'),probe=probe),initial)
        monitor.heartbeat = True
        def predict(action, rows):
            batch = np.array(x[rows],copy=True)
            if action is not None:
                return legacy.predict(models,legacy.Action(ACTIONS[action]),batch), {}
            probs, light, med, deferred = legacy.cascade(models,batch)
            return probs, dict(lightlr_probabilities=light.tolist(),deferred_mask=deferred.tolist(),
                               deferred_medrf_probabilities=med[deferred].tolist())
        window_number = [0]
        def select(view):
            method = METHODS[window_number[0]//3] if probe else args.method
            return choices[method](view)
        def outcome(item):
            window_number[0] += 1
            # Flatten fields for the unchanged recorder's post-hoc accounting.
            batches = item['batches']
            item.update(completed_source_indices=[v for b in batches for v in b['source_indices']],
                final_probabilities=[v for b in batches for v in b['probabilities']],
                queue_after=item['backlog_rows'], deadline_overrun_seconds=max(0.,item['completion_seconds']-1),
                encoded_state={'index':item['state_index']})
            emit('outcome', **item)
            if probe:
                emit('idle_sample',window_index=item['window'],probe_only=True,detector_inference_executed=True)
        if args.stage == 'idle' and not probe:
            for i in range(args.seconds):
                monitor.check()
                time.sleep(max(0,start+i-time.monotonic()))
                emit('idle_sample',window_index=i,detector_inference_executed=False,**legacy.telemetry())
        else:
            backlog = run_windows(arrivals,indices,offsets,select=select,predict=predict,
                clock=time.monotonic,sleep=time.sleep,guard=monitor.check,emit=outcome,start=start)
            emit('r2_final_backlog',rows=len(backlog['backlog_source_indices']),
                 source_indices=backlog['backlog_source_indices'],arrival_windows=backlog['backlog_arrival_windows'])
        time.sleep(max(0,start+args.seconds-time.monotonic()))
        monitor.finish()
        emit('complete',stage=args.stage,method=args.method,seconds=args.seconds,
             cpu_intervals=monitor.count,probe_only=probe)
    finally:
        monitor.stop.set()
        monitor.thread.join(5)


if __name__ == '__main__':
    try:
        main()
    except BaseException as error:
        emit('failed',status='INVALID_RETAIN_NO_RETRY',error=repr(error))
        raise
