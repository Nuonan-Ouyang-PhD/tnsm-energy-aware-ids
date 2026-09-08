# Actual software experiment results

Twelve fitted classifiers and 50 shared held-out traces (200 static-model evaluations) completed. Saved row identities, cross-split feature fingerprints, prediction metrics and every trace were independently recalculated by this local audit. This is not an external independent review.

## Selected pools after cross-split duplicate removal

| Dataset | Train | Validation | Test | Removed validation / test |
|---|---:|---:|---:|---:|
| ton_iot | 138441 | 22842 | 22490 | 14688 / 12582 |
| ciciot2023 | 200000 | 76709 | 71145 | 23291 / 28855 |
| n_baiot | 200000 | 87039 | 83355 | 12961 / 16645 |

## Held-out test metrics, fixed threshold 0.5

| Dataset | Model | Accuracy | Balanced accuracy | F1 | ROC-AUC |
|---|---|---:|---:|---:|---:|
| ton_iot | TinyDT | 0.4832 | 0.6599 | 0.4792 | 0.9906 |
| ton_iot | LightLR | 0.9818 | 0.9766 | 0.9620 | 0.9938 |
| ton_iot | MedRF | 0.9876 | 0.9906 | 0.9746 | 0.9967 |
| ton_iot | HeavyMLP | 0.9872 | 0.9883 | 0.9736 | 0.9915 |
| ciciot2023 | TinyDT | 0.9816 | 0.8290 | 0.9904 | 0.9997 |
| ciciot2023 | LightLR | 0.9770 | 0.7863 | 0.9880 | 1.0000 |
| ciciot2023 | MedRF | 0.9839 | 0.8501 | 0.9915 | 1.0000 |
| ciciot2023 | HeavyMLP | 0.9867 | 0.8763 | 0.9930 | 1.0000 |
| n_baiot | TinyDT | 0.9971 | 0.9861 | 0.9984 | 0.9887 |
| n_baiot | LightLR | 0.9971 | 0.9867 | 0.9984 | 0.9965 |
| n_baiot | MedRF | 0.9995 | 0.9981 | 0.9997 | 1.0000 |
| n_baiot | HeavyMLP | 0.9960 | 0.9806 | 0.9978 | 0.9945 |

## Interpretation and limits

TON TinyDT generalization deteriorated sharply on the held-out IP-pair groups despite high validation scores. The result is retained unchanged; no post-test threshold tuning or split replacement was performed. High AUROC does not cancel its large false-positive count at the fixed operational threshold.

Training used a predeclared maximum of 200,000 rows per dataset and at most 100,000 per held-out pool, not all 54 million materialized rows. Split isolation is TON IP-pair, CIC capture, and N-BaIoT device; TON is not host-disjoint. Exact feature duplicates are removed across selected pools, not exhaustively across the full dataset. Numeric imputation and categorical encoding are train-only. Native raw features remain unchanged.

Ten replay seeds vary workload draws conditional on a single model-training seed (11). Replacement and unique-row counts are recorded for every trace. Their intervals are not independent training or hardware confidence intervals. Static LightLR is included as an additional pool-member diagnostic.

Prediction caches store float32 scores. The audit confirms bitwise equality to serialized-model predictions cast to float32 and unchanged thresholded confusion counts, but rounded ties can change ROC-AUC and average precision. Classifier tables use original model scores; replay tables use the actual cached scores. Every ranking-metric difference is retained in results_audit.json; the initial audit assumption of negligible rank changes was rejected and replaced by direct model-score reconstruction, not a relaxed tolerance.

No adaptive scheduler, external-meter energy saving, full-device power, or completed physical-study claim is made here. The meter interface and actual empirical cost registry remain prerequisites. Pi encoded-input parity/timing readiness is reported separately and is not end-to-end IDS latency.
