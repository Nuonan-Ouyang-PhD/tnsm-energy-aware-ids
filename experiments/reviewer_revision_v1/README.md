# Reviewer-revision implementation V1

This directory exposes the exact frozen runtime source, scheduler modules, protocol,
configuration, and validation/packaging scripts used for the R0-R4 reviewer-requested
revision campaign.

The original V1 and P0/P1 experiments were not modified or rerun. The large frozen
model/input files, generated R2 workloads, raw physical traces, and complete hash tree
are preserved in the reconstructable evidence archive under
`releases/reviewer-revision-20260909-v1/`.

The outcome boundary is intentional:

- R0 provenance/source audit: PASS.
- R1 fixed `[0.3, 0.7]` confidence-cascade campaign: 40/40 valid physical runs.
- R2 predeclared variable-load factorial: 60/60 valid physical runs.
- R3 controller-only power: not executed because the frozen artifact contained eight
  observed-support states while the protocol requested four without identifying them.
- R4A TinyDT validation-only threshold selection and one-time test evaluation: complete.
- R4B stable reference-load diagnostic: not executed because no independently specified
  stable reference-load device was available.

These files support evidence reconstruction and validation; they do not state a paper
conclusion.
