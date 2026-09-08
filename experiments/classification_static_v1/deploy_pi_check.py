"""Deploy only newly generated model/check artifacts to the isolated Pi directory."""
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parent
HOST='pi@pi4b8g.local'
REMOTE='/home/pi/tnsm-campaign-v1'


def main():
    assert (ROOT/'results/classification_summary.json').is_file()
    bundle=ROOT/'pi_check_bundle';bundle.mkdir()
    shutil.copy2(ROOT/'pi_inference_check.py',bundle/'pi_inference_check.py')
    for dataset in ('ton_iot','ciciot2023','n_baiot'):
        source=ROOT/'results'/dataset
        target=bundle/'inputs'/dataset;target.mkdir(parents=True)
        x=np.load(source/'test_X.npy',mmap_mode='r')[:10000]
        p=np.load(source/'test_predictions.npz',allow_pickle=False)['probabilities'][:len(x)]
        assert len(x)>=100 and p.shape==(len(x),4)
        np.save(target/'check_X.npy',x)
        np.save(target/'check_predictions.npy',p)
        for name in ('TinyDT.joblib','LightLR.joblib','MedRF.joblib','HeavyMLP.pt'):
            shutil.copy2(source/name,target/name)
    manifest={str(p.relative_to(bundle)):hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(bundle.rglob('*')) if p.is_file()}
    (bundle/'inputs_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    ssh=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=8',HOST]
    subprocess.run(ssh+[f'test ! -e {REMOTE}/inputs && test ! -e {REMOTE}/pi_inference_check.py && test ! -e {REMOTE}/pi_inference_report.json'],check=True)
    subprocess.run(['scp','-r',str(bundle/'inputs'),str(bundle/'inputs_manifest.json'),str(bundle/'pi_inference_check.py'),HOST+':'+REMOTE+'/'],check=True)
    with (ROOT/'execution/pi_inference.log').open('x') as log:
        result=subprocess.run(ssh+[f'{REMOTE}/venv/bin/python -B -u {REMOTE}/pi_inference_check.py'],stdout=log,stderr=subprocess.STDOUT)
    (ROOT/'execution/pi_inference_exit.json').write_text(json.dumps({'exit_code':result.returncode,'host':HOST,'remote':REMOTE},indent=2)+'\n')
    if result.returncode:raise SystemExit(result.returncode)
    subprocess.run(['scp',HOST+':'+REMOTE+'/pi_inference_report.json',str(ROOT/'execution/pi_inference_report.json')],check=True)
    with (ROOT/'execution/pi_dependencies.txt').open('x') as f:
        subprocess.run(ssh+[f'{REMOTE}/venv/bin/python -m pip freeze'],stdout=f,check=True)


if __name__=='__main__':main()
