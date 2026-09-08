"""Authorized one-shot CLI orchestration. Never retries or cleans staging."""
import hashlib
import json
import os
import plistlib
import subprocess
import sys
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
WORK = HERE.parent
REPO = Path('/Volumes/RESEARCH_DATA/10_PROJECTS/COMPLETE_RESEARCH_BY_SOURCE_PATH/Downloads/tnsm-energy-aware-ids')
DECISIONS = REPO / 'docs/DECISIONS.md'
PACKAGE = WORK / 'materialization_executor_evidence_v1r3'
AUTH_ID = 'MATERIALIZATION-20260906-V1R3-BROAD-AUTHORIZED'


def now():
    return datetime.now(timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, obj):
    with (HERE / name).open('x') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
        f.write('\n')


def info(path):
    return plistlib.loads(subprocess.check_output(['diskutil','info','-plist',str(path)], timeout=30))


def prepare():
    expected = {'MATERIALIZATION_FINAL_REQUEST_V1.zip': 'b123293dfe331d59393688d07c799c1fdb42f0df2367ef919c2f949843bff655',
        'MATERIALIZATION_EXECUTOR_EVIDENCE_V1R3.zip': '6701586ac840ddf8d3d13b8c39b5e2aca600d83cd27d415d473bbadb6e67569e',
        'MATERIALIZATION_EXECUTION_REQUEST_V1.zip': '55c3c6ee9d6e01fb764a650432b379ca41ca52b703dd33c9ec9cf17088271c63'}
    for filename, digest in expected.items():
        assert sha(WORK / filename) == digest
    with zipfile.ZipFile(WORK / 'MATERIALIZATION_FINAL_REQUEST_V1.zip') as z:
        request_bytes = z.read('materialization_final_request_v1/final_request.json')
    assert request_bytes == (WORK/'materialization_final_request_v1/final_request.json').read_bytes()
    request = json.loads(request_bytes)
    review = Path('/Users/nuonanouyang/Downloads/MATERIALIZATION_FINAL_REQUEST_V1_INDEPENDENT_REVIEW.zip')
    with zipfile.ZipFile(review) as z:
        assert z.testzip() is None
        root='materialization_final_request_review/'
        for line in z.read(root+'MANIFEST_SHA256.txt').decode().splitlines():
            digest, name = line.split(None,1)
            assert hashlib.sha256(z.read(root+name.lstrip('*'))).hexdigest()==digest
    auth = {key: request[key] for key in ('contract_id','request_zip_sha256','executor_evidence_zip_sha256',
        'evidence_archive_root','evidence_manifest_sha256','contract_sha256','executor_sha256','output_root','staging_root','source_roots','volume_uuid')}
    auth.update({'contract_id':'MATERIALIZATION-EXECUTOR-20260906-V1R3', 'evidence_archive_root':'materialization_executor_evidence_v1r3', 'executor_evidence_zip_sha256':expected['MATERIALIZATION_EXECUTOR_EVIDENCE_V1R3.zip'], 'evidence_manifest_sha256':sha(PACKAGE/'MANIFEST_SHA256.txt'), 'contract_sha256':sha(PACKAGE/'contract/materialization_contract_v1r2.json'), 'executor_sha256':sha(PACKAGE/'scripts/materialize_dataset_native_v1r2.py'), 'superseding_user_instruction':'继续 你直接完成全部所有的实验不需要经过我', 'new_runtime_review':'local 32-test regression passed; no claim of external V1R3 review'})
    auth.update({'kind':'materialization_execution_authorization','authorization_id':AUTH_ID,
        'authorized_by_user':True,'recorded_at_utc':now(),
        'operations':{'materialization':True,'splitting':False,'training':False,'encoder_fitting':False,'model_fitting':False},
        'final_request_zip_sha256':expected['MATERIALIZATION_FINAL_REQUEST_V1.zip'],
        'final_review_zip_sha256':sha(review), 'user_approval_text_sha256':sha(HERE/'USER_APPROVAL.md'),
        'approval_text_format':'User text transcribed with tables/HTML spacing normalized; attached independent review retained separately',
        'decisions_path':str(DECISIONS)})
    save('authorization.json',auth)
    before=DECISIONS.read_bytes()
    with (HERE/'DECISIONS.before.md').open('xb') as f:f.write(before)
    save('preparation.json',{'time':now(),'approved_archives':expected,'decisions_before_sha256':hashlib.sha256(before).hexdigest(),
        'decisions_before_bytes':len(before),'review_zip_sha256':sha(review),'executor_path':str(PACKAGE/'scripts/materialize_dataset_native_v1r2.py')})
    with (HERE/'final_review.zip').open('xb') as f:f.write(review.read_bytes())
    print(json.dumps(auth,indent=2))


def execute():
    auth=json.loads((HERE/'authorization.json').read_bytes())
    previous=(HERE/'DECISIONS.before.md').read_bytes()
    assert DECISIONS.read_bytes().startswith(previous)
    assert AUTH_ID in DECISIONS.read_text()
    volume=Path('/Volumes/RESEARCH_DATA'); vi=info(volume)
    assert vi['VolumeUUID']==auth['volume_uuid'] and vi['Writable'] and not vi['Locked']
    stores=[info(x['APFSPhysicalStore']) for x in vi['APFSPhysicalStores']]
    physical=[info(x['ParentWholeDisk']) for x in stores]
    assert all(not x['Internal'] and x['VirtualOrPhysical']=='Physical' for x in physical)
    for key in ('output_root','staging_root'):assert not os.path.lexists(auth[key])
    roots={k:Path(v) for k,v in auth['source_roots'].items()}
    for path in roots.values():
        assert path.resolve(strict=True)==path and path.is_dir()
        for key in ('output_root','staging_root'):
            target=Path(auth[key]);assert target!=path and target not in path.parents and path not in target.parents
    vfs=os.statvfs(volume); free=vfs.f_bavail*vfs.f_frsize
    assert free>=26745491380
    save('site_refresh.json',{'time':now(),'volume':vi,'stores':stores,'physical':physical,'free_bytes':free,
        'sources':{k:{'path':str(v),'device':v.stat().st_dev,'inode':v.stat().st_ino} for k,v in roots.items()},
        'output_and_staging_absent':True,'nonoverlap':True,'decisions_after_sha256':sha(DECISIONS),
        'runtime_python':sys.version,'runtime_platform':sys.platform})
    command=[sys.executable,'-B','-u',str(PACKAGE/'scripts/materialize_dataset_native_v1r2.py'),
        '--contract',str(PACKAGE/'contract/materialization_contract_v1r2.json'),'--execute',
        '--authorization-record',str(HERE/'authorization.json'), '--request-zip',str(WORK/'MATERIALIZATION_EXECUTION_REQUEST_V1.zip'),
        '--executor-evidence-zip',str(WORK/'MATERIALIZATION_EXECUTOR_EVIDENCE_V1R3.zip'), '--decisions',str(DECISIONS),
        '--ton-root',str(roots['ton_iot']),'--cic-root',str(roots['ciciot2023']),'--nb-root',str(roots['n_baiot'])]
    # Exclusive log creation prevents accidental repeat invocation before launch.
    with (HERE/'executor.stdout.json').open('x') as stdout, (HERE/'executor.stderr.log').open('x') as stderr:
        p=subprocess.Popen(['/usr/bin/caffeinate','-i']+command,stdout=stdout,stderr=stderr,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        save('process.json',{'started_at':now(),'pid':p.pid,'command':command,'sleep_prevention':'caffeinate -i','automatic_retry':False})
        print('RUNNING pid=%d; unmodified CLI; no automatic retry'%p.pid,flush=True)
        start=time.monotonic(); code=p.wait()
    save('completion.json',{'ended_at':now(),'exit_code':code,'elapsed_seconds':time.monotonic()-start,
        'output_exists':os.path.lexists(auth['output_root']),'staging_exists':os.path.lexists(auth['staging_root']),
        'splitting_run':False,'training_run':False})
    print('EXIT %d'%code,flush=True)
    sys.exit(code)


if __name__=='__main__':
    if sys.argv[1:] == ['prepare']:prepare()
    elif sys.argv[1:] == ['execute']:execute()
    else:raise SystemExit('choose prepare or execute; never retry a failed run')
