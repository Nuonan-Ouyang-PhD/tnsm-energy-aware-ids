"""Sequential measured profiles; fail closed, preserve partial data, no retry."""
import fcntl
import hashlib
import json
import math
import os
import random
import subprocess
import threading
import time
from datetime import datetime,timezone
from pathlib import Path
import hid
from measurement import request,decode,integrate

ROOT=Path(__file__).resolve().parent
REMOTE='/home/pi/tnsm-physical-static-v1'
PYTHON='/home/pi/tnsm-campaign-v1/venv/bin/python'
SSH=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8','-o','ServerAliveInterval=2','-o','ServerAliveCountMax=2','pi@pi4b8g.local']
NAMES=['TinyDT','LightLR','MedRF','HeavyMLP']


def save(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False)


def event(name,**detail):
    item={'utc':datetime.now(timezone.utc).isoformat(),'event':name,**detail}
    with (ROOT/'execution/events.jsonl').open('a') as f:f.write(json.dumps(item)+'\n')
    print(json.dumps(item),flush=True)


def clock_check():
    checks=[]
    command="python3 -u -c 'import sys,time;print(\"ready\",flush=True);[(print(time.time(),flush=True)) for line in sys.stdin]'"
    p=subprocess.Popen(SSH+[command],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,bufsize=1)
    try:
        import select
        if not select.select([p.stdout],[],[],15)[0]:raise RuntimeError('clock handshake timeout')
        assert p.stdout.readline().strip()=='ready'
        for _ in range(5):
            t0=time.time();p.stdin.write('ping\n');p.stdin.flush()
            if not select.select([p.stdout],[],[],3)[0]:raise RuntimeError('clock response timeout')
            remote=float(p.stdout.readline());t1=time.time()
            checks.append({'host_send':t0,'host_receive':t1,'remote_epoch':remote,
                'offset_interval':[remote-t1,remote-t0],'roundtrip_seconds':t1-t0})
    finally:
        p.stdin.close()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.terminate();p.wait(timeout=5)
    best=min(checks,key=lambda x:x['roundtrip_seconds'])
    assert max(map(abs,best['offset_interval']))<=.25,('clock uncertainty too large',checks)
    return checks


def run_profile(run,device,baseline):
    folder=ROOT/'execution'/run['run_id'];folder.mkdir()
    save(folder/'clock_check.json',clock_check())
    command=SSH+[f'{PYTHON} -B -u {REMOTE}/profile_worker.py --model {run["model"]} --seconds 1800']
    save(folder/'command.json',{'argv':command})
    log=(folder/'pi_telemetry.jsonl').open('x');err=(folder/'pi_stderr.log').open('x')
    process=subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=err,text=True,bufsize=1)
    state={'ready':None,'error':None,'last':None,'windows':[],'complete':None};done=threading.Event()
    def read_remote():
        try:
            for line in process.stdout:
                log.write(line);log.flush();item=json.loads(line)
                if item['event']=='ready':state['ready']=item
                elif item['event']=='window':state['last']=item;state['windows'].append(item)
                elif item['event']=='failed':state['error']=item
                elif item['event']=='complete':state['complete']=item
        except BaseException as error:state['error']=repr(error)
        finally:done.set()
    reader=threading.Thread(target=read_remote,daemon=True);reader.start()
    heartbeat_stop=threading.Event()
    samples=[];started=False
    try:
        deadline=time.monotonic()+1900
        while state['ready'] is None:
            if state['error'] or done.is_set():raise RuntimeError(('remote preparation failed',state['error']))
            if time.monotonic()>deadline:raise RuntimeError('ready timeout')
            time.sleep(.2)
        # Read and validate a fresh ADC frame before declaring a formal start.
        device.write(request(250));pre_raw=bytes(device.read(64,1000));decode(pre_raw,250,baseline)
        start=time.time()+5;mono=time.monotonic()+start-time.time()
        save(folder/'run.json',{**run,'start_utc_epoch':start,'seconds':1800,'baseline_volts':baseline,'prestart_adc_hex':pre_raw.hex()})
        process.stdin.write(json.dumps({'start_utc':start})+'\n');process.stdin.flush();started=True
        def heartbeats():
            while not heartbeat_stop.is_set():
                try:process.stdin.write('heartbeat\n');process.stdin.flush()
                except (BrokenPipeError,ValueError):return
                heartbeat_stop.wait(1)
        threading.Thread(target=heartbeats,daemon=True).start()
        event('profile_scheduled',**run,start_utc_epoch=start,pid=process.pid)
        with (folder/'power.jsonl').open('x') as powerlog:
            for index in range(1801):
                target=mono+index;delay=target-time.monotonic()
                if delay>0:time.sleep(delay)
                if time.monotonic()-target>.25:raise RuntimeError('meter sampling deadline missed')
                if state['error']:raise RuntimeError(('Pi failed',state['error']))
                if index>2 and (state['last'] is None or state['last']['index']<index-2):raise RuntimeError('Pi telemetry stale')
                begin=time.monotonic();utc=time.time();device.write(request(index))
                raw=bytes(device.read(64,1000));end=time.monotonic()
                if end-begin>.25:raise RuntimeError('meter roundtrip too slow')
                values=decode(raw,index,baseline)
                sample={'index':index,'utc_epoch_request':utc,'request_monotonic':begin,'receive_monotonic':end,
                    'sample_monotonic':(begin+end)/2,'roundtrip_seconds':end-begin,'raw_hex':raw.hex(),**values}
                samples.append(sample);powerlog.write(json.dumps(sample)+'\n');powerlog.flush()
                if index%60==0:event('profile_progress',run_id=run['run_id'],seconds=index,volts=values['volts'],watts=values['watts'])
        exit_code=process.wait(timeout=10);reader.join(timeout=3)
        assert exit_code==0 and state['complete'] and not state['error']
        windows=state['windows'];assert len(windows)==1800
        assert [w['index'] for w in windows]==list(range(1800))
        assert all(w['rows']==(0 if run['model']=='idle' else 100) for w in windows)
        assert all(0<b['utc_epoch']-a['utc_epoch']<=1.5 for a,b in zip(windows,windows[1:]))
        energy,duration=integrate(samples)
        summary={**run,'status':'PASS','power_samples':len(samples),'telemetry_windows':len(windows),
            'observed_duration_seconds':duration,'energy_joules':energy,'mean_watts':energy/duration,
            'voltage_min':min(s['volts'] for s in samples),'voltage_max':max(s['volts'] for s in samples),
            'maximum_temperature_c':max(w['temperature_c'] for w in windows),
            'scope':'instrumented idle or encoded-input static profile; uncalibrated meter; user-accepted above-label supply'}
        save(folder/'summary.json',summary);event('profile_complete',**summary);return summary
    except BaseException as error:
        save(folder/'failure.json',{'status':'INVALID','reason':repr(error),'samples_retained':len(samples),'start_sent':started})
        raise
    finally:
        heartbeat_stop.set()
        try:process.stdin.close()
        except (BrokenPipeError,ValueError):pass
        try:process.wait(timeout=8)
        except subprocess.TimeoutExpired:process.terminate();process.wait(timeout=5)
        reader.join(timeout=3);log.close();err.close()


def main():
    lock=(ROOT/'controller.lock').open('a');fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
    execution=ROOT/'execution';execution.mkdir()
    rng=random.Random(20260906);schedule=[]
    for repetition in range(1,4):
        order=NAMES.copy();rng.shuffle(order)
        for n,model in enumerate(['idle']+order):schedule.append({'run_id':f'r{repetition}-{n}-{model}','repetition':repetition,'model':model})
    save(execution/'schedule.json',{'seed':20260906,'runs':schedule})
    bound={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in ROOT.iterdir() if p.is_file() and p.suffix in ('.py','.md','.json')}
    save(execution/'identity.json',{'source_hashes':bound,'pid':os.getpid(),'permission':'all experiments; explicit accepted above-label supply',
         'independent_meter_calibration':False,'voltage_gate_superseded_by_user':True})
    device=hid.device();summaries=[]
    try:
        device.open(0x5fc9,0x0063,'075356');device.write(request(249));raw=bytes(device.read(64,1000))
        baseline=decode(raw,249)['volts'];save(execution/'meter_start.json',{'raw_hex':raw.hex(),'baseline_volts':baseline})
        for run in schedule:summaries.append(run_profile(run,device,baseline))
        save(execution/'summary.json',{'status':'PASS','completed_profiles':15,'profiles':summaries})
        event('static_profiles_complete',profiles=15,remaining='adaptive policy training/replay and 40 paired physical runs')
    except BaseException as error:
        save(execution/'failure.json',{'status':'STOPPED','reason':repr(error),'completed_profiles':len(summaries),'automatic_retry':False})
        event('campaign_stopped',reason=repr(error));raise
    finally:device.close()


if __name__=='__main__':main()
