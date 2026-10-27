# TNSM final submission package

This directory publishes the final clean submission bundle for:

> When Learned IDS Model Selection Collapses to a Static Choice: A Measurement Study at the Edge

The authoritative downloadable artifact is `TNSM_Submission_Final.zip`.
Its SHA-256 is:

```text
942a929951c5c21b2df70bd621c0726ee4aa0d3b035a840942653cadaedf2a92
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

The reward audit is now executable at
`experiments/adaptive_scheduler_v1/reward_audit.py`, with deterministic,
hash-bound outputs under `reward_audit_v1/`. It uses 2,500 validation windows
and keeps the aggregate held-out test gap as a separately labelled post-hoc
diagnostic. The manuscript also discloses that the software trace adapter's
constant 35 C temperature proxy makes the executed thermal component zero and
cannot provide action-level thermal attribution.

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
