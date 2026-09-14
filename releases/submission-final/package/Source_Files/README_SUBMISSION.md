# TNSM new manuscript submission - 2026-09-13

Main manuscript: `main.tex`
Supplement: `supplement.tex`
Compiled manuscript: `../Manuscript.pdf` (10 pages)

## Title
When Learned IDS Model Selection Collapses to a Static Choice: A Measurement Study at the Edge

## Structure

The manuscript is now organized into eleven sections corresponding to the files under `sections/`:

1. `01_introduction.tex` — Introduction (four-part narrative: motivation, gaps, contributions, roadmap; four numbered research questions)
2. `02_background.tex` — Concise related-work positioning across edge IDS, cascades/early exit, inference serving, and learned orchestration
3. `03_system_model.tex` — Compact system model, service objectives, threat model, and adaptive-value criterion
4. `04_data.tex` — Dataset-Native Data Preparation
5. `05_methods.tex` — Detector Pool, Reward Specification, and Non-degeneracy Framework (Theorem 1 and Corollary 1; compact causal runtime sequence)
6. `06_evaluation.tex` — Evaluation Protocol and Measurement Instrumentation
7. `07_static_results.tex` — Static and Attribution Results (TON-IoT operating points; static physical; primary; P1A–P1E)
8. `08_dynamic_results.tex` — Dynamic Scheduler Results Under Fixed and Variable Load (R1 cascade; R2 factorial with DeadlineGuard positive result; R3 stop; R4 threshold diagnostic)
9. `09_discussion.tex` — Discussion (attribution scale, reward as contract, causal observables principle, off-support safety, measurement practice, external validity, six-item practitioner checklist)
10. `10_limitations.tex` — Limitations and Reproducibility Boundary
11. `11_conclusion.tex` — Conclusion

## What changed relative to the prior submission

The manuscript is a new submission that fully considers the prior TNSM-2026-10776 reviews. No experiment, split, threshold, policy, or frozen raw measurement was changed. The reorganization introduces three positive framework contributions and consolidates them with the earlier evidence:

- Pairwise non-degeneracy theorem (Theorem 1) and compact corollary in Section V-D. The complete proof and validation-only reward audit are Supplementary Theorem S1 and Algorithm S1. Under the frozen candidate-range normalization tau_{MedRF,LightLR}=0.7967 exceeds the achievable balanced-accuracy gap of 0.014 by roughly 60x, so the LightLR collapse of both learned selectors is predicted before any test outcome is inspected.
- Explicit system model, service objectives, and network-layer threat model in Section III, with an operational off-support threat surface identified as directly relevant to service management.
- Positive service-management result promoted in Section VIII-B: DeadlineGuard cuts energy by 43.714 J against Static-MedRF per 500-s run (2.98%; 95% paired CI 41.418-46.010 J), eliminates all 512/5,000 deadline misses, and costs 1.373 F1 pp. All ten paired-block energy differences share sign (exact sign-flip p=0.00195).

## Reorganized content (preserved evidence)

The supplementary P1 and reviewer campaigns (P1A-P1E, R1, R2, R3, R4) remain represented in Sections VII-VIII. All frozen numerical claims are retained. The supplement adds only the theorem proof and reward-audit pseudocode requested for methodological reproducibility; no experiment, split, threshold, policy, or raw measurement is changed.

## Content that is deliberately not claimed

- Multi-node scale-out (single Pi 4B 8 GB; single meter; no board-to-board estimate)
- Cross-dataset dynamic-power generalization (CIC/N-BaIoT auxiliary only)
- Controller-only power attribution for R2 (R3 remains NOT_EXECUTED_PREDECLARED_AMBIGUITY)
- Post-hoc equivalence testing (no equivalence margin was declared)
- Adversarial-ML threats (evasion, membership inference, poisoning) - orthogonal, discussed as future work

## Reviewer response

See `Response_to_Reviewers.pdf`. Every prior comment maps to a section in the new manuscript.

## Compilation

Run `pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex` from this directory. A generated `main.bbl`, IEEEtran.cls, and IEEEtran.bst are included for submission-system portability. All figures are under `figures/` and all table rows are under `tables/`.
