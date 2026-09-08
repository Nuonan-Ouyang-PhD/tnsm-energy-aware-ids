"""Create profile input artifacts; no fitting and no test-pool selection."""
import hashlib
import json
import shutil
from pathlib import Path
import joblib
import numpy as np
import torch

root=Path(__file__).resolve().parent
source=root.parent/'tnsm_experiments_v1/results/ton_iot'
dest=root/'inputs';dest.mkdir()
x=np.load(source/'train_X.npy',mmap_mode='r')[:10000].copy()
pool=np.load(source/'train_pool.npz',allow_pickle=False)
np.save(dest/'train_X.npy',x);np.save(dest/'train_ids.npy',pool['ids'][:10000])
names=['TinyDT','LightLR','MedRF','HeavyMLP'];pred=[]
for name in names[:-1]:
    path=source/(name+'.joblib');shutil.copy2(path,dest/path.name)
    pred.append(joblib.load(path).predict_proba(x)[:,1])
state=torch.load(source/'HeavyMLP.pt',map_location='cpu',weights_only=True)
net=torch.nn.Sequential(torch.nn.Linear(state['input_dim'],64),torch.nn.ReLU(),torch.nn.Dropout(.2),
    torch.nn.Linear(64,32),torch.nn.ReLU(),torch.nn.Dropout(.2),torch.nn.Linear(32,16),torch.nn.ReLU(),
    torch.nn.Dropout(.2),torch.nn.Linear(16,1));net.load_state_dict(state['state_dict']);net.eval()
torch.set_num_threads(2)
with torch.no_grad():pred.append(torch.sigmoid(net(torch.from_numpy(x))).numpy().ravel())
shutil.copy2(source/'HeavyMLP.pt',dest/'HeavyMLP.pt')
np.save(dest/'train_predictions.npy',np.stack(pred,axis=1))
manifest={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(dest.iterdir())}
manifest['profile_worker.py']=hashlib.sha256((root/'profile_worker.py').read_bytes()).hexdigest()
with (root/'inputs_manifest.json').open('x') as f:json.dump(manifest,f,indent=2)
print(json.dumps({'rows':len(x),'shape':list(x.shape),'bound_files':len(manifest)}))
