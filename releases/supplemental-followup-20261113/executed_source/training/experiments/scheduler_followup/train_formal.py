"""Locked train/validation-only follow-up. Never imports a physical runner."""
import copy
import gzip
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import torch
from core import ACTIONS, Observation, reward
from pilot import read_pool

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OLD = ROOT / "experiments/adaptive_scheduler_v1"
sys.path.insert(0, str(OLD))
from scheduler.dqn import DQNPolicy, DQNTransition
from scheduler.tabular_q import TabularQPolicy, TabularUpdate
from scheduler.state import ACTION_ORDER
from scheduler.isolation import Partition

OUT = ROOT / "supplemental_scheduler_20261112/formal_training_01"
SEEDS = (2003, 2011, 2017, 2027, 2029)
VARIANTS = ("full", "minus_arrival", "minus_threat", "minus_previous_action")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    with path.open("x") as f:
        json.dump(value, f, indent=2, allow_nan=False)


def encode(view, variant):
    index = view.index
    values = (index//36, (index//12)%3, (index//4)%3, index%4)
    omitted = {"full": -1, "minus_arrival": 0, "minus_threat": 2, "minus_previous_action": 3}[variant]
    result = 0
    for i, (v, dim) in enumerate(zip(values, (3, 3, 3, 4))):
        if i != omitted:
            result = result*dim+v
    return result


def prepare(pool, seed, costs, directory):
    probs, labels, _ = pool
    rng = np.random.default_rng(seed)
    cells = [(n,p) for n in (50,100,4000) for p in (.1,.5,.9)]
    rng.shuffle(cells)
    schedule = [cell for cell in cells for _ in range(50)] + [(100,.1)]*50
    classes = [np.flatnonzero(labels == k) for k in (0,1)]
    arrivals, rewards, threats, counts, indices = [], [], [], [], []
    low, high = min(x[0] for x in costs), max(x[0] for x in costs)
    for n, prevalence in schedule:
        positive = int(round(n*prevalence))
        ids = np.concatenate([rng.choice(classes[0],n-positive),rng.choice(classes[1],positive)])
        rng.shuffle(ids)
        y, p = labels[ids], probs[ids]
        rw, cf = [], []
        for a in range(4):
            pred = p[:,a] >= .5
            tn=int(np.sum((y==0)&~pred));fp=int(np.sum((y==0)&pred))
            fn=int(np.sum((y==1)&~pred));tp=int(np.sum((y==1)&pred))
            ba=.5*(tn/(tn+fp)+tp/(tp+fn))
            completion=((n+99)//100)*costs[a][1]
            if completion>1:
                raise RuntimeError("zero-queue simulator assumption failed; no silent workload change")
            value,_=reward(balanced_accuracy=ba,normalized_power=(costs[a][0]-low)/(high-low),
                           completion_seconds=completion,backlog_rows=0,work_rows=n)
            rw.append(value);cf.append((tn,fp,fn,tp))
        arrivals.append(n);rewards.append(rw);threats.append(p.mean(axis=0));counts.append(cf);indices.append(ids)
    data={"arrivals":np.array(arrivals),"rewards":np.array(rewards),
          "threats":np.array(threats),"confusion":np.array(counts),
          "source_indices":np.concatenate(indices)}
    with (directory/f"trace_{seed}.npz").open("xb") as f:np.savez_compressed(f,**data)
    return data


def evaluate(policy, variant, traces):
    results=[]
    for data in traces:
        threat,previous=.5,0;total=0.;occupancy=np.zeros(4,dtype=int);confusion=np.zeros(4,dtype=np.int64)
        for w,n in enumerate(data["arrivals"]):
            state=encode(Observation(int(n),0,threat,previous),variant)
            action=policy.select_action(state,training=False);a=ACTION_ORDER.index(action)
            total+=float(data["rewards"][w,a]);occupancy[a]+=1;confusion+=data["confusion"][w,a]
            threat=float(data["threats"][w,a]);previous=a
        results.append({"reward_sum":total,"occupancy":occupancy.tolist(),"confusion_tn_fp_fn_tp":confusion.tolist()})
    return results


def main():
    OUT.mkdir(exist_ok=False)
    torch.set_num_threads(1)
    original=json.loads((OLD/"config/scheduler_experiment_v1.json").read_text())
    train_seeds=original["training_and_selection"]["training_trace_seeds"]
    validation_seeds=original["training_and_selection"]["validation_trace_seeds"]
    manifest=json.loads((OLD/"policy_inputs/manifest.json").read_text())
    calibration=ROOT/"supplemental_scheduler_20261112/latency_calibration_02/report.json"
    calibrated=json.loads(calibration.read_text())
    if calibrated["status"]!="PASS":raise RuntimeError("calibration not accepted")
    source_paths=list(HERE.glob("*.py"))+list((OLD/"scheduler").glob("*.py"))
    bindings={str(p.relative_to(ROOT)):sha(p) for p in source_paths}
    matrix=[(algorithm,variant,seed) for algorithm,variants in (("Tabular-Q",VARIANTS),("DQN",("full",))) for variant in variants for seed in SEEDS]
    save(OUT/"TRAINING_LOCK.json",{"created_epoch":time.time(),"matrix":matrix,"episodes_per_run":1000,
        "windows_per_episode":500,"train_trace_seeds":train_seeds,"validation_trace_seeds":validation_seeds,
        "checkpoint_rule":"last episode only; no checkpoint search",
        "physical_selection":"maximum validation reward sum among full-state seeds, tie lowest seed; no test use",
        "reward_source_sha256":sha(HERE/"core.py"),"source_sha256":bindings,"calibration_sha256":sha(calibration),
        "original_config_sha256":sha(OLD/"config/scheduler_experiment_v1.json"),
        "queue_ablation":"NOT_EXECUTED_NOT_IDENTIFIABLE_USER_ACCEPTED",
        "thermal_claim":False,"test_data_access":False,
        "cost_scope":"new warm-input p95 latency surrogate; historical TON static power proxy, not new measured energy",
        "limitations":"zero backlog in this simulator; no queue-control claim; test previously seen in historical study",
        "train_cache":manifest["output_sha256"]["ton_iot_train_predictions.npz"],
        "validation_cache":manifest["output_sha256"]["validation_drift_401.npz"]})
    archive=OUT/"executed_source";archive.mkdir()
    for path in source_paths:
        dest=archive/path.relative_to(ROOT);dest.parent.mkdir(parents=True,exist_ok=True)
        with dest.open("xb") as f:f.write(path.read_bytes())
    costs=[(original["resource_cost_registry"]["models"][m]["mean_watts"],calibrated["latency_registry"][m]["p95_seconds"]) for m in ACTIONS]
    train_pool=read_pool("ton_iot_train_predictions.npz",manifest)
    val_pool=read_pool("validation_drift_401.npz",manifest)
    trdir=OUT/"train_traces";vdir=OUT/"validation_traces";trdir.mkdir();vdir.mkdir()
    train=[prepare(train_pool,s,costs,trdir) for s in train_seeds]
    validation=[prepare(val_pool,s,costs,vdir) for s in validation_seeds]
    save(OUT/"WORKLOAD_HASHES.json",{str(p.relative_to(OUT)):sha(p) for d in (trdir,vdir) for p in d.iterdir()})
    registry=[]
    for algorithm,variant,seed in matrix:
        name=f"{algorithm}-{variant}-{seed}";dest=OUT/name;dest.mkdir()
        config=copy.deepcopy(original)
        config["reward"]={"implementation":"scheduler_followup/core.py:reward",
            "detection_weight":.5,"power_weight":.2,"completion_weight":.2,
            "deadline_penalty":1.,"unfinished_fraction_penalty":1.,"thermal_component":None}
        config["online_state"]["discrete_state_cardinality"]={"full":108,"minus_arrival":36,"minus_threat":36,"minus_previous_action":27}[variant]
        policy=(TabularQPolicy if algorithm=="Tabular-Q" else DQNPolicy)(config,seed=seed)
        save(dest/"config.json",config)
        with gzip.open(dest/"transitions.jsonl.gz","xt") as log,(dest/"episodes.jsonl").open("x") as progress:
            for episode in range(1000):
                data=train[episode%len(train)];threat,previous=.5,0;total=0.
                for w,n in enumerate(data["arrivals"]):
                    state=encode(Observation(int(n),0,threat,previous),variant)
                    action=policy.select_action(state,training=True,episode=episode);a=ACTION_ORDER.index(action)
                    value=float(data["rewards"][w,a]);total+=value
                    threat=float(data["threats"][w,a]);previous=a;terminal=w==499
                    next_state=state if terminal else encode(Observation(int(data["arrivals"][w+1]),0,threat,previous),variant)
                    if algorithm=="Tabular-Q":policy.update(TabularUpdate(state,action,value,next_state,terminal,Partition.TRAIN))
                    else:
                        policy.observe(DQNTransition(state,action,value,next_state,terminal,Partition.TRAIN));policy.optimize()
                    log.write(json.dumps([episode,w,state,a,value,next_state,terminal])+"\n")
                progress.write(json.dumps({"episode":episode,"reward_sum":total})+"\n");progress.flush()
                if episode%100==0:print(json.dumps({"run":name,"episode":episode}),flush=True)
        policy.freeze()
        weights=dest/("weights.npy" if algorithm=="Tabular-Q" else "weights.pt")
        with weights.open("xb") as f:
            if algorithm=="Tabular-Q":np.save(f,policy.q_values,allow_pickle=False)
            else:torch.save(policy.copy_online_state(),f)
        result={"run":name,"algorithm":algorithm,"variant":variant,"seed":seed,"weights_sha256":sha(weights),
                "updates":policy.update_count,"frozen":True,"validation":evaluate(policy,variant,validation),"test_accessed":False}
        save(dest/"result.json",result);registry.append(result)
        print(json.dumps({"completed":name,"runs_completed":len(registry)}),flush=True)
    selected={a:max((x for x in registry if x["algorithm"]==a and x["variant"]=="full"),
                   key=lambda x:(sum(v["reward_sum"] for v in x["validation"]),-x["seed"]))["run"] for a in ("Tabular-Q","DQN")}
    save(OUT/"POLICY_SELECTION_FREEZE.json",{"selected":selected,"registry":registry,"test_accessed":False})
    print(json.dumps({"status":"TRAINING_COMPLETE","selected":selected}),flush=True)


if __name__=="__main__":
    main()
