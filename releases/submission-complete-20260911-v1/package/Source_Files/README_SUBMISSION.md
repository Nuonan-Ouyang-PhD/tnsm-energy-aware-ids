# TNSM merged submission package (2026-09-11)

This package uses the verified eight-page rich manuscript as the active baseline. The main PDF was freshly compiled from `main.tex`; it is not copied from an earlier V4/V5 build.

## Included manuscript updates

- Restored the measured DeadlineGuard--Static-MedRF comparison: 43.714 J (2.98%), paired 95% CI 41.418--46.010 J, 512/5,000 deadline misses removed, with the 1.373-pp F1 trade-off.
- Retained run SDs, the DQN block-4 excursion diagnostic and figure, the 66.76% cascade-window explanation, and the 314/324 Tabular-Q off-support map.
- Added the offline all-detector validation-threshold diagnostic, CFSM occupancy detail, and clearly labelled DQN timing sensitivity bounds. None changes a frozen primary threshold or physical result.
- The planned controller-only R3' measurement remains unexecuted and is not used for attribution.

## Evidence boundaries

Physical measurements are TON-IoT replay on one Raspberry Pi 4B with a KM003C power meter. CICIoT2023 and N-BaIoT support supplementary classification/replay checks; no cross-dataset dynamic-power claim is made. Frozen V1/P0/P1 evidence is not modified or rerun.

## Recompile

From the package root:

```text
tectonic -X compile --outdir ../build main.tex
tectonic -X compile --outdir ../build supplement.tex
```

The delivered main manuscript is 8 pages and the supplement is 26 pages. `main.bbl`, all section files, figures, and table inputs are included for Overleaf or local compilation.

## Fresh-build checks

- Main PDF page count: 8.
- Main PDF text contains the restored 0.7967 non-degeneracy threshold, 43.714 J DeadlineGuard result, 512/5,000 deadline count, 314/324 support map, 66.76% cascade-window statistic, 49.05-pp TinyDT threshold diagnostic, CFSM occupancy, and 1.5669-ms DQN timing.
- Source/PDF timestamp check was performed after compilation; the PDF is newer than the latest `.tex` source.
- ZIP CRC/self-test and content manifest are checked in the delivery root.
