"""FIFO physical service loop; injected clock/model IO permits hardware-free tests.

No labels or future arrivals are exposed to select(). Temperature is safety-only.
This module does not start hardware or authorize a campaign.
"""
from collections import deque
from core import Observation


def run_windows(arrivals, indices, offsets, *, select, predict, clock, sleep,
                guard, emit, start):
    if len(offsets) != len(arrivals) + 1 or offsets[0] != 0 or offsets[-1] != len(indices):
        raise ValueError("workload offsets mismatch")
    if any(int(offsets[i+1]-offsets[i]) != int(n) or n < 0 for i, n in enumerate(arrivals)):
        raise ValueError("workload arrivals mismatch")
    queue = deque()
    threat, previous = .5, 0
    for window, n in enumerate(arrivals):
        target, deadline = start + window, start + window + 1
        guard()
        if clock() < target:
            sleep(target-clock())
        guard()
        observation = Observation(int(n), len(queue), threat, previous)
        for source in indices[offsets[window]:offsets[window+1]]:
            queue.append((int(source), window))
        decision_start = clock()
        action = select(observation)
        selection_seconds = clock()-decision_start
        if action not in (0, 1, 2, 3, None):
            raise ValueError("unknown action")
        batches, probabilities = [], []
        while queue and clock() < deadline:
            guard()
            pairs = [queue.popleft() for _ in range(min(100, len(queue)))]
            begin = clock()
            scores, detail = predict(action, [p[0] for p in pairs])
            finished = clock()
            scores = [float(x) for x in scores]
            if len(scores) != len(pairs) or any(not 0 <= x <= 1 for x in scores):
                raise ValueError("invalid model probabilities")
            probabilities.extend(scores)
            batches.append({"source_indices": [p[0] for p in pairs],
                "arrival_windows": [p[1] for p in pairs], "probabilities": scores,
                "service_seconds": finished-begin, "completion_from_run_start": finished-start,
                "row_deadline_missed": [finished > start+p[1]+1 for p in pairs],
                "prediction_detail": detail})
        finish = clock()
        guard()
        # No completion is a recorded overload outcome, not a silent dropped window.
        if probabilities:
            threat = sum(probabilities)/len(probabilities)
        previous = 1 if action is None else action
        emit({"window": window, "observation": vars(observation), "state_index": observation.index,
            "action": action, "selection_seconds": selection_seconds, "batches": batches,
            "completed_rows": len(probabilities), "backlog_rows": len(queue),
            "completion_seconds": finish-target, "deadline_missed": finish > deadline or bool(queue),
            "labels_available": False})
    return {"backlog_source_indices": [p[0] for p in queue],
            "backlog_arrival_windows": [p[1] for p in queue]}
