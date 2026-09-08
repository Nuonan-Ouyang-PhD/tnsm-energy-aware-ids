"""Small auditable evidence package; large matrices/traces remain indexed locally."""
import hashlib
import json
import shutil
import stat
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def sha(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()


def main():
    assert json.loads((ROOT/'execution/results_audit.json').read_bytes())['status']=='PASS'
    pi=json.loads((ROOT/'execution/pi_inference_report.json').read_bytes());assert pi['status']=='PASS'
    assert len(pi['datasets'])==3
    for models in pi['datasets'].values():
        assert len(models)==4
        for result in models.values():
            assert result['label_disagreements']==0 and result['rows_checked']==10000
    original=json.loads((ROOT/'execution/source_binding.json').read_bytes())
    for name,h in original['source_hashes'].items():assert sha(ROOT/name)==h,(name,'post-launch source drift')
    package=ROOT.parent/'tnsm_software_experiment_evidence_v1';package.mkdir()
    index={}
    for base in (ROOT/'results',ROOT/'execution',ROOT/'pi_check_bundle'):
        for p in sorted(base.rglob('*')):
            if p.is_file():index[str(p.relative_to(ROOT))]={'bytes':p.stat().st_size,'sha256':sha(p)}
    for p in sorted(ROOT.iterdir()):
        if p.is_file():index[p.name]={'bytes':p.stat().st_size,'sha256':sha(p)}
    with (package/'LOCAL_ARTIFACT_INDEX.json').open('x') as f:json.dump({'local_root':str(ROOT),'artifacts':index},f,indent=2)
    for relative in index:
        source=ROOT/relative
        # Exclude large sample matrices and trace arrays, but retain model weights.
        if source.suffix in ('.npy','.npz') or relative.startswith('pi_check_bundle/inputs/'):
            continue
        target=package/relative;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
    files=sorted(p for p in package.rglob('*') if p.is_file())
    manifest=''.join(sha(p)+'  '+p.relative_to(package).as_posix()+'\n' for p in files)
    (package/'MANIFEST_SHA256.txt').write_text(manifest)
    out=ROOT.parent/'TNSM_SOFTWARE_EXPERIMENT_EVIDENCE_V1.zip'
    with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(package.rglob('*')):
            if not p.is_file():continue
            item=zipfile.ZipInfo(package.name+'/'+p.relative_to(package).as_posix(),(1980,1,1,0,0,0))
            item.create_system=3;item.external_attr=(stat.S_IFREG|0o644)<<16;item.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(item,p.read_bytes())
    with zipfile.ZipFile(out) as z:
        assert z.testzip() is None
        for line in manifest.splitlines():
            h,name=line.split('  ',1);assert hashlib.sha256(z.read(package.name+'/'+name)).hexdigest()==h
    print(json.dumps({'path':str(out),'bytes':out.stat().st_size,'sha256':sha(out),'manifest_files':len(files),'indexed_local_artifacts':len(index)},indent=2))


if __name__=='__main__':main()
