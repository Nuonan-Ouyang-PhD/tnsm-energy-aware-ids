"""Collect small, verifiable execution evidence without bundling data shards."""
import hashlib
import json
import stat
import zipfile
from collections import Counter
from pathlib import Path

HERE=Path(__file__).resolve().parent
WORK=HERE.parent


def sha(data):return hashlib.sha256(data).hexdigest()


def save(name,value):
    with (HERE/name).open('x') as f:json.dump(value,f,indent=2,ensure_ascii=False);f.write('\n')


def main():
    completion=json.loads((HERE/'completion.json').read_bytes());assert completion['exit_code']==0
    result=json.loads((HERE/'executor.stdout.json').read_bytes());output=Path(result['output_root'])
    auth=json.loads((HERE/'authorization.json').read_bytes())
    assert output.is_dir() and not Path(auth['staging_root']).exists()
    events=[json.loads(line) for line in (HERE/'executor.stderr.log').read_text().splitlines() if line.startswith('{')]
    counts=Counter(x['event'] for x in events)
    assert counts=={'preflight_start':1,'source_preflight_pass':400,'preflight_complete':1,'shard_rendered':399,'shard_replay_pass':399,'publication_complete':1}
    scans=[x for x in events if x['event']=='source_preflight_pass']
    assert len({x['source'] for x in scans})==400
    assert sum(x['bytes'] for x in scans)==17114499704
    assert sum(x['row_count'] for x in scans)==54050349
    assert sum(len(x['excluded_rows']) for x in scans)==3
    contract=json.loads((WORK/'materialization_executor_evidence_v1r3/contract/materialization_contract_v1r2.json').read_bytes())
    for dataset,binding in contract['input_binding']['inventories'].items():
        inv=json.loads((WORK/'materialization_executor_evidence_v1r3'/binding['file']).read_bytes())
        actual={x['relative_path']:x for x in scans if x['source'].startswith(auth['source_roots'][dataset]+'/')}
        assert set(actual)=={x['relative_path'] for x in inv['files']}
        for expected in inv['files']:
            got=actual[expected['relative_path']]
            for field in ('sha256','bytes','row_count','header_sha256'):assert got[field]==expected[field]
    save('source_preflight_400.json',scans)
    manifest=(output/'MANIFEST_SHA256.txt').read_bytes()
    entries={line.split('  ',1)[1]:line.split('  ',1)[0] for line in manifest.decode().splitlines()}
    files={p.relative_to(output).as_posix():p for p in output.rglob('*') if p.is_file()}
    assert set(entries)==set(files)-{'MANIFEST_SHA256.txt'}
    byte_total=sum(p.stat().st_size for p in files.values())
    assert byte_total==result['output_bytes']<=25671749556
    replay={(x['dataset'],x['ordinal']):x for x in events if x['event']=='shard_replay_pass'}
    manifests={};ledgers={};total_rows=0
    for dataset in ('ton_iot','ciciot2023','n_baiot'):
        relative='datasets/'+dataset+'/manifest.json'
        data=(output/relative).read_bytes();assert sha(data)==entries[relative]
        manifests[dataset]=json.loads(data)
        relative='datasets/'+dataset+'/lineage/shards.jsonl'
        data=(output/relative).read_bytes();assert sha(data)==entries[relative]
        ledgers[dataset]=[json.loads(line) for line in data.decode().splitlines()]
        for item in ledgers[dataset]:
            actual=replay[dataset,item['shard_ordinal']]
            for kind in ('features','labels'):
                assert actual[kind+'_sha256']==item[kind+'_sha256']==entries[item[kind+'_file']]
                assert files[item[kind+'_file']].stat().st_size==item[kind+'_bytes']
            assert actual['rows']==item['source_rows_accepted']
            total_rows+=item['source_rows_accepted']
    assert total_rows==54050346
    save('dataset_manifests.json',manifests);save('shard_lineage.json',ledgers)
    save('output_index.json',{'root':str(output),'root_manifest_sha256':sha(manifest),
        'files':{n:{'bytes':p.stat().st_size,'sha256':sha(manifest) if n=='MANIFEST_SHA256.txt' else entries[n]} for n,p in files.items()}})
    decisions=Path(auth['decisions_path']).read_bytes()
    assert decisions.startswith((HERE/'DECISIONS.before.md').read_bytes())
    with (HERE/'DECISIONS.after.md').open('xb') as f:f.write(decisions)
    save('verification_summary.json',{'status':'PASS','event_counts':dict(counts),'preflight_files':400,
        'source_rows':54050349,'excluded_rows':3,'accepted_rows':total_rows,'shard_pairs':399,
        'output_files':len(files),'output_bytes':byte_total,'root_manifest_sha256':sha(manifest),
        'verification_scope':'reconciled actual execution events and output metadata; executor verified all output hashes before native publication',
        'splitting_in_materializer':False,'training_in_materializer':False})
    print(json.dumps({'status':'PASS','output_bytes':byte_total,'accepted_rows':total_rows,'output_files':len(files)},indent=2))


if __name__=='__main__':main()
