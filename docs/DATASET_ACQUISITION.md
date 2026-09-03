---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '31d0c646-0920-4096-b434-e5af683fc890'
  PropagateID: '31d0c646-0920-4096-b434-e5af683fc890'
  ReservedCode1: '2e63d2dd-9b87-4b04-a5d3-856f3dc64f50'
  ReservedCode2: '2e63d2dd-9b87-4b04-a5d3-856f3dc64f50'
---

# Official dataset acquisition and hash freeze

The dataset bytes are acquired and hashed on the M4 Mac mini. Large raw files
stay on the Mac and are never copied to the Pi. The official sites do not
publish one common checksum list for the exact subsets needed here, so our
manifest records the exact acquired bytes, source page, date, scope, size, and
SHA-256 before preprocessing.

## 1. Prepare directories

```bash
./scripts/init_dataset_stage.sh
```

Keep each original download unchanged in `datasets/incoming/<dataset_id>/`.
Extract a copy into `datasets/extracted/<dataset_id>/`; do not delete or rename
the original archive. Have at least 30 GB free on the Mac before beginning.

## 2. Download from the registered official source

### TON-IoT (`ton_iot`)

Official page: <https://research.unsw.edu.au/projects/toniot-datasets>

Follow the UNSW SharePoint link. Acquire only the train/test network subset
(`train_test_network.csv`) together with the official Network
Features-Description and Statistics documents. Exclude the
Processed_Network_dataset CSVs, the SecurityEvents_Network_datasets
ground-truth files, raw network logs, and the operating-system and sensor
telemetry datasets (see DECISIONS.md #8 and #9). The official page states
that academic research use is free in perpetuity and requires citation of the
dataset papers.

### CICIoT2023 (`ciciot2023`)

Official page: <https://www.unb.ca/cic/datasets/iotdataset-2023.html>

Complete the download form linked from the UNB page. Download the standard
per-category directory release (`CSV/CSV.zip`), not the PCAP directory, the
`MERGED_CSV` release, the example notebook, or the Supplementary Materials.
Labels are not present as a CSV column in the directory release; they are
derived deterministically from the directory and filename (see DECISIONS.md
#10). Save a dated copy of the download terms next to the original archive
because the form controls access and the public page does not state a simple
reusable checksum list.

Three files in the official release contain one truncated final line each
(no trailing newline, fewer than 39 columns). The raw CSVs are kept unchanged;
the three lines are registered in the quality-exception manifest and will be
excluded deterministically by their registered positions during preprocessing
(see DECISIONS.md #10).

### N-BaIoT (`n_baiot`)

Official page: <https://archive.ics.uci.edu/dataset/442/detection%2Bof%2Biot%2Bbotnet%2Battacks%2Bn%2Bbaiot>

Download the 1.7 GB archive (DOI `10.24432/C5RC8J`). Retain all nine device
directories. UCI identifies the license as CC BY 4.0. N-BaIoT labels are encoded
by directory and filename rather than a universal CSV label column.

Inside the official ZIP, each device directory carries one plain
`benign_traffic.csv` plus the attack captures packed as RAR archives
(`mirai_attacks.rar`, `gafgyt_attacks.rar`; Ennio_Doorbell and
Samsung_SNH_1011_N_Webcam ship only the gafgyt archive officially). The
original ZIP and RAR archives stay unchanged in `datasets/incoming/`; the
RAR contents are unpacked into per-archive copies under
`datasets/extracted/n_baiot/<device>/<archive>_extracted/` for inventory.
Attack labels derive from the archive subdirectory and CSV filename
(e.g., `mirai_attacks/ack.csv` -> Mirai ack).

## 3. Register immutable acquisition hashes

Run after each original download finishes:

```bash
PYTHONPATH=src .venv/bin/python -m tnsm_exp dataset-register ton_iot datasets/incoming/ton_iot
PYTHONPATH=src .venv/bin/python -m tnsm_exp dataset-register ciciot2023 datasets/incoming/ciciot2023
PYTHONPATH=src .venv/bin/python -m tnsm_exp dataset-register n_baiot datasets/incoming/n_baiot
```

Each command creates a timestamped, non-overwriting manifest under
`artifacts/datasets/acquisitions/`. Empty files and symlinks are rejected.

## 4. Inventory extracted CSVs

After extracting copies, run:

```bash
PYTHONPATH=src .venv/bin/python -m tnsm_exp dataset-inventory ton_iot datasets/extracted/ton_iot
PYTHONPATH=src .venv/bin/python -m tnsm_exp dataset-inventory ciciot2023 datasets/extracted/ciciot2023
PYTHONPATH=src .venv/bin/python -m tnsm_exp dataset-inventory n_baiot datasets/extracted/n_baiot
```

The inventory streams one file at a time, which is suitable for the 16 GB Mac.
It records every CSV hash, header, column count, row count, and malformed-row
count. Do not begin feature alignment or splitting until all three inventories
pass and have been reviewed together.

## Scientific boundary

The manuscript's historical claim of a common 44-feature mapping is not assumed
correct. The feature mapping and split policy will be constructed only from the
three real inventories. Acquisition and inventory manifests are
`paper_eligible=false`; they are provenance inputs, not results.

> AI生成