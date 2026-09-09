# R4 — Software-only diagnostics and optional reference-load check

## R4A TinyDT validation-threshold diagnostic
No retraining and no replacement of the primary threshold-0.5 result.

Using the already frozen TinyDT validation probability cache:
1. evaluate all unique validation scores plus boundary candidates;
2. choose the threshold maximizing validation balanced accuracy;
3. deterministic tie break: choose the HIGHEST threshold among equal maxima to avoid an implicit FPR-favoring lower threshold;
4. freeze and hash the selected threshold before applying it to test;
5. apply exactly once to the frozen test score cache.

Report validation and test:
- threshold;
- TN/FP/FN/TP;
- F1;
- recall;
- FPR;
- balanced accuracy;
- AUROC;
- average precision / PR-AUC proxy already used in the paper.

This is a diagnostic of calibration/threshold shift. It does not replace threshold 0.5 and must be labelled post-hoc revision analysis.

## R4B Optional fixed reference-load measurement
First inventory whether a stable, independently specified USB electronic/resistive reference load is physically available.

If NOT available:
write `REFERENCE_LOAD_NOT_AVAILABLE.json` and do not improvise a calibration source.

If available with independently known nominal voltage/current/power:
- record device identity/specification and uncertainty if known;
- 5 x 300-s measurements before the new revision campaigns and 5 x 300-s measurements after;
- retain raw KM003C frames and actual timestamps;
- report repeatability, start-vs-end drift, and observed deviation from the reference specification.

Do not call this laboratory calibration unless the reference itself is traceably calibrated.
