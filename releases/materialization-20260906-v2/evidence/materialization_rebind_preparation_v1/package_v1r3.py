import hashlib
import json
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

work=Path(__file__).resolve().parent.parent
root=work/'materialization_executor_evidence_v1r3'
report=root/'reports';report.mkdir()
proc=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(root/'tests'),'-p','test_materializer_synthetic.py'],capture_output=True,text=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
with (report/'synthetic_tests.log').open('x') as f:f.write(proc.stdout+proc.stderr)
assert proc.returncode==0 and 'Ran 32 tests' in proc.stderr
contract=json.loads((root/'contract/materialization_contract_v1r2.json').read_bytes())
with zipfile.ZipFile(work/'MATERIALIZATION_REBIND_EVIDENCE_V1.zip') as z:
    old=json.loads(z.read('materialization_rebind_evidence_v1/contract/materialization_contract_v1r2.json'))
    for name in old['runtime_evidence_binding']['required_local_files']:
        if name.startswith('inputs/'):
            assert (root/name).read_bytes()==z.read('materialization_rebind_evidence_v1/'+name)
    changes={}
    for key in set(old)|set(contract):
        if old.get(key)!=contract.get(key):changes[key]={'before':old.get(key),'after':contract.get(key)}
    assert set(changes)=={'contract_id','runtime_evidence_binding','header_identity'}
    with (report/'contract_diff.json').open('x') as f:json.dump(changes,f,indent=2)
files=sorted(p for p in root.rglob('*') if p.is_file())
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(root).as_posix()+'\n' for p in files)
with (root/'MANIFEST_SHA256.txt').open('x') as f:f.write(manifest)
dest=work/'MATERIALIZATION_EXECUTOR_EVIDENCE_V1R3.zip'
with zipfile.ZipFile(dest,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted([root]+list(root.rglob('*'))):
        i=zipfile.ZipInfo(p.relative_to(work).as_posix()+('/' if p.is_dir() else ''),(1980,1,1,0,0,0))
        i.create_system=3;i.external_attr=((stat.S_IFDIR|0o755) if p.is_dir() else (stat.S_IFREG|0o644))<<16;i.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(i,b'' if p.is_dir() else p.read_bytes())
print(json.dumps({'archive_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'manifest_sha256':hashlib.sha256(manifest.encode()).hexdigest(),'contract_sha256':hashlib.sha256((root/'contract/materialization_contract_v1r2.json').read_bytes()).hexdigest(),'executor_sha256':hashlib.sha256((root/'scripts/materialize_dataset_native_v1r2.py').read_bytes()).hexdigest(),'tests':32,'unchanged_runtime_metadata_files':8},indent=2))
