import json
import os
import subprocess
import sys
from datetime import datetime,timezone
from pathlib import Path

root=Path(__file__).resolve().parent
with (root/'test_results.log').open('x') as log:
    result=subprocess.run([sys.executable,'-B','-m','unittest','discover','-s',str(root),'-p','test_measurement.py'],stdout=log,stderr=subprocess.STDOUT)
assert result.returncode==0
with (root/'dependencies.txt').open('x') as log:
    subprocess.run([sys.executable,'-m','pip','freeze'],stdout=log,check=True)
with (root/'controller.console.log').open('x') as log:
    command=['/usr/bin/caffeinate','-i',sys.executable,'-B','-u',str(root/'controller.py')]
    child=subprocess.Popen(command,stdout=log,stderr=subprocess.STDOUT,start_new_session=True,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
record={'pid':child.pid,'command':command,'utc':datetime.now(timezone.utc).isoformat(),'scope':'15 sequential static profiles; stop on first invalid run'}
with (root/'launch.json').open('x') as f:json.dump(record,f,indent=2)
print(json.dumps(record))
