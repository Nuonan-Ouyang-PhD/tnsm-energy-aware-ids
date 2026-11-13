"""Load only a byte-bound selected full-state policy; never optimize online."""
import hashlib
import json
from pathlib import Path

import numpy as np
from core import deadline_guard

METHODS = ('Static-LightLR', 'Static-MedRF', 'ConfidenceCascade_0p3_0p7',
           'DeadlineGuard', 'Tabular-Q', 'DQN')


def bound_bytes(path, expected):
    raw = Path(path).read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError('bound artifact drift: '+str(path))
    return raw


def load_selector(method, *, medrf_p95, config_path=None, config_sha=None,
                  weights_path=None, weights_sha=None):
    if method not in METHODS:
        raise ValueError('unknown method')
    if method == 'Static-LightLR':
        return lambda view: 1
    if method == 'Static-MedRF':
        return lambda view: 2
    if method == 'ConfidenceCascade_0p3_0p7':
        return lambda view: None
    if method == 'DeadlineGuard':
        return lambda view: deadline_guard(view, medrf_p95)
    # Deserialize the verified bytes rather than reopening a mutable path.
    import io
    config = json.loads(bound_bytes(config_path, config_sha))
    raw = bound_bytes(weights_path, weights_sha)
    if config['online_state']['discrete_state_cardinality'] != 108:
        raise ValueError('physical comparison requires full-state policy')
    if method == 'Tabular-Q':
        q = np.load(io.BytesIO(raw), allow_pickle=False)
        if q.shape != (108,4) or not np.isfinite(q).all():
            raise ValueError('invalid Q table')
        q.flags.writeable = False
        return lambda view: int(np.argmax(q[view.index]))
    import torch
    from scheduler.dqn import DQNPolicy
    from scheduler.state import ACTION_ORDER
    policy = DQNPolicy(config)
    policy.load_online_state(torch.load(io.BytesIO(raw),map_location='cpu',weights_only=True))
    policy.freeze()
    return lambda view: ACTION_ORDER.index(policy.select_action(view.index,training=False))
