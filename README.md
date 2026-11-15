# Energy-Aware Edge Intrusion Detection

Code and experiment results for **Model Selection for Energy-Aware Edge Intrusion Detection: A Controlled Measurement Study**.

The study compares static deployment, Q-learning, DQN, a deadline-based rule, and a confidence cascade on a Raspberry Pi 4B. Each method is evaluated in ten paired blocks with varying arrival rate and attack prevalence.

## Paper

[Submission package](paper/TNSM_Submission.zip) · [Manuscript](paper/Manuscript.pdf) · [Supplementary material](paper/Supplementary_Material.pdf) · [LaTeX source](paper/Source_Files/) · [Build instructions](paper/README.md)

## Main results

Q-learning and DQN select LightLR throughout the physical experiment. Their energy differences from Static-LightLR are +0.25 J and +0.60 J per 500-second run; the paired intervals span zero. DeadlineGuard selects MedRF throughout. All methods complete the workload without recorded deadline misses.

Cascade uses 12.06 J less energy than Static-MedRF, with a paired 95% interval of −16.55 to −7.58 J. F1 decreases by 0.0446 percentage points and recall by 0.2411 points, while false-positive rate decreases by 0.1534 points. This is an implementation-specific energy–detection trade-off, not a cost-free improvement.

These measurements concern whole-device USB input on one Raspberry Pi 4B and TON-IoT feature replay. They do not include packet capture, feature extraction, or training energy.

## Reproduce the reported tables

Python 3.11 or newer:

```bash
python3 experiments/scheduler_followup/reanalyse_json.py releases/supplemental-followup-20261113/analysis
```

This reads the existing run summaries and paired statistics. It does not train policies or start a hardware experiment.

To generate the manuscript tables, plot, PDFs, and submission ZIP:

```bash
python3 scripts/build_paper.py
```

The document build requires NumPy, SciPy, Matplotlib, latexmk, pdfLaTeX, and Poppler. See [paper/README.md](paper/README.md) for installation and compilation instructions.

## Code and results

| Resource | Contents |
| --- | --- |
| [Physical experiment](releases/supplemental-followup-20261113/) | Six-method run summaries, paired results, and runtime sources |
| [Executed controllers](releases/supplemental-followup-20261113/executed_source/) | State encoder, service loop, model selection, measurement code, and deployed policy weights |
| [Run metrics](releases/supplemental-followup-20261113/analysis/RUN_METRICS.json) | Per-run energy, detection, completion, and occupancy |
| [Paired results](releases/supplemental-followup-20261113/analysis/PAIRED_STATISTICS_AND_SENSITIVITIES.json) | All method pairs, three block sets, raw and idle-adjusted outcomes |
| [Classification pipeline](experiments/classification_static_v1/) | Dataset preparation, fixed detectors, and static replay |
| [Paper build](scripts/build_paper.py) | Table generation and LaTeX packaging |

Methods use current arrivals and pre-arrival FIFO carryover. Labels and future arrivals are not online inputs. Cascade observes current confidence only after LightLR inference. Training has no nonzero carryover, and temperature is safety telemetry rather than a learned control variable.

## Datasets

The physical study uses the 32-feature TON-IoT network-record pipeline. CICIoT2023 and N-BaIoT provide separate static classification characterization with 39 and 115 features. Download the source data from the original providers:

- [TON-IoT — UNSW](https://research.unsw.edu.au/projects/toniot-datasets)
- [CICIoT2023 — University of New Brunswick](https://www.unb.ca/cic/datasets/iotdataset-2023.html)
- [N-BaIoT — UCI](https://archive.ics.uci.edu/dataset/442/detection+of+iot+botnet+attacks+n+baiot)

Source datasets are not redistributed here. The [experiment directory](releases/supplemental-followup-20261113/README.md) describes the available summaries, runtime files, and raw-archive boundary. Additional fixed-rate experiments are kept separately and are not pooled with the six-method physical comparison.

## Citation

```bibtex
@misc{ouyang_edge_ids,
  author = {Nuonan Ouyang and Adrian Shatte and Zhigang Lu and Chao Chen and Wei Xiang},
  title = {Model Selection for Energy-Aware Edge Intrusion Detection: A Controlled Measurement Study},
  year = {2026},
  howpublished = {Research manuscript and accompanying code},
  url = {https://github.com/Nuonan-Ouyang-PhD/tnsm-energy-aware-ids}
}
```
