# TNSM final submission package

This directory publishes the final clean submission bundle for:

> When Learned IDS Model Selection Collapses to a Static Choice: A Measurement Study at the Edge

The authoritative downloadable artifact is `TNSM_Submission_Final.zip`.
Its SHA-256 is:

```text
0f66889aedf77a003adc713ebfde0c8c5259cb3cb2f53cb84bea6920d9e56e4d
```

The `package/` directory is a byte-for-byte extraction of that archive so the
PDFs, LaTeX source, figures, generated table rows, bibliography, class/style
files, and source manifest can also be inspected directly on GitHub.

## Contents and checks

- 78 content files; no nested ZIP or build directory.
- Main manuscript: 10 pages.
- Supplementary material: 26 pages.
- Response to reviewers: 10 pages.
- Cover letter: 2 pages.
- ZIP CRC/self-test: PASS.
- `package/Source_Files/MANIFEST_SHA256.txt`: 73/73 entries verified.
- Clean compilation of all four deliverables: PASS.

The package uses the accepted final submission as the sole manuscript master.
The compact system model, pairwise non-degeneracy theorem/corollary,
external-budget/SLO normalization rule, focused related-work positioning,
supplementary proof and reward-audit pseudocode, and strengthened methodology
response are included without changing the frozen experimental results.

The retrospective audit is executable at
`experiments/adaptive_scheduler_v1/reward_audit.py`, with deterministic,
hash-bound outputs under `reward_audit_validation/`. It reads no test metrics.
MedRF and HeavyMLP cannot reverse against LightLR on observed validation support,
but TinyDT has greater immediate reward in seven of 2,500 windows. Neither global
LightLR optimality nor execution before test inspection is established. The former
`reward_audit_v1/` remains a historical attempt that read aggregate test diagnostics.
The current adapter reports unavailable post-action temperature as null, flags
the missing measurement, and omits the thermal penalty. Historical frozen runs
used a constant 35 C proxy and had zero thermal penalty; they are not rerun.

Seven focused regression tests and deterministic audit regeneration pass. Twelve
of thirteen scheduler infrastructure tests pass in the bundled Python environment;
the DQN unit test cannot run there because PyTorch is unavailable. All four PDFs
were rebuilt and checked for unresolved references and layout. No frozen
experiment, checkpoint, trace, configuration, or historical source was changed.

## Reproduction

To rebuild the manuscript from the extracted source:

```bash
cd package/Source_Files
pdflatex main.tex
bibtex main
pdflatex main.tex
pdflatex main.tex
```

Build `supplement.tex`, `Response_to_Reviewers.tex`, and `Cover_Letter.tex` with
`pdflatex`. The generated `main.bbl`, `IEEEtran.cls`, and `IEEEtran.bst` are
included for submission-system portability.

Dataset acquisition, software checks, physical-campaign boundaries, and large
evidence-archive reconstruction are documented in the repository root README.
Raw datasets and large measurement traces are intentionally not duplicated in
this submission bundle.
