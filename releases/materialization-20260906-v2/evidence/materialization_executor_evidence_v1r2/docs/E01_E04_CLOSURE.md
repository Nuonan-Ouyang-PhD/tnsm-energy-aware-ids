# E01–E04 closure matrix

| Finding | Implemented control | Synthetic regression evidence |
| --- | --- | --- |
| E01: approved ZIP did not bind the executed working copy | Validate the real ZIP and MANIFEST without extraction; byte-compare the actual contract, executor, and eight runtime metadata files; use the archive contract snapshot | Positive real-ZIP CLI control; contract semantic drift, whitespace-only contract drift, executor comment drift, and frozen runtime-input drift all refuse before a nonexistent source trap is inspected |
| E02: replay bypassed storage controls | Shared serializer writes replay bytes only to incremental digest/count sinks; no replay directory or retained buffer; scratch checks cover every replay shard | Large invented-field capacity model completes with staging peak no larger than final output and no `.replay-*` path |
| E03a: zero-row structure file skipped identity validation | Preflight every inventory entry, then require the single structure item and scan to remain zero-row/well-formed before exclusion | Unbound append fails size/hash identity; freshly rebound nonzero structure file still fails the structural invariant |
| E03b: LF contract conflicted with frozen exceptions | Require LF normally; allow only three exact registered malformed final rows with `ends_with_newline=false`; recheck during render/replay | Ordinary LF succeeds; ordinary rebound no-LF fails; three registered no-LF rows succeed; unregistered malformed row and rebound registered-LF entry fail |
| E04a: late output could be replaced | Darwin `renameatx_np(RENAME_EXCL)` via retained parent descriptor; unsupported operation fails closed | Late empty directory, nonempty directory with sentinel, regular file, and symlink are all preserved and refused |
| E04b: substituted staging could be deleted | Retain parent/staging device+inode; remove automatic pathname cleanup entirely; preserve and report failed or foreign staging | Displaced owned staging and replacement directory with foreign sentinel both remain; ordinary injected failure retains owned staging and unrelated neighbor |

All tests use invented fixtures and temporary directories. They are not execution
authorization records and do not access the real datasets or formal output roots.
