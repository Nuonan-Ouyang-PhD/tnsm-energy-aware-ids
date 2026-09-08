# Implementation and boundaries

## Authorization gate

The command-line entry point only executes when all of the following are supplied
and mutually consistent:

1. `--execute`;
2. a JSON record whose kind is `materialization_execution_authorization` and whose
   user-authorization value is exactly `true`;
3. the accepted request ZIP at its frozen SHA-256;
4. the reviewed executor-evidence ZIP, whose SHA-256 is repeated in the
   authorization record;
5. an append-only `DECISIONS.md` entry containing the authorization ID, contract
   ID, request ZIP hash, executor-evidence ZIP hash, and exact output root;
6. exactly three source-root arguments.

All of these checks occur before source roots are inspected. `--show-contract` is
the only non-executing mode. This package contains no authorization record.

## Deterministic transformation

The executor excludes the N-BaIoT zero-row structure demonstration before sort
and numbering. Remaining inventory entries are ordered by the UTF-8 bytes of the
relative path within each dataset; ordinals restart at 1 and use four decimal
digits. Shard IDs append the first 16 hexadecimal characters of the frozen source
SHA-256.

CSV cells remain parsed strings. No trimming, numeric parsing, case conversion,
normalization, missing-value replacement, encoding, or fitting occurs. Output is
UTF-8 without BOM, LF-terminated, comma-delimited, and minimally quoted. Binary
labels remain the literal strings `benign` and `attack`. TON-IoT and CICIoT2023
write an empty `source_family` CSV cell. Unavailable TON-IoT/CIC JSON metadata is
JSON `null`; N-BaIoT `capture_id` is the ordered three-string array
`[device_id, source_family, source_subtype]`.

The source contract requires one physical LF-terminated line per CSV record and
rejects quoted multiline records. The three frozen CICIoT2023 exclusions must
match every registered identity field and remain final physical lines.

## Failure and publication boundary

Output and staging are distinct absent siblings under one existing parent. The
executor refuses pre-existing output or staging, checks minimum free space before
source preflight, enforces a cumulative byte cap before every output write, and
checks the scratch reserve after each feature/label shard pair. It never retries
automatically.

Only an exact staging directory created by the current process is eligible for
cleanup. All source identities are checked before that directory is created. The
final tree is published through one same-parent `os.replace` only after count,
label-total, replay, root-manifest, and complete bound-metadata revalidation.

## Synthetic evidence

The fixtures are invented small files that exercise:

- TON-IoT column exclusion, label mapping, empty family cells, commas, whitespace,
  numeric lexical forms, and missing cells;
- CICIoT2023 benign/attack mapping and the three exact malformed-final-row cases;
- N-BaIoT zero-row exclusion, benign/attack metadata, and capture arrays;
- exact static expected feature/label output bytes;
- full-tree reproducibility across independent runs;
- authorization-first denial, wrong source identity, unexpected labels,
  unregistered malformed rows, insufficient space, hard-cap failure, no-clobber,
  contained cleanup, and injected failure;
- direct rejection of the four previously under-covered mutations: identical
  output/staging, reversed TON binary labels, wrong CIC inventory SHA-256, and a
  missing `source_subtype` sidecar column.

No test points to or discovers the real dataset roots.

## Work still requiring a later decision

- identify the actual mounted-volume path;
- choose and review the exact new-volume output/staging sibling paths;
- verify capacity and filesystem behavior on that volume;
- rebuild and independently review the re-bound executor evidence package;
- only then consider a separate materialization-only execution authorization.

Splitting, sampling/balancing, encoder fitting, model fitting, and training remain
outside this implementation and forbidden.
