# Current manuscript working tree

This tree derives from the previous submission source without overwriting it.
Scientific interpretation is being updated for the corrected November follow-up.
It is NOT a submission-ready or independently accepted package. Historical
supplement/response material retained in the source copy must be revised before
release; copying is not endorsement of its old claims. Do not submit old PDFs.

Current main source: `Source_Files/main.tex`, which selects the corrected
`sections/followup_*.tex` files. Current brief response: `Source_Files/Response_Followup.tex`.
The old full `Response_to_Reviewers.tex`, `supplement.tex`, old section files and
assets are retained as historical editing material, not current approved text.
Current supplement source: `Source_Files/Supplement_Followup.tex`, containing the
full 540-entry paired result table, information/coverage limitations and scoped
immediate-preference lemma. Full comment-by-comment response reconciliation is
still pending. Do not combine the brief current response with stale old replies.

Current compiled working PDFs: `main.pdf` (6 pages), `Supplement_Followup.pdf`
(10 pages), and `Response_Followup.pdf` (2 pages). They have been rendered for
layout review and contain no unresolved reference markers. The main build still
reports a Tectonic bibliography consistency/rerun warning and some underfull text
boxes; these are not represented as a publication-readiness PASS. Scientific
coverage, complete prior-comment reconciliation, reference audit and final layout
remain subject to review. No evidence or measurements were regenerated.

To compile from repository root with a local Tectonic installation:

```bash
tectonic --keep-logs --outdir manuscript_working manuscript_working/Source_Files/main.tex
tectonic --keep-logs --outdir manuscript_working manuscript_working/Source_Files/Supplement_Followup.tex
tectonic --keep-logs --outdir manuscript_working manuscript_working/Source_Files/Response_Followup.tex
```

The generated source manifest covers only the selected current working files,
not the preserved historical editing copies. It is not an independent audit.

Primary evidence: `../releases/supplemental-followup-20261113/`.
Correction ledger: `../docs/SCIENTIFIC_CORRECTIONS_20261114.md`.
Original frozen experimental bytes are not edited by manuscript revisions.
