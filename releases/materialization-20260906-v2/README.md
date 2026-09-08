# Materialization audit chain

This directory preserves the request, executor review iterations, output-path rebind,
final authorization, failed first run, and validated successful materialization run.

The successful run is `evidence/materialization_run_v2/`. The earlier failure is retained
under `evidence/materialization_run_v1/`; it is not silently removed or presented as a
successful run. Source CSV files and the large materialized output tree are not stored in Git.
The evidence records their frozen inventories, hashes, lineage, row counts, and output manifests.
