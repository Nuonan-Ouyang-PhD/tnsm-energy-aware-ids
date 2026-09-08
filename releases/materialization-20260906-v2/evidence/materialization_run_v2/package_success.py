import hashlib
import json
import stat
import zipfile
from pathlib import Path

root=Path(__file__).resolve().parent
files=sorted(p for p in root.iterdir() if p.is_file() and p.name!='MANIFEST_SHA256.txt')
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in files)
with (root/'MANIFEST_SHA256.txt').open('x') as f:f.write(manifest)
out=root.parent/'MATERIALIZATION_RUN_V2_SUCCESS_EVIDENCE.zip'
with zipfile.ZipFile(out,'x',compression=zipfile.ZIP_DEFLATED) as z:
    for p in sorted(root.iterdir()):
        assert p.is_file() and not p.is_symlink()
        item=zipfile.ZipInfo(root.name+'/'+p.name,(1980,1,1,0,0,0))
        item.create_system=3;item.external_attr=(stat.S_IFREG|0o644)<<16;item.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(item,p.read_bytes())
with zipfile.ZipFile(out) as z:
    assert z.testzip() is None
    for line in manifest.splitlines():
        h,name=line.split('  ',1);assert hashlib.sha256(z.read(root.name+'/'+name)).hexdigest()==h
print(json.dumps({'archive':str(out),'bytes':out.stat().st_size,'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'manifest_files':len(files)},indent=2))
