# Materialization V1R3 actual execution result

PASS. The user’s superseding instruction authorized repairs and continuation of
all defined experiments without repeated approval. The previously accepted V1R2
attempt had stopped before staging because its header hash recipe differed from
the frozen inventory recipe. V1R3 corrects that implementation mismatch, keeps
raw-file hashes and frozen feature/label semantics intact, and passed 32 local
synthetic tests. V1R3 is not represented as independently externally reviewed.

Actual run ended 2026-09-06T11:55:16.331400Z, exit 0, elapsed 1261.621 seconds.
All 400 raw files passed identity, byte, header, row and exact anomaly preflight.
Input: 17,114,499,704 bytes and 54,050,349 data rows. Exactly the three registered
CIC tails were excluded. The zero-row structure file was validated, not rendered.

All 399 feature/label shard pairs passed streaming hash replay. Published data:
54,050,346 rows, 806 files, 18,778,579,551 bytes. Native feature counts remain
32 / 39 / 115. Native no-replace publication succeeded; the staging path no longer
exists. No raw data was moved, deleted, edited, or copied by the materializer.

Output: `/Volumes/RESEARCH_DATA/TNSM-MATERIALIZATION-20260906-V1`

Root manifest SHA-256:
`d79caa7ed64d1e37c0599b12bbc0af925a1c469090dfab8f104dcd6ffb9dbd1e`

Runtime evidence ZIP SHA-256:
`6701586ac840ddf8d3d13b8c39b5e2aca600d83cd27d415d473bbadb6e67569e`

The small evidence bundle contains actual authorization, exact invocation,
site refresh, all preflight/replay events, dataset manifests, lineage and output
hash/byte index. It deliberately does not contain the large materialized shards.
The collector reconciles logs/metadata; full output hashing was performed by the
executor before publication. Subsequent experiment stages are separate and are
not represented as part of this materializer’s validation.
