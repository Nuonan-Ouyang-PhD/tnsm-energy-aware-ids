"""Bounded, group-isolated native classifiers; no energy claims or raw edits."""
import os
os.environ.setdefault('OMP_NUM_THREADS','2')
os.environ.setdefault('OPENBLAS_NUM_THREADS','2')
import csv
import hashlib
import json
import time
from collections import Counter, defaultdict
from pathlib import Path

import joblib
import numpy as np
import torch
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
                             confusion_matrix, precision_recall_fscore_support, roc_auc_score)
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.tree import DecisionTreeClassifier

HERE=Path(__file__).resolve().parent
WORK=HERE.parent
DATA=Path('/Volumes/RESEARCH_DATA/TNSM-MATERIALIZATION-20260906-V1')
RESULTS=HERE/'results'
SPLITS=('train','validation','test')
CAPS={'train':200000,'validation':100000,'test':100000}
SEED=11
MODELS=('TinyDT','LightLR','MedRF','HeavyMLP')
CATEGORIES=['proto','service','conn_state','ssl_version','ssl_cipher','http_method',
            'http_version','http_orig_mime_types','http_resp_mime_types','weird_name']


def dump(path,value):
    with path.open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False);f.write('\n')


def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def key(value):
    return hashlib.sha256(('11|'+value).encode()).hexdigest()


def ton_assignments():
    auth=json.loads((WORK/'materialization_run_v2/authorization.json').read_bytes())
    source=Path(auth['source_roots']['ton_iot'])/'train_test_network.csv'
    expected='26ddc513552de36de6428b2e578efaed2b57504c716dfba847cc0109a64e1974'
    assert digest(source)==expected, 'TON grouping source no longer matches frozen input'
    split=[]; groups={}
    with source.open(encoding='utf-8-sig',newline='') as f:
        for row in csv.DictReader(f):
            group=key('|'.join(sorted([row['src_ip'],row['dst_ip']])))
            bucket=int(group[:16],16)%100
            s='train' if bucket<60 else 'validation' if bucket<80 else 'test'
            groups[group]=s;split.append(s)
    assert digest(source)==expected, 'TON grouping source changed while reading'
    return np.asarray(split),groups


def assign_shards(dataset,ledgers):
    if dataset=='ton_iot':return {},[]
    assignments={};uncovered=[]
    if dataset=='n_baiot':
        devices=sorted({x['source_file'].split('/')[0] for x in ledgers},key=key)
        assert len(devices)==9
        mapping={v:('train' if n<5 else 'validation' if n<7 else 'test') for n,v in enumerate(devices)}
        assignments={x['shard_id']:mapping[x['source_file'].split('/')[0]] for x in ledgers}
    else:
        groups=defaultdict(list)
        for x in ledgers:groups[x['source_file'].split('/')[1]].append(x)
        for category,items in groups.items():
            items=sorted(items,key=lambda x:key(x['source_file']));n=len(items)
            if n<3:
                uncovered.append(category)
                for x in items:assignments[x['shard_id']]='train'
                continue
            nval=max(1,int(n*.2));ntest=max(1,int(n*.2));ntrain=n-nval-ntest
            for ordinal,x in enumerate(items):assignments[x['shard_id']]='train' if ordinal<ntrain else 'validation' if ordinal<ntrain+nval else 'test'
    return assignments,uncovered


def numeric(value):
    if value in ('T','True','true'):return 1.
    if value in ('F','False','false'):return 0.
    try:
        v=float(value)
        return v if np.isfinite(v) else np.nan
    except ValueError:return np.nan


def select_rows(dataset,destination):
    lineage=DATA/'datasets'/dataset/'lineage/shards.jsonl'
    ledgers=[json.loads(x) for x in lineage.read_text().splitlines()]
    mapping,uncovered=assign_shards(dataset,ledgers)
    ton_splits,ton_groups=ton_assignments() if dataset=='ton_iot' else (None,{})
    plan={};totals=Counter();offsets=Counter()
    for index,x in enumerate(ledgers):
        if dataset=='ton_iot':
            assert len(ton_splits)==x['source_rows_accepted']
            for s in SPLITS:totals[s]=int(np.count_nonzero(ton_splits==s))
        else:totals[mapping[x['shard_id']]]+=x['source_rows_accepted']
    sampled={s:np.sort(np.random.default_rng(SEED+i).choice(totals[s],size=min(CAPS[s],totals[s]),replace=False)) for i,s in enumerate(SPLITS)}
    for index,x in enumerate(ledgers):
        if dataset=='ton_iot':
            plan[index]={s:np.flatnonzero(ton_splits==s)[sampled[s]] for s in SPLITS}
        else:
            s=mapping[x['shard_id']];start=offsets[s];end=start+x['source_rows_accepted']
            a=sampled[s];plan[index]={s:a[np.searchsorted(a,start):np.searchsorted(a,end)]-start};offsets[s]=end
    with (DATA/ledgers[0]['features_file']).open() as f:columns=next(csv.reader(f))
    cats=[i for i,v in enumerate(columns) if dataset=='ton_iot' and v in CATEGORIES]
    nums=[i for i in range(len(columns)) if i not in cats]
    pools={s:{'numeric':np.empty((len(sampled[s]),len(nums)),dtype=np.float64),
              'categorical':np.empty((len(sampled[s]),len(cats)),dtype=object),
              'y':np.empty(len(sampled[s]),dtype=np.int8),
              'ids':np.empty((len(sampled[s]),2),dtype=np.int64),
              'fingerprints':np.empty(len(sampled[s]),dtype='U64')} for s in SPLITS}
    filled=Counter();identity=[]
    for index,x in enumerate(ledgers):
        selected={int(row):s for s,rows in plan[index].items() for row in rows}
        hf=hashlib.sha256();hl=hashlib.sha256();rows_seen=0
        with (DATA/x['features_file']).open('rb') as ff,(DATA/x['labels_file']).open('rb') as lf:
            fh=ff.readline();lh=lf.readline();hf.update(fh);hl.update(lh)
            assert next(csv.reader([fh.decode().rstrip('\n')]))==columns
            assert next(csv.reader([lh.decode().rstrip('\n')]))==['binary_label','canonical_family','source_family','source_subtype']
            for rownum,raw in enumerate(ff):
                label=lf.readline();assert label
                hf.update(raw);hl.update(label);rows_seen+=1
                if rownum not in selected:continue
                s=selected[rownum];j=filled[s];filled[s]+=1
                values=next(csv.reader([raw.decode().rstrip('\n')]))
                labels=next(csv.reader([label.decode().rstrip('\n')]))
                assert len(values)==len(columns) and labels[0] in ('benign','attack')
                pools[s]['numeric'][j]=[numeric(values[i]) for i in nums]
                pools[s]['categorical'][j]=[values[i] for i in cats]
                pools[s]['y'][j]=int(labels[0]=='attack')
                pools[s]['ids'][j]=[index,rownum+1]
                pools[s]['fingerprints'][j]=hashlib.sha256(json.dumps(values,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
            assert not lf.readline()
        assert rows_seen==x['source_rows_accepted']
        assert hf.hexdigest()==x['features_sha256'] and hl.hexdigest()==x['labels_sha256']
        identity.append({'shard':index,'source_file':x['source_file'],'source_sha256':x['source_file_sha256'],'rows':rows_seen,
                         'split':mapping.get(x['shard_id'],'per_row_IP_pair'),
                         'feature_sha256_verified':hf.hexdigest(),'labels_sha256_verified':hl.hexdigest()})
        print(json.dumps({'event':'sampled_shard','dataset':dataset,'ordinal':index+1,'filled':dict(filled)}),flush=True)
    seen={};removed={};conflicts={};counts={}
    for s in SPLITS:
        pool=pools[s];assert filled[s]==len(sampled[s])
        keep=np.ones(filled[s],dtype=bool);conflicts[s]=0
        if s!='train':
            for i,h in enumerate(pool['fingerprints']):
                if h in seen:
                    keep[i]=False;conflicts[s]+=int(seen[h]!=int(pool['y'][i]))
        removed[s]=int((~keep).sum())
        for k in pool:pool[k]=pool[k][keep]
        for h,y in zip(pool['fingerprints'],pool['y']):seen[h]=int(y)
        counts[s]={'rows':len(pool['y']),'benign':int((pool['y']==0).sum()),'attack':int((pool['y']==1).sum()),
                   'numeric_missing_cells':int(np.isnan(pool['numeric']).sum())}
        assert len(np.unique(pool['y']))==2, (dataset,s,'insufficient two-class holdout after leakage filtering')
        np.savez_compressed(destination/(s+'_pool.npz'),**{k:v for k,v in pool.items() if k!='categorical'})
    split_report={'dataset':dataset,'seed':SEED,'partition_rows_before_sampling':dict(totals),
        'sample_counts':counts,'cross_split_duplicates_removed':removed,'conflicting_duplicates_removed':conflicts,
        'train_only_categories':uncovered,'shards':identity,'ton_pair_group_assignments':ton_groups,
        'numeric_columns':[columns[i] for i in nums],'categorical_columns':[columns[i] for i in cats],
        'native_feature_count':len(columns),'materialization_manifest_sha256':digest(DATA/'MANIFEST_SHA256.txt')}
    dump(destination/'split_manifest.json',split_report)
    return pools,split_report


def encode(pools,destination):
    imputer=SimpleImputer(strategy='median',keep_empty_features=True)
    scaler=StandardScaler()
    train=imputer.fit_transform(pools['train']['numeric']);scaler.fit(train)
    encoder=None
    if pools['train']['categorical'].shape[1]:
        encoder=OneHotEncoder(handle_unknown='infrequent_if_exist',min_frequency=5,max_categories=128,sparse_output=False,dtype=np.float32)
        encoder.fit(pools['train']['categorical'])
    result={}
    for s,p in pools.items():
        x=scaler.transform(imputer.transform(p['numeric'])).astype(np.float32)
        if encoder is not None:x=np.concatenate([x,encoder.transform(p['categorical'])],axis=1)
        assert np.isfinite(x).all(), 'nonfinite encoded tensor'
        result[s]=x
        np.save(destination/(s+'_X.npy'),x)
    joblib.dump({'imputer':imputer,'scaler':scaler,'encoder':encoder},destination/'preprocessor.joblib')
    return result


def metrics(y,p):
    prediction=p>=.5
    precision,recall,f1,_=precision_recall_fscore_support(y,prediction,average='binary',zero_division=0)
    return {'rows':len(y),'accuracy':float(accuracy_score(y,prediction)),
            'balanced_accuracy':float(balanced_accuracy_score(y,prediction)),
            'precision':float(precision),'recall':float(recall),'f1':float(f1),
            'roc_auc':float(roc_auc_score(y,p)),'average_precision':float(average_precision_score(y,p)),
            'confusion_matrix':confusion_matrix(y,prediction,labels=[0,1]).tolist()}


def train(dataset,pools,x,destination):
    torch.set_num_threads(2);torch.use_deterministic_algorithms(True)
    models={'TinyDT':DecisionTreeClassifier(max_depth=6,min_samples_split=20,min_samples_leaf=10,random_state=SEED),
            'LightLR':LogisticRegression(C=1,solver='liblinear',max_iter=1000,random_state=SEED),
            'MedRF':RandomForestClassifier(n_estimators=25,max_depth=10,min_samples_split=10,min_samples_leaf=5,n_jobs=2,random_state=SEED)}
    cache={s:np.empty((len(pools[s]['y']),4),dtype=np.float32) for s in ('validation','test')}
    summary={}
    for index,name in enumerate(MODELS):
        start=time.monotonic()
        if name!='HeavyMLP':
            model=models[name];model.fit(x['train'],pools['train']['y'])
            joblib.dump(model,destination/(name+'.joblib'))
            predict=lambda a:model.predict_proba(a)[:,1]
        else:
            torch.manual_seed(SEED);np.random.seed(SEED)
            model=torch.nn.Sequential(torch.nn.Linear(x['train'].shape[1],64),torch.nn.ReLU(),torch.nn.Dropout(.2),
                torch.nn.Linear(64,32),torch.nn.ReLU(),torch.nn.Dropout(.2),torch.nn.Linear(32,16),torch.nn.ReLU(),
                torch.nn.Dropout(.2),torch.nn.Linear(16,1))
            optimizer=torch.optim.Adam(model.parameters(),lr=.001);loss_fn=torch.nn.BCEWithLogitsLoss()
            tx=torch.from_numpy(x['train']);ty=torch.tensor(pools['train']['y'],dtype=torch.float32).reshape(-1,1)
            for epoch in range(30):
                model.train();order=torch.randperm(len(tx));loss_sum=0.
                for b in range(0,len(tx),1024):
                    ix=order[b:b+1024];optimizer.zero_grad();loss=loss_fn(model(tx[ix]),ty[ix]);loss.backward();optimizer.step();loss_sum+=loss.item()*len(ix)
                print(json.dumps({'event':'mlp_epoch','dataset':dataset,'epoch':epoch+1,'train_loss':loss_sum/len(tx)}),flush=True)
            model.eval();torch.save({'input_dim':tx.shape[1],'state_dict':model.state_dict()},destination/'HeavyMLP.pt')
            def predict(a):
                with torch.no_grad():return np.concatenate([torch.sigmoid(model(torch.from_numpy(a[b:b+4096]))).numpy().ravel() for b in range(0,len(a),4096)])
        summary[name]={'training_seconds':time.monotonic()-start}
        for s in ('validation','test'):
            pred=predict(x[s]);assert np.isfinite(pred).all()
            cache[s][:,index]=pred;summary[name][s]=metrics(pools[s]['y'],pred)
        print(json.dumps({'event':'classifier_complete','dataset':dataset,'model':name,'metrics':summary[name]}),flush=True)
    for s in ('validation','test'):np.savez_compressed(destination/(s+'_predictions.npz'),probabilities=cache[s],labels=pools[s]['y'],ids=pools[s]['ids'],fingerprints=pools[s]['fingerprints'],models=np.array(MODELS))
    dump(destination/'classification_metrics.json',summary)
    return summary


def main():
    complete=json.loads((WORK/'materialization_run_v2/completion.json').read_bytes())
    assert complete['exit_code']==0 and complete['output_exists'] and not complete['staging_exists']
    RESULTS.mkdir()
    dump(RESULTS/'run_identity.json',{'plan_sha256':digest(HERE/'PLAN.md'),'script_sha256':digest(Path(__file__)),
        'materialization_manifest_sha256':digest(DATA/'MANIFEST_SHA256.txt'),'seed':SEED,
        'status':'software_classifier_study; physical energy and adaptive policy study not yet complete',
        'numpy':np.__version__,'torch':torch.__version__})
    result={}
    for dataset in ('ton_iot','ciciot2023','n_baiot'):
        folder=RESULTS/dataset;folder.mkdir()
        pools,split=select_rows(dataset,folder);x=encode(pools,folder)
        result[dataset]=train(dataset,pools,x,folder)
        del pools,x
    dump(RESULTS/'classification_summary.json',result)
    print('CLASSIFICATION_CAMPAIGN_COMPLETE',flush=True)


if __name__=='__main__':main()
