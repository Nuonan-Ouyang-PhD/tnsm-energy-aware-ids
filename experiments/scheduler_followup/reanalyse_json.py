"""Read-only stdlib reanalysis of published JSON. No model, training or device IO."""
import argparse
import itertools
import json
import math
from pathlib import Path
import statistics

SETS={'all_valid':list(range(1,11)),'exclude_block1':list(range(2,11)),
      'exclude_all_recovered':[2,3,4,6,7,8,9,10]}
T={10:2.2621571628540993,9:2.306004135204166,8:2.3646242515927844}


def recompute(rows):
    lookup={(r['block'],r['method']):r for r in rows}
    methods=sorted({r['method'] for r in rows})
    if len(rows)!=60 or len(lookup)!=60 or len(methods)!=6 or any((b,m) not in lookup for b in range(1,11) for m in methods):
        raise ValueError('expected 60 unique runs and ten complete six-method blocks')
    metrics=[k for k,v in rows[0].items() if isinstance(v,(int,float)) and k!='block']
    result=[]
    for a,b in itertools.combinations(methods,2):
        for metric in metrics:
            for label,blocks in SETS.items():
                d=[lookup[i,a][metric]-lookup[i,b][metric] for i in blocks]
                mean=statistics.mean(d);sd=statistics.stdev(d);half=T[len(d)]*sd/math.sqrt(len(d))
                result.append(dict(set=label,first=a,second=b,metric=metric,n=len(d),mean_difference=mean,
                                   sample_sd=sd,ci95=[mean-half,mean+half]))
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('directory',type=Path,help='directory containing RUN_METRICS and PAIRED_STATISTICS_AND_SENSITIVITIES JSON')
    args=parser.parse_args();rows=json.loads((args.directory/'RUN_METRICS.json').read_text())
    computed=recompute(rows);supplied=json.loads((args.directory/'PAIRED_STATISTICS_AND_SENSITIVITIES.json').read_text())
    key=lambda r:(r['set'],r['first'],r['second'],r['metric'])
    expected={key(r):r for r in supplied};errors=[]
    if set(expected)!={key(r) for r in computed} or len(expected)!=len(supplied):errors.append('contrast membership/uniqueness')
    for row in computed:
        old=expected.get(key(row),{})
        if row['n']!=old.get('n') or any(abs(row[k]-old.get(k,math.inf))>1e-10 for k in ('mean_difference','sample_sd')) or any(abs(a-b)>1e-10 for a,b in zip(row['ci95'],old.get('ci95',[math.inf]*2))):errors.append(str(key(row)))
    print(json.dumps(dict(status='FAIL' if errors else 'PASS',statistics_checked=len(computed),errors=errors,
        scope='Author-side JSON-only recomputation, not independent raw-log or ZIP acceptance',
        intervals='paired-block Student-t, nominal unadjusted, no equivalence test'),indent=2))
    raise SystemExit(bool(errors))


if __name__=='__main__':main()
