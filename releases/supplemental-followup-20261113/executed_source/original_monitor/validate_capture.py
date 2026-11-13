"""Require continuous process-aware telemetry over the entire measured horizon."""
import json


def validate(directory, seconds, probe=False):
    events = [json.loads(x) for x in (directory/'pi_events.jsonl').read_text().splitlines()]
    start = json.loads((directory/'start.json').read_text())['start_utc_epoch']
    intervals = [e for e in events if e['event']=='cpu_interval']
    complete = [e for e in events if e['event']=='complete']
    if not intervals or len(complete)!=1 or any(e['event'] in ('failed','monitor_failed') for e in events):
        raise RuntimeError('missing/failed continuous guard')
    if any(not e['pass'] or e['limit']!=.05 or e['temperature_c']>=70 or e['throttled']!='throttled=0x0' for e in intervals):
        raise RuntimeError('guard threshold failed')
    for i,e in enumerate(intervals):
        if e['right']['monotonic']-e['left']['monotonic']>1.5:
            raise RuntimeError('guard sampling gap')
        if i and e['left']['monotonic']!=intervals[i-1]['right']['monotonic']:
            raise RuntimeError('discontinuous CPU interval')
    if intervals[0]['utc_epoch']>start or intervals[-1]['utc_epoch']<start+seconds:
        raise RuntimeError('guard does not cover measured horizon')
    if not intervals[-1]['final'] or complete[0]['cpu_intervals']!=len(intervals):
        raise RuntimeError('final guard accounting missing')
    if probe:
        outcomes=[e for e in events if e['event']=='outcome']
        if len(outcomes)!=18 or sum(e['completed_rows'] for e in outcomes)!=24900:
            raise RuntimeError('engineering probe row accounting failed')
        if any(e['backlog_rows'] for e in outcomes):
            raise RuntimeError('engineering probe unfinished backlog')
    return dict(status='PASS',cpu_intervals=len(intervals),
                maximum_external_cpu_fraction=max(e['external_busy_fraction'] for e in intervals),probe_only=probe)
