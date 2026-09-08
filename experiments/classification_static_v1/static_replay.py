"""Shared held-out traces for static classifiers; no fabricated energy metric."""
import hashlib
import json
from pathlib import Path
import numpy as np
from classification_campaign import RESULTS, MODELS, metrics, dump

SEEDS=[11,23,37,53,71,89,107,131,157,191]
PHASES=[(100,.05),(100,.35),(120,.70),(100,.40),(80,.10)]


def trace_indices(labels,scenario,seed):
    rng=np.random.default_rng(seed)
    if scenario=='stationary':
        ids=rng.choice(len(labels),20000,replace=len(labels)<20000)
        return ids,{'replacement':len(labels)<20000,'windows':200,'samples_per_window':100}
    required={1:sum(w*round(100*r) for w,r in PHASES),0:sum(w*(100-round(100*r)) for w,r in PHASES)}
    chosen={};replacement={}
    for label in (0,1):
        pool=np.flatnonzero(labels==label);assert len(pool)>0
        replacement[label]=required[label]>len(pool)
        chosen[label]=rng.choice(pool,required[label],replace=replacement[label])
    offset={0:0,1:0};out=[]
    for windows,ratio in PHASES:
        pos=round(100*ratio);neg=100-pos
        for _ in range(windows):
            rows=np.concatenate([chosen[1][offset[1]:offset[1]+pos],chosen[0][offset[0]:offset[0]+neg]])
            offset[1]+=pos;offset[0]+=neg;rng.shuffle(rows);out.extend(rows)
    return np.array(out,dtype=np.int64),{'replacement_by_label':replacement,'required_by_label':required,
        'phases':[{'windows':w,'attack_ratio':r} for w,r in PHASES],'windows':500,'samples_per_window':100}


def main():
    output=RESULTS/'static_replay';output.mkdir()
    summaries=[]
    for dataset in ('ton_iot','ciciot2023','n_baiot'):
        cache=np.load(RESULTS/dataset/'test_predictions.npz',allow_pickle=False)
        assert list(cache['models'])==list(MODELS)
        for scenario in ('stationary','drift') if dataset!='n_baiot' else ('stationary',):
            for seed in SEEDS:
                indices,design=trace_indices(cache['labels'],scenario,seed)
                ids=cache['ids'][indices];fingerprints=cache['fingerprints'][indices]
                trace_digest=hashlib.sha256(ids.astype('<i8').tobytes()+''.join(fingerprints).encode()).hexdigest()
                filename=f'{dataset}-{scenario}-{seed}'
                np.savez_compressed(output/(filename+'.npz'),indices=indices,source_ids=ids,
                    feature_fingerprints=fingerprints,labels=cache['labels'][indices],
                    model_probabilities=cache['probabilities'][indices],models=cache['models'])
                entry={'dataset':dataset,'scenario':scenario,'seed':seed,'trace_sha256':trace_digest,
                    'rows':len(indices),'unique_rows':len(np.unique(indices)),'design':design,
                    'metrics':{name:metrics(cache['labels'][indices],cache['probabilities'][indices,n]) for n,name in enumerate(MODELS)},
                    'methods_share_identical_trace':True,'energy_measured':False,
                    'eligible_claim':'held-out classifier predictions on controlled replay only; no adaptive scheduler or physical energy result'}
                summaries.append(entry)
                dump(output/(filename+'.json'),entry)
    dump(output/'summary.json',summaries)
    print(json.dumps({'event':'static_replay_complete','shared_traces':len(summaries),'static_model_evaluations':len(summaries)*4}),flush=True)


if __name__=='__main__':main()
