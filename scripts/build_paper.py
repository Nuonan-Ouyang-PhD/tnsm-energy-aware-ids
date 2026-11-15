#!/usr/bin/env python3
"""Build the paper from recorded JSON results. No training or hardware access.

Requires Python 3.11+, NumPy, SciPy, Matplotlib, latexmk, pdfLaTeX, and Poppler.
Run from any directory: python3 scripts/build_paper.py
"""
from __future__ import annotations
import itertools
import json
import math
import re
import shutil
import statistics
import subprocess
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAPER = ROOT / 'paper'
SOURCE = PAPER / 'Source_Files'
DATA = ROOT / 'releases/supplemental-followup-20261113/analysis'
OLD = ROOT / 'releases/submission/package/Source_Files'
METHODS = ['Static-LightLR', 'Tabular-Q', 'DQN', 'ConfidenceCascade_0p3_0p7', 'DeadlineGuard', 'Static-MedRF']
NAMES = {'Static-LightLR': 'Static-LightLR', 'Static-MedRF': 'Static-MedRF', 'Tabular-Q': 'Q-learning', 'DQN': 'DQN', 'DeadlineGuard': 'DeadlineGuard', 'ConfidenceCascade_0p3_0p7': 'Cascade'}
SHORT = dict(zip(METHODS, ['LR', 'Q', 'DQN', 'C', 'DG', 'RF']))
SETS = {'A': list(range(1, 11)), 'B': list(range(2, 11)), 'C': [2, 3, 4, 6, 7, 8, 9, 10]}
METRICS = ['energy_joules', 'mean_watts', 'idle_adjusted_energy_joules', 'idle_adjusted_mean_watts', 'f1', 'recall', 'fpr', 'balanced_accuracy', 'deadline_miss_windows', 'late_completed_rows', 'completed_rows', 'final_backlog_rows']
DOCUMENTS = {'main': 'Manuscript', 'Supplementary_Material': 'Supplementary_Material', 'Response_to_Reviewers': 'Response_to_Reviewers', 'Cover_Letter': 'Cover_Letter'}


def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8'))


def write(relative: str, text: str) -> None:
    path = SOURCE / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8')


def paired(rows, first, second, metric, blocks):
    from scipy.stats import t
    d = [float(rows[b, first][metric]) - float(rows[b, second][metric]) for b in blocks]
    mean, sd = statistics.mean(d), statistics.stdev(d)
    half = float(t.ppf(.975, len(d)-1)) * sd / math.sqrt(len(d))
    return mean, sd, mean-half, mean+half


def load_results():
    runs = read_json(DATA / 'RUN_METRICS.json')
    rows = {(r['block'], r['method']): r for r in runs}
    expected = {(b, m) for b in range(1, 11) for m in METHODS}
    if len(runs) != 60 or set(rows) != expected:
        raise ValueError('Expected exactly ten complete six-method blocks')
    registered = read_json(DATA / 'PAIRED_STATISTICS_AND_SENSITIVITIES.json')
    aliases = {'all_valid': 'A', 'exclude_block1': 'B', 'exclude_all_recovered': 'C'}
    if len(registered) != 540:
        raise ValueError('Expected 540 paired entries')
    for item in registered:
        actual = paired(rows, item['first'], item['second'], item['metric'], SETS[aliases[item['set']]])
        recorded = (item['mean_difference'], item['sample_sd'], *item['ci95'])
        if not all(math.isclose(a, b, rel_tol=1e-7, abs_tol=1e-7) for a, b in zip(actual, recorded)):
            raise ValueError(f'Paired values differ: {item["first"]}, {item["second"]}, {item["metric"]}, {item["set"]}')
    return runs, rows


def generate_tables(runs, rows):
    write('tables/numbers.tex', '% Tables are generated from the recorded run-level results.\n')
    lines = [r'\begin{table*}[t]\centering\small',
             r'\caption{Physical results over ten paired blocks per method. Energy is mean $\pm$ sample SD; detection entries are block means. All methods complete 627,500 rows per run, with zero recorded deadline-miss windows, late completed rows, and final backlog.}\label{tab:results}',
             r'\begin{tabular}{lrrrrr}\toprule Method & Energy (J) & F1 & Recall (\%) & FPR (\%) & Window action\\\midrule']
    for m in METHODS:
        rr = [rows[b, m] for b in SETS['A']]
        energy = [r['energy_joules'] for r in rr]
        action = 'LightLR' if m in METHODS[:3] else 'MedRF' if m in METHODS[4:] else 'Cascade'
        lines.append(f'{NAMES[m]} & ${statistics.mean(energy):.1f}\\pm{statistics.stdev(energy):.1f}$ & {statistics.mean(r["f1"] for r in rr):.4f} & {100*statistics.mean(r["recall"] for r in rr):.3f} & {100*statistics.mean(r["fpr"] for r in rr):.3f} & {action}'+r'\\')
    lines += [r'\bottomrule\end{tabular}\end{table*}']
    write('tables/main_results.tex', '\n'.join(lines)+'\n')

    lines = [r'\begin{table*}[t]\centering\footnotesize',
             r'\caption{Energy sensitivities, in J/run. Each entry is mean difference [nominal paired 95\% CI]. A: all ten blocks; B: exclude block 1; C: exclude blocks 1 and 5. Adjusted energy subtracts the corresponding preceding-idle baseline.}\label{tab:sensitivity}',
             r'\setlength{\tabcolsep}{4pt}\begin{tabular}{llrrr}\toprule Contrast & Endpoint & A ($n=10$) & B ($n=9$) & C ($n=8$)\\\midrule']
    contrasts = [('Tabular-Q','Static-LightLR'), ('DQN','Static-LightLR'), ('ConfidenceCascade_0p3_0p7','Static-MedRF'), ('DeadlineGuard','Static-MedRF')]
    for a, b in contrasts:
        for metric, endpoint in [('energy_joules','Raw'), ('idle_adjusted_energy_joules','Adjusted')]:
            cells = []
            for blocks in SETS.values():
                mean, sd, lo, hi = paired(rows, a, b, metric, blocks)
                cells.append(f'${mean:+.2f}\\;[{lo:.2f},{hi:.2f}]$')
            lines.append(f'{SHORT[a]}--{SHORT[b]} & {endpoint} & '+' & '.join(cells)+r'\\')
    lines += [r'\bottomrule\end{tabular}\end{table*}']
    write('tables/main_sensitivity.tex', '\n'.join(lines)+'\n')

    registry = read_json(DATA / 'ACCEPTED_RUN_REGISTRY.json')
    positions = {r['spec']['run_id']: r['spec']['position'] for r in registry}
    lines = [r'\small\setlength{\tabcolsep}{5pt}\begin{longtable}{rrlrrrr}',
             r'\caption{All accepted workloads.}\label{tab:runs}\\',
             r'\toprule Block & Order & Method & Raw (J) & Adjusted (J) & F1 & Recall (\%)\\\midrule\endfirsthead',
             r'\toprule Block & Order & Method & Raw (J) & Adjusted (J) & F1 & Recall (\%)\\\midrule\endhead',
             r'\bottomrule\endfoot']
    for r in sorted(runs, key=lambda x: (x['block'], positions[x['run_id']])):
        lines.append(f'{r["block"]} & {positions[r["run_id"]]} & {NAMES[r["method"]]} & {r["energy_joules"]:.1f} & {r["idle_adjusted_energy_joules"]:.1f} & {r["f1"]:.4f} & {100*r["recall"]:.3f}'+r'\\')
    lines += [r'\end{longtable}\normalsize']
    write('tables/run_results.tex', '\n'.join(lines)+'\n')

    labels = {'energy_joules':'Energy (J)', 'mean_watts':'Power (W)', 'idle_adjusted_energy_joules':'Adjusted energy (J)', 'idle_adjusted_mean_watts':'Adjusted power (W)', 'f1':'F1 (pp)', 'recall':'Recall (pp)', 'fpr':'FPR (pp)', 'balanced_accuracy':'BA (pp)', 'deadline_miss_windows':'Missed windows', 'late_completed_rows':'Late rows', 'completed_rows':'Completed rows', 'final_backlog_rows':'Final backlog'}
    lines = [r'\footnotesize\setlength{\tabcolsep}{4pt}\begin{longtable}{lllrrr}',
             r'\caption{All 540 method-pair, metric, and analysis-set combinations.}\label{tab:allpairs}\\',
             r'\toprule Pair & Outcome & Set & Mean & SD & 95\% CI\\\midrule\endfirsthead',
             r'\toprule Pair & Outcome & Set & Mean & SD & 95\% CI\\\midrule\endhead', r'\bottomrule\endfoot']
    for a, b in itertools.combinations(METHODS, 2):
        for metric in METRICS:
            scale = 100 if metric in {'f1','recall','fpr','balanced_accuracy'} else 1
            digits = 4 if 'watts' in metric or scale == 100 else 2 if 'joules' in metric else 0
            for s, blocks in SETS.items():
                mean, sd, lo, hi = (scale*x for x in paired(rows,a,b,metric,blocks))
                lines.append(f'{SHORT[a]}--{SHORT[b]} & {labels[metric]} & {s} & {mean:.{digits}f} & {sd:.{digits}f} & $[{lo:.{digits}f},{hi:.{digits}f}]$'+r'\\')
    lines += [r'\end{longtable}\normalsize']
    write('tables/all_pairs.tex', '\n'.join(lines)+'\n')

    for source, dest in [('overlap_rows.tex','overlap_rows.tex'), ('p1e_rows.tex','hyperparameter_rows.tex')]:
        write('tables/'+dest, (OLD/'tables'/source).read_text(encoding='utf-8'))
    reward = (OLD/'tables/p1d_rows.tex').read_text(encoding='utf-8')
    write('tables/reward_rows.tex', '\n'.join(line for line in reward.splitlines() if line.startswith('Reward &'))+'\n')


def make_plot(rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.7, 3.2))
    pairs = [('Tabular-Q','Static-LightLR'), ('DQN','Static-LightLR'), ('ConfidenceCascade_0p3_0p7','Static-MedRF'), ('DeadlineGuard','Static-MedRF')]
    for i, (a,b) in enumerate(pairs):
        differences = [rows[k,a]['energy_joules']-rows[k,b]['energy_joules'] for k in SETS['A']]
        y = [i + (k-4.5)*.025 for k in range(10)]
        ax.scatter(differences, y, s=15, alpha=.65)
        mean, sd, lo, hi = paired(rows,a,b,'energy_joules',SETS['A'])
        ax.errorbar(mean,i,xerr=[[mean-lo],[hi-mean]],fmt='D',capsize=4,markersize=5)
    ax.axvline(0,linewidth=.8,linestyle='--')
    ax.set_yticks(range(len(pairs)), ['Q - Static-LightLR','DQN - Static-LightLR','Cascade - Static-MedRF','DeadlineGuard - Static-MedRF'])
    ax.set_xlabel('Paired energy difference (J/run)')
    ax.invert_yaxis()
    fig.tight_layout()
    target = SOURCE/'figures/paired_energy.pdf'
    target.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(target, bbox_inches='tight')
    plt.close(fig)


def prepare_sources():
    for name in ['IEEEtran.cls','IEEEtran.bst']:
        shutil.copy2(OLD/name, SOURCE/name)
    bib = (ROOT/'manuscript_working/Source_Files/references.bib').read_text(encoding='utf-8')
    write('references.bib', '\n'.join(line for line in bib.splitlines() if not line.lstrip().startswith('%'))+'\n')
    for name in ['training_returns.pdf','validation_returns.pdf']:
        dest=SOURCE/'figures'/name
        dest.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(OLD/'figures'/name,dest)
    # Keep the journal abstract within its 200-word limit.
    path=SOURCE/'main.tex'
    text=path.read_text(encoding='utf-8')
    abstract = r'''Selecting a lightweight intrusion detector can reduce energy use without requiring an adaptive controller. We examine the added value of runtime selection using six methods in ten paired blocks on a Raspberry Pi 4B, varying arrival rate and attack prevalence. Q-learning and a deep Q-network select LightLR throughout. Their energy differences from Static-LightLR are +0.25 J and +0.60 J per 500-second run, with paired 95\% confidence intervals of $[-4.05,4.55]$ J and $[-4.12,5.32]$ J. A confidence cascade reduces energy by 12.06 J relative to Static-MedRF, with reductions of 0.0446 percentage points in F1, 0.2411 points in recall, and 0.1534 points in false-positive rate. The energy direction persists under idle adjustment and exclusion of interrupted blocks. All methods complete the workload without recorded deadline violations; the deadline-based controller remains on MedRF. A pairwise immediate-utility condition clarifies how resource normalization restricts action preferences. These findings distinguish detector choice from adaptation and show the importance of comparing learned selectors with their realized static choices and input-dependent alternatives.'''
    text=re.sub(r'\\begin\{abstract\}.*?\\end\{abstract\}', lambda m: '\\begin{abstract}\n'+abstract+'\n\\end{abstract}', text, flags=re.S)
    path.write_text(text,encoding='utf-8')
    # Standard pdfLaTeX accepts the source's UTF-8 punctuation; minus signs in
    # prose quotes are normalized without altering the review wording.
    for p in SOURCE.glob('*.tex'):
        txt=p.read_text(encoding='utf-8').replace('\u2212','-')
        p.write_text(txt,encoding='utf-8')


def compile_documents():
    for command in ['latexmk','pdftotext','pdfinfo']:
        if shutil.which(command) is None:
            raise RuntimeError(f'{command} is required')
    output=ROOT/'paper-build'
    output.mkdir(exist_ok=True)
    pages={}
    for stem, name in DOCUMENTS.items():
        cmd=['latexmk','-pdf','-interaction=nonstopmode','-halt-on-error','-file-line-error', '-outdir='+str(output), stem+'.tex']
        process=subprocess.run(cmd,cwd=SOURCE,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
        (output/(stem+'.console.txt')).write_text(process.stdout,encoding='utf-8')
        print(process.stdout[-9000:],flush=True)
        if process.returncode:
            raise RuntimeError(f'LaTeX failed: {stem}')
        log=(output/(stem+'.log')).read_text(encoding='utf-8',errors='replace')
        fatal=['There were undefined references','Citation `','Reference `','Missing character:','Overfull \\hbox','Overfull \\vbox']
        hits=[line for line in log.splitlines() if any(marker in line for marker in fatal)]
        if hits:
            raise RuntimeError(f'{stem}: '+ '\n'.join(hits))
        pdf=output/(stem+'.pdf')
        text=subprocess.check_output(['pdftotext',str(pdf),'-'],text=True)
        (output/(stem+'.txt')).write_text(text,encoding='utf-8')
        if '\ufffd' in text or '??' in text:
            raise RuntimeError(f'Unexpected text extraction marker: {stem}')
        info=subprocess.check_output(['pdfinfo',str(pdf)],text=True)
        pages[name]=int(re.search(r'^Pages:\s+(\d+)',info,re.M).group(1))
        shutil.copy2(pdf,PAPER/(name+'.pdf'))
        bbl=output/(stem+'.bbl')
        if bbl.exists():
            shutil.copy2(bbl,SOURCE/bbl.name)
        if shutil.which('pdftoppm'):
            preview=output/'previews'
            preview.mkdir(exist_ok=True)
            subprocess.run(['pdftoppm','-f','1','-singlefile','-scale-to','1400','-png',str(pdf),str(preview/name)],check=True)
    if pages['Manuscript']>10 or pages['Cover_Letter']!=1:
        raise RuntimeError(f'Page target exceeded: {pages}')
    return pages


def make_package(pages):
    target=PAPER/'TNSM_Submission.zip'
    suffixes={'.tex','.bib','.bbl','.bst','.cls','.pdf'}
    with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for name in DOCUMENTS.values():
            z.write(PAPER/(name+'.pdf'),name+'.pdf')
        for p in sorted(SOURCE.rglob('*')):
            if p.is_file() and p.suffix in suffixes:
                z.write(p,'Source_Files/'+p.relative_to(SOURCE).as_posix())
    with zipfile.ZipFile(target) as z:
        if z.testzip() is not None:
            raise RuntimeError('ZIP CRC error')
        if any(n.endswith('.zip') for n in z.namelist()):
            raise RuntimeError('Nested archive')
    report='\n'.join(f'{name}.pdf: {count} pages' for name,count in pages.items())+'\nTNSM_Submission.zip: four PDFs and LaTeX sources\n'
    (PAPER/'BUILD.txt').write_text(report,encoding='utf-8')
    print(report,flush=True)


def main():
    SOURCE.mkdir(parents=True,exist_ok=True)
    runs,rows=load_results()
    generate_tables(runs,rows)
    make_plot(rows)
    prepare_sources()
    pages=compile_documents()
    make_package(pages)

if __name__=='__main__':
    main()
