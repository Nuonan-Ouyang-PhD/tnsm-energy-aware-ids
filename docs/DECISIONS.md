---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '3660da55-1cb7-4527-bca1-15f10c9064b7'
  PropagateID: '3660da55-1cb7-4527-bca1-15f10c9064b7'
  ReservedCode1: 'daf43c3f-00e7-4879-9052-cdab64978b9b'
  ReservedCode2: 'daf43c3f-00e7-4879-9052-cdab64978b9b'
---

# Experiment decisions

1. All old tables, plots, and validation CSVs are historical drafting material,
   not formal evidence, because their raw logs, code, and provenance are absent.
2. Raspberry Pi 4 Model B 8 GB (`pi4b8g`) is the primary evaluation device.
3. The Pi 3B+, Pi 4B 4 GB, and Pi 5 are optional sequential portability checks;
   they are not required to run simultaneously with the primary device.
4. One external logging power meter is sufficient because devices are measured
   sequentially. Internal Pi telemetry is diagnostic, not a replacement for
   input-power measurement.
5. The M4 Mac mini is used for data preparation, model training, orchestration,
   aggregation, and plotting. It is not the claimed lightweight deployment target.
6. Pi 5 is excluded from the present stage while HORIZON00 is running.
7. Smoke results are always marked `paper_eligible=false`.
8. TON-IoT ground-truth CSVs are excluded. `train_test_network.csv` already
   carries the `label` and `type` label columns, and the 18 GroundTruth files
   (about 990 MB) correspond to the full Processed/Raw dataset that this
   experiment does not download. Per-row joins across versions would risk
   mixing dataset provenance, so the selected-subset status is
   `ground_truth: not_applicable_to_selected_subset`. If the full Processed
   Network data is ever adopted, the 23 processed CSVs and 18 ground-truth CSVs
   must be acquired, registered, and validated together as a new protocol
   version; they must never be mixed with the present subset.
9. The first TON-IoT acquisition and inventory manifests
   (`ton_iot_20260903T075757Z.json`, `ton_iot_20260903T075904Z.json`) were
   generated with the earlier, broader `selected_scope` wording ("processed
   and train/test network-traffic material") inherited from the stage-setup
   commit, which described more material than was actually acquired. The
   acquired bytes themselves are correct: `train_test_network.csv` plus the
   four official Network Features-Description / Statistics documents. The
   config and acquisition document now state the exact scope, and both
   manifests were regenerated against the corrected commit. The superseded
   manifests remain in the repository, unchanged, as append-only diagnostic
   records; only the regenerated manifests belong to the frozen evidence.

> AI生成