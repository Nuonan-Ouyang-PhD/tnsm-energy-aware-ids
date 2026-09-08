"""Sequential software stages under the user's broad continuation authority."""
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime,timezone
from pathlib import Path

HERE=Path(__file__).resolve().parent
RUN=HERE/'execution'


def event(name,**details):
    value={'time':datetime.now(timezone.utc).isoformat(),'event':name,**details}
    with (RUN/'events.jsonl').open('a') as f:f.write(json.dumps(value)+'\n')
    print(json.dumps(value),flush=True)


def stage(name,command):
    with (RUN/(name+'.log')).open('x') as log:
        p=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,
                           env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1','OMP_NUM_THREADS':'2','OPENBLAS_NUM_THREADS':'2'})
        event('stage_started',stage=name,pid=p.pid,command=command)
        code=p.wait()
    event('stage_finished',stage=name,exit_code=code)
    if code:raise SystemExit(code)


def main():
    RUN.mkdir()
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in HERE.iterdir() if p.suffix in ('.py','.md')}
    with (RUN/'source_binding.json').open('x') as f:json.dump({'source_hashes':hashes,'user_authorization':'继续 你直接完成全部所有的实验不需要经过我'},f,ensure_ascii=False,indent=2)
    stage('tests',[sys.executable,'-B','-m','unittest','discover','-s',str(HERE),'-p','test_classification_campaign.py'])
    stage('dependencies',[sys.executable,'-m','pip','freeze'])
    event('waiting_for_materialization_publication')
    completion=HERE.parent/'materialization_run_v2/completion.json'
    while not completion.exists():time.sleep(10)
    value=json.loads(completion.read_bytes())
    if value['exit_code']!=0:
        event('blocked_materialization_failed',result=value);raise SystemExit(2)
    event('materialization_dependency_passed',result=value)
    stage('classification',[sys.executable,'-B','-u',str(HERE/'classification_campaign.py')])
    stage('static_replay',[sys.executable,'-B','-u',str(HERE/'static_replay.py')])
    event('software_classifier_and_static_replay_complete',remaining=['adaptive policy state/reward/cost specification','external power meter interface','Pi latency and physical power evaluation'])


if __name__=='__main__':main()
