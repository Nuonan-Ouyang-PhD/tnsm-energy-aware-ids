# Implementation and boundaries

## Runtime authorization gate

The CLI performs the following before it inspects any supplied source root:

1. parse the local contract only to learn the proposed guard;
2. validate a materialization-only authorization record and accepted request ZIP;
3. read the exact authorization-bound evidence ZIP into memory without extraction;
4. reject duplicate, unsafe, encrypted, symlink, non-regular, oversized,
   CRC-failing, or MANIFEST-inconsistent archive members;
5. parse the contract member from that archive as the authoritative contract;
6. compare every required local runtime file byte-for-byte with its MANIFEST-bound
   archive member using a no-follow regular-file open;
7. verify the archive root, evidence MANIFEST hash, contract hash, executor hash,
   evidence ZIP hash, request ZIP hash, output root, operation map, and append-only
   decision entry.

The approved in-memory contract is passed into execution and is not reloaded from
the pathname. All runtime files are checked again before source access and before
publication. The executor has no local Python dependency beyond the standard
library. The evidence ZIP does not claim to bind macOS, Python, or standard-library
bytes, and self-checking cannot defeat a deliberately modified program that has
also had its checks maliciously removed.

## Complete source preflight

For every inventory, the executor reconciles file count, total bytes, and total
rows and requires the discovered CSV set to match. Every listed file is then
checked for regular-file identity, byte size, full SHA-256, header SHA-256, exact
columns, row count, malformed-row count, strict UTF-8, physical-record syntax,
and the newline policy.

Only after this full pass may `n_baiot/demonstrate_structure.csv` be removed from
the shard set. It must be present exactly once and remain zero-row and well formed.

A header and every ordinary record must end in LF. The only permitted missing-LF
records are the three CIC malformed final rows already present in the frozen
quality-exception manifest. Each must match its dataset-relative path, frozen file
hash and size, final physical-line position, raw bytes/hash, column counts, row
count, and `ends_with_newline=false`. No new exception can be inferred.

## Transformation and replay

Shard numbering, feature selection, labels, metadata representations, CSV/JSON
serialization, ledgers, manifests, and root-MANIFEST rules are unchanged from the
accepted V1 output contract.

Normal output serialization writes through a byte-counting hard-cap sink and an
incremental SHA-256 sink. Replay calls the same serializer with two digest-only
sinks whose `write` methods retain no bytes and touch no filesystem path. It
compares output hashes and byte counts, source hash, accepted rows, exclusion
records, and label counts for each shard. No `.replay-*` directory exists.

Free-space checks occur before source preflight, after every normal shard pair,
after every hash-only replay shard, after dataset metadata, after run identity,
after the root manifest, and immediately before publication.

## Publication and failed staging

The executor opens the configured output parent as a directory descriptor, creates
the absent staging sibling with mode 0700 relative to that descriptor, and retains
the parent and staging device/inode identities. It revalidates both identities
before publication.

On macOS, publication calls `renameatx_np` with `RENAME_EXCL` using the retained
parent descriptor. A destination directory, file, or symlink that appears at any
time causes an atomic refusal without replacement. Missing API support and
filesystem errors fail closed; there is no `os.replace` or ordinary-rename
fallback.

On failure the executor does not automatically recursively delete staging. This
is intentional: Darwin/POSIX offers no standard pathname removal primitive that
atomically says "remove only if this name still denotes the retained inode."
The owned staging identity is preserved and reported for audit. If the name is
missing or denotes another inode, that entry is left untouched and reported as
foreign. Automatic retry is forbidden.

## Scope still forbidden

No real CSV was read or hashed while building or testing this revision. No formal
output/staging path was created. The two frozen configs, 32/39/115 features, label
semantics, zero cross-dataset admission, and three existing exclusions are
unchanged. Materialization, splitting, sampling/balancing, encoder or model
fitting, and training remain unauthorized.
