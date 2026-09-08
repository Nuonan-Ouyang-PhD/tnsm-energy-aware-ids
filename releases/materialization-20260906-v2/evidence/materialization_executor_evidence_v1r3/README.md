# Materialization executor V1R3

User instruction after the failed first attempt: “继续 你直接完成全部所有的实验不需要经过我”.
This supersedes repeated user-approval checkpoints and authorizes compatibility
repair and subsequent experiment stages. Each executed stage retains its exact
recorded artifact bindings. This materializer itself remains materialization-only.

Changes from accepted output rebind V1: contract ID/archive root and an explicit
header identity recipe; parsed header hashing uses U+001F exactly as the frozen
inventory generator. A leading UTF-8 BOM is consumed at physical line 1 only.
Full-file raw SHA-256 still includes every BOM/line-ending byte. The same header
validator is used in preflight, conversion and streaming replay. Scientific
feature/label definitions, all eight runtime metadata files, source roots,
output roots, exceptions and storage budgets remain unchanged.

Structured stderr events provide each successful source preflight and completed
render/replay shard plus final publication. They are outside the deterministic
output tree. No automatic fallback, cleanup or retry is added.

The script/contract relative filenames retain v1r2 for entry-path compatibility;
the archive root, contract ID, actual bytes and hashes distinguish this V1R3.

Tests: previous 26 materializer tests plus six header/identity regressions.
All tests use invented fixtures. The frozen TON header column names are used
to construct one synthetic BOM/CRLF header; no raw data rows are bundled.
