"""One-time, bounded editorial changes to the existing full manuscript.
No experiment, training, policy selection or raw-data modification.
"""
from pathlib import Path
import json
import re

ROOT = Path('TNSM_2026_10776_IDS_Model_Selection_Submission')

def replace_once(text, old, new):
    if old not in text:
        if new in text:
            return text
        raise RuntimeError('Expected source passage not found: ' + old[:100])
    if text.count(old) != 1:
        raise RuntimeError('Ambiguous source passage: ' + old[:100])
    return text.replace(old, new, 1)

def edit(name, function):
    path = ROOT / name
    before = path.read_text()
    after = function(before)
    if after != before:
        path.write_text(after)
        print('Edited', name)

lock = json.loads(Path('releases/supplemental-followup-20261113/executed_source/cadence_repair/PHYSICAL_LOCK.json').read_text())
assert abs(lock['medrf_p95'] - 0.015221096) < 1e-14

# All of the original theory, section structure and results remain in place.
def methods(s):
    s = replace_once(s,
        'Its fixed calibration is not retuned using physical outcomes.',
        r'Here $L_{95}^{\rm RF}=0.015221096$~s per batch of at most 100 rows (15.221096~ms), as recorded in the frozen physical-run configuration. At 4,000 arrivals/s with no carryover, the rule therefore predicts $40L_{95}^{\rm RF}=0.608844$~s, below its one-second threshold. This warm-input calibration is distinct from the earlier tight-loop characterization in Supplementary Table~S6; the latter is not used by this rule. Its fixed calibration is not retuned using physical outcomes.')
    s = replace_once(s,
        'Archived process-start and policy-creation timestamps indicate approximately 26.7~s',
        'For the original fixed-load training only, archived process-start and policy-creation timestamps indicate approximately 26.7~s')
    return s
edit('sections/05_methods.tex', methods)

# Guard calibration is stated beside the variable-load training/service definition.
def supplement(s):
    anchor = 'Training carryover remains zero; queue ablation is not identifiable and is not executed.'
    addition = r'''Training carryover remains zero; queue ablation is not identifiable and is not executed.

The frozen physical configuration uses a MedRF warm-input batch p95 of 15.221096~ms. DeadlineGuard multiplies this value by $\lceil(N_t+Q_t^-)/100\rceil$, where $Q_t^-$ is the pre-arrival carryover. For $N_t=4{,}000$ and zero carryover, the resulting estimate is 0.608844~s. Table~S6 reports an earlier tight-loop characterization (MedRF p95 27.4078~ms for TON-IoT); it is not the calibration used in this variable-load rule. The frozen value is retained in the companion repository's physical-run configuration, without adjustment from these physical outcomes.'''
    s = replace_once(s, anchor, addition)
    return s
edit('supplement.tex', supplement)

# Restore each Reviewer 2 comment in full, preserving its numbering and all response boxes.
comments = [
'''Comment 1: I'm not convinced the dynamic scheduler actually beats the simplest static option. Looking at Table V, static TinyDT matches the scheduler's F1 on TON-IoT and slightly beats it on CIC-IoT, while using less power and being faster on both. So what is the dynamic scheduler really buying us? The authors frame it as ``you don't need to pick a model in advance,'' but they themselves profiled all four models on the hardware to set up the cost indices---so the profiling effort was already done. I'd like to see a setting where the dynamic approach clearly wins over TinyDT, for example traffic that shifts over time, concept drift, or scenarios where the best static model changes. Otherwise the case for the added complexity is hard to make.''',
r'''Comment 2: The reward weights are picked without a good explanation, and everything depends on them. The weights $\vec{w}=[0.5,0.2,0.2,0.1]$ are just stated and used throughout. The authors admit in the Limitations that different weights would change the results, but no sensitivity analysis is provided. This is a problem because all the main findings---which model gets picked most often, the power and latency savings, the thermal behavior---flow directly from this choice. Also, the cost indices are normalized so TinyDT = 1.0, which essentially bakes ``TinyDT is cheapest'' into the reward, and then the paper reports that TinyDT dominates as a finding. Please include a sweep over different weight settings to show the conclusions hold up.''',
'''Comment 3: Table III mixes things that shouldn't be compared directly. The IoT pool models and the UNSW-NB15 reference architectures sit in one table, which makes it tempting to compare F1 across them---but the text itself says you shouldn't. I'd suggest splitting them into two tables.''',
'''Comment 4: The CFSM baseline can't be reproduced from what's written. The thresholds are described as ``fixed'' but the actual values aren't given. Since Figure 3 depends on this baseline, please add the threshold values somewhere.'''
]
def response(s):
    start = s.index(r'\section*{Reviewer 2}')
    end = s.index(r'\section*{Reviewer 3}', start)
    part = s[start:end]
    for n, comment in enumerate(comments, 1):
        pattern = r'(\\begin\{rcommentbox\}\s*)Comment ' + str(n) + r':.*?(\s*\\end\{rcommentbox\})'
        part, count = re.subn(pattern, lambda m: m[1] + comment + m[2], part, count=1, flags=re.S)
        assert count == 1, (n, count)
    s = s[:start] + part + s[end:]
    s = s.replace('Rebuilt title:', 'New manuscript title:')
    old = 'We did not restore or tune the legacy numerical story. Instead, we rebuilt the dataset lineage, detector pipeline, scheduler implementation, and physical evidence, and we now retain results even when they weaken the original claim.'
    new = 'We revised the data preparation and detector evaluation, clarified the scheduler implementation, and expanded the physical comparison. The manuscript distinguishes fixed-load characterization from the variable-load experiment and reports the detection and resource trade-offs together.'
    s = replace_once(s, old, new)
    s = replace_once(s,
        'that certifies before deployment whether a declared reward permits any state to reverse the preferred action',
        'that identifies when two actions can reverse immediate-utility preference under fixed resource differences')
    # Profiling was already required: answer the restored criticism explicitly.
    sentence = 'We report this specific trade-off, not a free improvement or universal RL failure.'
    s = replace_once(s, sentence,
        sentence + ' All compared selectors use prior detector profiling; we do not claim that runtime selection avoids that profiling cost.')
    # Retain the already corrected experiment-specific answers, dates and template.
    assert 'For the original fixed-load campaign, the training harness' in s
    assert 'These timings and the historical training durations are not measurements of corrected R2' in s
    assert '15 November 2026' in s
    return s
edit('Response_to_Reviewers.tex', response)

# Keep the same numbers and table structure; eliminate horizontal overflow locally.
def static_results(s):
    start = s.index(r'\label{tab:p1a}')
    end = s.index(r'\end{table}', start)
    block = s[start:end]
    block = block.replace(r'\setlength{\tabcolsep}{5pt}', r'\setlength{\tabcolsep}{2.6pt}')
    block = block.replace(r'\begin{tabular}{lrrr}', r'\begin{tabular}{@{}lrrr@{}}')
    block = block.replace(r'\quad ', r'\hspace{0.4em}')
    return s[:start] + block + s[end:]
edit('sections/07_static_results.tex', static_results)

# Fix the existing R1/R2 composition: make the R1 clipping physical, not just a CropBox.
# The figure data and the four existing R2 panels are not recalculated differently.
def plot_script(s):
    old = 'page.show_pdf_page(pymupdf.Rect(0,0,half,rect.height),leftdoc,0)'
    new = '''# Rasterize only the unchanged R1 source panel at 600 dpi to enforce its crop.
# A PDF CropBox alone allowed hidden historical R2 content to overlay the new panel.
left_image = leftdoc[0].get_pixmap(matrix=pymupdf.Matrix(600/72, 600/72), clip=leftdoc[0].rect, alpha=False)
page.insert_image(pymupdf.Rect(0,0,half,rect.height), pixmap=left_image)'''
    return replace_once(s, old, new)
edit('scripts/make_r2_dashboard.py', plot_script)

# Verify already-applied local cleanups rather than reverting concurrent work.
assert 'Candidate-pool normalization can prevent immediate pairwise preference reversals under fixed resource costs.' in (ROOT/'sections/01_introduction.tex').read_text()
assert 'Version &' not in (ROOT/'supplement.tex').read_text()
assert not re.search(r'&\s*v[123]\s*&', (ROOT/'tables/physical_runs_rows.tex').read_text())
assert '15 November 2026' in (ROOT/'Cover_Letter.tex').read_text()
print('Localized text changes completed; no experimental values changed.')
