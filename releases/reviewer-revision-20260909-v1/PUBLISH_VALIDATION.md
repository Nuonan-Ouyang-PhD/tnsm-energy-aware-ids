# GitHub publication validation

Publication preparation was performed from the final evidence archive without
re-running any experiment.

- Source archive bytes: 327,666,190.
- Source archive SHA-256: `845ced5c96f932ee8d3509e2effcb39870a2fb9995bad9a6fe524f6c60b270e4`.
- Split layout: three 80 MiB parts plus one final part; every part is below GitHub's
  ordinary 100 MB single-file limit.
- Lexically ordered part reassembly: 327,666,190 bytes and the exact source archive
  SHA-256 above.
- Archive inspection before publication: 1,912 entries, 1,911/1,911 manifest matches,
  CRC PASS, zero duplicate member names, zero unsafe paths, and zero symlinks.
- Repository test suite at publication commit preparation: 230/230 PASS.
- Credential-pattern scan over the browsable source/evidence files: no private-key,
  classic GitHub token, or fine-grained GitHub token pattern found.

This records local publication validation only; it is not a claim about a GitHub-hosted
CI run.
