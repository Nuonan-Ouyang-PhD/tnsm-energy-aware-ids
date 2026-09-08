# Authorized materialization attempt — stopped before staging

Authorization: MATERIALIZATION-ONLY-20260906-B123293DFE33-AUTHORIZED.
Approved final request: b123293dfe331d59393688d07c799c1fdb42f0df2367ef919c2f949843bff655.

The external authorization record was created and appended, with bindings,
source roots and normalized approval text, to the actual project DECISIONS.md.
All previous DECISIONS bytes were preserved as an unchanged prefix.
Approved evidence ZIPs, executor and configs were not modified.

Execution ended at 2026-09-06T11:18:33.962822Z (Melbourne 21:18:33), exit 2:

    REFUSED: source header SHA-256 mismatch: train_test_network.csv

The actual unmodified CLI accepted the authorization and runtime binding,
entered source preflight, then rejected the first TON source header before
counting its rows. It did not complete preflight for 400 files. No conversion,
replay or publication occurred. Both formal output and staging are absent.
No automatic retry or cleanup was performed.

## Read-only diagnosis following the stopped attempt

One diagnostic pass hashed only the TON file and inspected its header; it did
not rerun the executor, TON proto census, or preflight over the remaining data.

- TON complete-file hash equals the frozen inventory:
  26ddc513552de36de6428b2e578efaed2b57504c716dfba847cc0109a64e1974.
- Frozen inventory header hash:
  024f793b346cb855a35269b079a95db373cfad64e9ba2f448e5a8678660e2e20.
- Actual raw first-line hash (513 bytes, UTF-8 BOM and CRLF included):
  049ba74ecfe7e52812e4967dab061128f6c297614a6765fdc6884b985f76dabd.
- Parsing the first line with utf-8-sig yields exactly the frozen 44 columns.

The inventory generator src/tnsm_exp/dataset_registry.py reads utf-8-sig and
sets header_sha256 to SHA256 of the parsed header joined by U+001F. The
executor scan_source_file instead compares SHA256 of raw header bytes to that
field. Its _serialize_shard repeats this raw-header comparison, and its CSV
parser decodes utf-8 without handling the initial BOM. Thus merely bypassing
the first rejection would not be an adequate remedy.

This evidence establishes a header identity recipe incompatibility, not TON
source corruption. Previously accepted synthetic tests did not expose this
real-inventory incompatibility. No inventory/config/source-byte mutation is
proposed as a workaround.

## Required next decision

The user's failure instruction prohibits automatic retry or an ad hoc contract
change. This attempt therefore remains stopped. A reviewed executor/contract
compatibility correction with authentic inventory-style synthetic tests would
change the approved runtime binding and needs explicit direction before
implementation and a new exact binding before any rerun. No automatic rerun
authorization is inferred from the original successful-preflight continuation.

All logs are retained in this directory; no full raw or materialized dataset
is included in the failure evidence package. Splitting/training/fitting remain
unexecuted and unauthorized.
