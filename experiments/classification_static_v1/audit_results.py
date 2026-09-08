"""Cross-check saved outputs without refitting or changing scientific choices."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path
import numpy as np
import joblib
from scipy.stats import t
from classification_campaign import metrics, MODELS

ROOT=Path(__file__).resolve().parent
RESULTS=ROOT/'results'


def read(p):return json.loads(p.read_bytes())


def main():
    summary=read(RESULTS/'classification_summary.json')
    checks=[];table=[];split_table=[];quantization=[]
    for dataset in ('ton_iot','ciciot2023','n_baiot'):
        folder=RESULTS/dataset
        split=read(folder/'split_manifest.json')
        pools={s:np.load(folder/(s+'_pool.npz'),allow_pickle=False) for s in ('train','validation','test')}
        for a,b in (('train','validation'),('train','test'),('validation','test')):
            assert not set(map(tuple,pools[a]['ids'])) & set(map(tuple,pools[b]['ids']))
            assert not set(pools[a]['fingerprints']) & set(pools[b]['fingerprints'])
        for s,pool in pools.items():
            assert len(pool['y'])==split['sample_counts'][s]['rows']
            assert int(pool['y'].sum())==split['sample_counts'][s]['attack']
        for s in ('validation','test'):
            cache=np.load(folder/(s+'_predictions.npz'),allow_pickle=False)
            assert list(cache['models'])==list(MODELS)
            for k in ('labels','ids','fingerprints'):
                assert np.array_equal(cache[k],pools[s]['y' if k=='labels' else k])
            for n,name in enumerate(MODELS):
                got=metrics(cache['labels'],cache['probabilities'][:,n]);old=summary[dataset][name][s]
                if name!='HeavyMLP':
                    model=joblib.load(folder/(name+'.joblib'))
                    full=model.predict_proba(np.load(folder/(s+'_X.npy'),mmap_mode='r'))[:,1]
                    assert np.array_equal(full.astype(np.float32),cache['probabilities'][:,n]),(dataset,name,s,'cache quantization mismatch')
                    exact=metrics(cache['labels'],full)
                else:exact=got
                for k in ('accuracy','balanced_accuracy','precision','recall','f1','roc_auc','average_precision'):
                    assert abs(exact[k]-old[k])<1e-12,(dataset,name,s,k,'original scores do not reproduce saved metric')
                for k in ('rows','confusion_matrix'):assert got[k]==old[k],(dataset,name,s,k)
                quantization.append({'dataset':dataset,'split':s,'model':name,'cache_dtype':'float32',
                    'roc_auc_delta':got['roc_auc']-old['roc_auc'],'average_precision_delta':got['average_precision']-old['average_precision'],
                    'confusion_unchanged':True,'cache_matches_serialized_model_after_float32_cast':True})
        for name in MODELS:
            row=summary[dataset][name]['test']
            table.append(f"| {dataset} | {name} | {row['accuracy']:.4f} | {row['balanced_accuracy']:.4f} | {row['f1']:.4f} | {row['roc_auc']:.4f} |")
        split_table.append(f"| {dataset} | "+' | '.join(str(split['sample_counts'][s]['rows']) for s in ('train','validation','test'))+' | '+str(split['cross_split_duplicates_removed']['validation'])+' / '+str(split['cross_split_duplicates_removed']['test'])+' |')
        checks.append({'dataset':dataset,'cross_split_row_ids_disjoint':True,'cross_split_feature_fingerprints_disjoint':True,'saved_metric_recalculation':'PASS','counts':split['sample_counts'],'train_only_categories':split['train_only_categories']})
    traces=read(RESULTS/'static_replay/summary.json');assert len(traces)==50
    aggregates=defaultdict(list)
    for entry in traces:
        dataset=entry['dataset'];scenario=entry['scenario'];seed=entry['seed']
        trace=np.load(RESULTS/'static_replay'/f'{dataset}-{scenario}-{seed}.npz',allow_pickle=False)
        cache=np.load(RESULTS/dataset/'test_predictions.npz',allow_pickle=False)
        ix=trace['indices']
        for tk,ck in (('source_ids','ids'),('feature_fingerprints','fingerprints'),('labels','labels'),('model_probabilities','probabilities')):
            assert np.array_equal(trace[tk],cache[ck][ix])
        h=hashlib.sha256(trace['source_ids'].astype('<i8').tobytes()+''.join(trace['feature_fingerprints']).encode()).hexdigest()
        assert h==entry['trace_sha256']
        assert len(np.unique(ix))==entry['unique_rows']
        if scenario=='drift':
            offset=0
            for phase in entry['design']['phases']:
                n=phase['windows'];block=trace['labels'][offset:offset+n*100].reshape(n,100)
                assert np.all(block.sum(axis=1)==round(100*phase['attack_ratio']));offset+=n*100
            assert offset==len(ix)==50000
        else:assert len(ix)==20000
        for n,name in enumerate(MODELS):
            got=metrics(trace['labels'],trace['model_probabilities'][:,n]);assert got==entry['metrics'][name]
            aggregates[dataset,scenario,name].append(got['f1'])
    aggregate=[]
    for key,values in aggregates.items():
        assert len(values)==10
        sd=float(np.std(values,ddof=1));mean=float(np.mean(values));half=float(t.ppf(.975,9)*sd/np.sqrt(10))
        aggregate.append({'dataset':key[0],'scenario':key[1],'model':key[2],'trace_seeds':10,'f1_mean':mean,'f1_sd':sd,'f1_mean_t95_interval':[mean-half,mean+half],'interpretation':'workload resampling only, conditional on one model seed and fixed split; not hardware or training uncertainty'})
    report={'status':'PASS','classifier_models':12,'shared_traces':50,'static_model_evaluations':200,'split_checks':checks,'prediction_cache_quantization':quantization,'static_replay_f1_aggregates':aggregate,'physical_energy_measured':False,'adaptive_policy_evaluated':False}
    with (ROOT/'execution/results_audit.json').open('x') as f:json.dump(report,f,indent=2)
    text='# Actual software experiment results\n\n'
    text+='Twelve fitted classifiers and 50 shared held-out traces (200 static-model evaluations) completed. Saved row identities, cross-split feature fingerprints, prediction metrics and every trace were independently recalculated by this local audit. This is not an external independent review.\n\n'
    text+='## Selected pools after cross-split duplicate removal\n\n| Dataset | Train | Validation | Test | Removed validation / test |\n|---|---:|---:|---:|---:|\n'+'\n'.join(split_table)+'\n\n'
    text+='## Held-out test metrics, fixed threshold 0.5\n\n| Dataset | Model | Accuracy | Balanced accuracy | F1 | ROC-AUC |\n|---|---|---:|---:|---:|---:|\n'+'\n'.join(table)+'\n\n'
    text+='## Interpretation and limits\n\nTON TinyDT generalization deteriorated sharply on the held-out IP-pair groups despite high validation scores. The result is retained unchanged; no post-test threshold tuning or split replacement was performed. High AUROC does not cancel its large false-positive count at the fixed operational threshold.\n\n'
    text+='Training used a predeclared maximum of 200,000 rows per dataset and at most 100,000 per held-out pool, not all 54 million materialized rows. Split isolation is TON IP-pair, CIC capture, and N-BaIoT device; TON is not host-disjoint. Exact feature duplicates are removed across selected pools, not exhaustively across the full dataset. Numeric imputation and categorical encoding are train-only. Native raw features remain unchanged.\n\n'
    text+='Ten replay seeds vary workload draws conditional on a single model-training seed (11). Replacement and unique-row counts are recorded for every trace. Their intervals are not independent training or hardware confidence intervals. Static LightLR is included as an additional pool-member diagnostic.\n\n'
    text+='Prediction caches store float32 scores. The audit confirms bitwise equality to serialized-model predictions cast to float32 and unchanged thresholded confusion counts, but rounded ties can change ROC-AUC and average precision. Classifier tables use original model scores; replay tables use the actual cached scores. Every ranking-metric difference is retained in results_audit.json; the initial audit assumption of negligible rank changes was rejected and replaced by direct model-score reconstruction, not a relaxed tolerance.\n\n'
    text+='No adaptive scheduler, external-meter energy saving, full-device power, or completed physical-study claim is made here. The meter interface and actual empirical cost registry remain prerequisites. Pi encoded-input parity/timing readiness is reported separately and is not end-to-end IDS latency.\n'
    with (ROOT/'RESULTS.md').open('x') as f:f.write(text)
    print(json.dumps({'status':'PASS','models':12,'traces':50,'evaluations':200}))


if __name__=='__main__':main()
