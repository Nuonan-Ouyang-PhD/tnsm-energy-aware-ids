---
AIGC:
  ContentProducer: '001191110102MAD55U9H0F10002'
  ContentPropagator: '001191110102MAD55U9H0F10002'
  Label: '1'
  ProduceID: '32bfcb43-be16-477f-83cf-d38643080811'
  PropagateID: '32bfcb43-be16-477f-83cf-d38643080811'
  ReservedCode1: 'df396d11-ce66-4bff-8e2f-307afab7751d'
  ReservedCode2: 'df396d11-ce66-4bff-8e2f-307afab7751d'
---

# Field semantics review record

This document records the official-documentation review of the three
dataset field inventories, performed after the TON-IoT label census
(`TON-IOT-LABEL-CENSUS-20260903-V1-VERIFIED`) and before any label or
feature mapping freeze. All statuses below are review outcomes, not
freeze decisions; every cross-dataset mapping remains `proposed` until
the ontology freeze, and this record itself is input to that freeze.

Sources reviewed (all official):

- TON-IoT: `datasets/incoming/ton_iot/Network Features-Description.pdf`
  (46-row feature table) and `Statistics of Network Records.pdf`.
- CICIoT2023: `datasets/incoming/ciciot2023/README.pdf` (feature table
  and attack taxonomy embedded as images) and `CSV-README.pdf`.
- N-BaIoT: UCI dataset page snapshot\n  `references/dataset_docs/n_baiot/uci_dataset_page_2026-09-04.html`\n  (SHA-256 `e0b79978d166b601ce1e8480625d8ad9fe40b328ad92d66f8eebde9730\n  b5d57f`, fetched 2026-09-04T00:00:39Z) and the introductory paper\n  Meidan et al. 2018\n  `references/dataset_docs/n_baiot/meidan2018_arxiv_v1_2026-09-04.pdf`\n  (open-access arXiv v1 PDF linked by UCI; related published-article\n  DOI: 10.1109/MPRV.2018.03367731; SHA-256 `1fa5bc4d4d2a12c2e93b18c4\n  d876bd83ab7f456797934fcc71c92db754811964`, fetched\n  2026-09-04T01:08:47Z); the frozen ZIP contains no feature\n  description.

## 1. TON-IoT field semantics (46 features per official table)

The official table covers all 44 CSV columns plus `ts` and
`http_uri`-adjacent entries; the train_test_network.csv header has 44
columns (no `ts`; the official table's 45/46 are `label`/`type`).

Key per-connection semantics (official wording summarized):

- `duration`: time of the packet connection = last packet seen − first
  packet seen. Unit: seconds implied, aggregation: connection.
- `src_bytes` / `dst_bytes`: payload bytes of TCP sequence numbers,
  directional, per connection. (NOTE: official text says "payload bytes
  of TCP sequence numbers", i.e. these are payload-byte counts, not IP
  totals; the IP-total columns are `src_ip_bytes`/`dst_ip_bytes`.)
- `src_pkts` / `dst_pkts`: packet counts per direction, per connection.
- `src_ip_bytes` / `dst_ip_bytes`: total IP-layer bytes including
  header, per direction.
- `missed_bytes`: missing bytes in content gaps.
- DNS/SSL/HTTP/weird columns: protocol-scoped per-connection
  attributes (categorical or numeric depending on column).
- `label` (0=normal, 1=attack) and `type` (attack category): labels,
  never features.

## 2. CICIoT2023 field semantics (per official README feature table)

The 39-column CSV header corresponds to the official feature table as
follows (notable observations only):

- `Header_Length`: header length (per packet/flow as extracted).
- `Protocol Type`: integer-coded protocol (IP, UDP, TCP, IGMP, ICMP,
  Unknown).
- `Time_To_Live`: TTL. (Official table lists a feature named "Duration"
  with description "Time-to-Live (ttl)"; the CSV header uses
  `Time_To_Live`. The header is authoritative for the CSV.)
- `Rate`: rate of packet transmission in a flow.
- Flag counts (`ack_count`, `syn_count`, `fin_count`, `rst_count`):
  number of packets with that flag set in the same flow. The boolean
  flag number columns (`fin_flag_number` .. `cwr_flag_number`) are flag
  values.
- Protocol indicator columns (`HTTP` .. `LLC`): 0/1 indicators of
  protocol presence in the flow.
- Length statistics (`Tot sum`, `Min`, `Max`, `AVG`, `Std`): statistics
  of packet lengths in the flow. `Tot sum` = "Summation of packets
  lengths in flow" (sum over packets in the flow, both directions —
  directionality not separated).
- `Tot size`: "Packet's length" (single-packet quantity in the official
  table; its exact per-row semantics in the released CSVs is not further
  documented).
- `IAT`: "The time difference with the previous packet" (inter-arrival
  time statistic; the official table does not state which aggregate
  (mean/max/last) is used per row).
- `Number`: "The number of packets in the flow."
- `Variance`: "Variance of the lengths of incoming packets in the flow /
  The variance of the lengths of outgoing packets in the flow" (the
  slash phrasing is ambiguous about direction).
- The official table also lists `ts`, `flow duration`, `Srate`, `Drate`,
  `urg coun`, `Magnitue`, `Radius`, `Covariance`, `Weight` — these names
  do NOT appear in the 39-column CSV header; the released per-category
  CSVs contain a 39-column subset. The header (frozen in the inventory)
  is authoritative for what is actually present.

Attack taxonomy (official README): 33 attacks in 7 categories (DDoS ×12,
DoS ×4, Recon ×5 listed in README — Port Scan, OS Scan, Host Discovery,
Ping Sweep, Vulnerability Scan; the release directories also split
Recon into 4 directories, with VulnerabilityScan counted under Recon in
the README taxonomy; Web-based ×6, Brute Force ×1, Spoofing ×2, Mirai
×3), plus benign. The 34 CSV directories (33 attack + Benign_Final)
match this taxonomy.

## 3. N-BaIoT field semantics (per UCI page "Additional Variable
Information")

- Stream-aggregation prefixes:
  - `H`: stats summarizing recent traffic from this packet's host (IP).
  - `HH`: stats summarizing recent traffic from this packet's host (IP)
    to the packet's destination host.
  - `HH_jit`: jitter of the traffic host->destination.
  - `HpHp`: stats summarizing recent traffic host+port -> host+port.
  - `MI_dir`: damped-window statistics aggregated by Source MAC-IP\n    (derived by elimination from Meidan et al. 2018 group widths; see\n    Section 5); `weight` = damped count, `mean`/`variance` = mean and\n    variance of outbound-only packet sizes; disposition `derived`,\n    decision `proposed`.
- Time frames: `L5, L3, L1, ...` are decay factors (damped window);
    how much recent history the statistics capture. L1 is damped-window
    statistics with decay factor λ=1; this is not a literal fixed
    one-second window.
- Statistics: `weight` (number of items observed in recent history),
  `mean`, `std`, `radius` (root squared sum of the two streams'
  variances), `magnitude` (root squared sum of the two streams' means),
  `cov` (approximated covariance between two streams), `pcc`
  (approximated Pearson-type correlation between two streams — the UCI
  text literally repeats "an approximated covariance between two
  streams" for both cov and pcc; the pcc wording on the page is
  truncated/duplicated, recorded as an unresolved wording point).
- Units are not stated for mean/std/radius/magnitude (they inherit the
  unit of the underlying per-stream statistic, itself undocumented in
  the page).
- Aggregation level: per-packet-triggered stream statistics over a
  damped window — NOT per-connection and NOT per-flow totals.
- No missing values (official page: "Has Missing Values? No") — matches
  the inventory's 0-malformed-row finding.
- 115 features, 7,062,606 instances (official page matches inventory).

## 4. Candidate mapping dispositions

Each candidate below was assessed against the seven gates (meaning,
unit, aggregation object, time window, directionality, reproducible
formula, official documentation support). Per the review instruction:
anything that cannot confirm unit, window, directionality, or
aggregation level is `unresolved` or `rejected` — column names alone
never justify a mapping.

| # | Candidate | TON-IoT | CICIoT2023 | N-BaIoT | Disposition |
|---|-----------|---------|------------|---------|-------------|
| 1 | `total_transferred_bytes` | `src_bytes+dst_bytes` (payload bytes per connection, directional split available) | `Tot sum` (sum of packet lengths in flow, directions merged) | none (window stats, no plain totals) | **unresolved** — aggregation objects differ (connection payload bytes vs flow packet-length sum); window/aggregation mismatch with any N-BaIoT column is structural |
| 2 | `packet_count` | `src_pkts+dst_pkts` (per-connection directional packet counts) | `Number` (packets in flow) | none (weight is damped-window item count, not a flow total) | **unresolved** — connection vs flow aggregation unproven identical; N-BaIoT weight is windowed, rejected for three-way |
| 3 | `flow_duration` | `duration` (last − first packet time, per connection) | none in the 39-column header (`flow duration` appears in the official table but NOT in the released CSV header) | none | **rejected as three-way** — only TON-IoT carries a duration column in the released data |
| 4 | `tcp_flag_indicators` | none (conn_state is a state string, not flags) | `fin/syn/rst/psh/ack/ece/cwr_flag_number` + `*_count` (per flow) | none | **rejected as three-way** — no TON-IoT flag-count columns in the released CSV |
| 5 | `protocol_indicators` | `proto` (categorical: tcp/udp/icmp...) | `TCP`, `UDP`, `ICMP`, `IGMP`, `IPv`, `LLC`, `ARP`, `DHCP` (0/1) | none | **derived (pairwise; decision_status=proposed)** — derivable by one-hot of `proto`; formula reproducible; but value sets differ (proto values observed in TON-IoT must be enumerated first — currently unknown beyond documentation) |
| 6 | `packet_length_statistics` | none in released CSV | `Min/Max/AVG/Std/Tot sum/Variance` (packet lengths in flow) | `HH_*_mean/std/magnitude/radius/cov/pcc` at L1 (damped-window statistics with decay factor λ=1; this is not a literal fixed one-second window) | **rejected** — CICIoT2023 aggregates over the whole flow; N-BaIoT aggregates over a damped window with stream decomposition; window and stream semantics differ. Cannot be equated without inventing semantics |
| 7 | `inter_arrival_time` | none in released CSV | `IAT` (time difference with previous packet; aggregate unspecified in official docs) | `HH_jit_*` (jitter of host->dest stream, damped window) | **rejected/unresolved** — IAT's per-row aggregate is undocumented; HH_jit is a damped-window stream statistic; different objects |
| 8 | `bytes_per_packet_ratio` | derivable (`(src_bytes+dst_bytes)/(src_pkts+dst_pkts)`) | derivable (`Tot sum/Number`) | none comparable | **unresolved** — derived on both sides but numerator semantics differ (payload bytes vs packet lengths incl. headers); unit mismatch unresolved |
| 9 | `src_bytes+dst_bytes` vs `Tot sum` (narrow form of #1) | payload bytes of TCP sequence numbers | summation of packets lengths in flow | — | **rejected** — payload bytes (TCP payload) vs packet lengths (link/IP packet length) are different physical quantities; converting requires header-size assumptions not documented |
| 10 | any TON-IoT column vs any N-BaIoT column | per-connection Zeek logs | — | damped-window stream statistics | **rejected (structural)** — no TON-IoT↔N-BaIoT pair passes the aggregation/time-window gates; the two datasets aggregate at different levels with different windows |

Pairwise/three-way core outcome (proposed, subject to freeze):

- **Three-way core: EMPTY.** No concept passes the seven gates in all
  three datasets. This is an honest outcome, not a failure to be
  papered over.
- **Pairwise candidates (TON-IoT ↔ CICIoT2023):** protocol indicators
  (#5, `derived`) and possibly packet-count (#2, `unresolved` pending
  aggregation-object confirmation). No other pair survives.
- **TON-IoT ↔ N-BaIoT core: EMPTY.** **CICIoT2023 ↔ N-BaIoT core:
  EMPTY.**

Consequence for the paper: cross-dataset claims must rely on
`binary_label` only (plus the harmonised experimental controls), not on
any shared feature representation. The scheduler-adaptation claim
(heterogeneous detectors over heterogeneous feature spaces) is fully
consistent with an empty three-way core.

## 5. N-BaIoT `MI_dir` resolution (derived evidence)

The UCI page defines H, HH, HH_jit, HpHp but not `MI_dir` (the first
prefix of 115 columns, 15 features: MI_dir_L5/L3/L1/L0.1/L0.01 ×
weight/mean/variance). This point is now resolved by the introductory
paper (Meidan et al. 2018):

- Evidence: `references/dataset_docs/n_baiot/meidan2018_arxiv_v1_2026-09-04.pdf`
  (open-access arXiv v1 PDF linked by UCI; related published-article
  DOI: 10.1109/MPRV.2018.03367731; SHA-256 `1fa5bc4d...811964`,
  fetched 2026-09-04T01:08:47Z).
- Meidan et al. Table 2 and the "Feature extraction" section define 23
  features per time scale, covering four aggregation objects: Source
  IP, Source MAC-IP, Channel, Socket. The literal string `MI_dir` does
  not appear anywhere in the paper text.
- Matching the frozen 115-column header by group width:
  `H` = 3 features → Source IP; `HH` = 7 → Channel; `HH_jit` = 3 →
  Channel jitter; `HpHp` = 7 → Socket; leaving `MI_dir` = the remaining
  3 → Source MAC-IP.
- Conclusion: `MI_dir_*` are damped-window statistics aggregated by
  Source MAC-IP; `weight` = damped count, `mean`/`variance` = mean and
  variance of outbound-only packet sizes.
- Disposition: `semantic_disposition = derived`,
  `decision_status = proposed`. NOT `exact`, because the prefix
  attribution is by elimination from group widths, not a verbatim
  definition in the paper. Remains subject to the ontology freeze.

## 6. Status summary

- All cross-dataset mappings: `decision_status = proposed` (none
  frozen); per-mapping semantic dispositions are `exact / derived /
  unresolved / rejected` as recorded above.
- Field semantics per dataset (what each native column means): recorded
  above from official documents; the per-dataset native feature sets
  are unchanged.
- No preprocessing, splitting, training, or data materialization
  occurred in this review; inputs were the three frozen inventories,
  the four in-tree official documents, the UCI page snapshot, and the
  Meidan et al. 2018 arXiv v1 PDF.

> AI生成