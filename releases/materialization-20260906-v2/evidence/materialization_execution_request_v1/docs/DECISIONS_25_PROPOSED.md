# Proposed DECISIONS.md entry — not installed, not authorized

The following is review text only. It must not be appended until the user has
independently accepted the exact request package and explicitly authorized the
materialization gate. Placeholders must be replaced with observed values.

> 25. MATERIALIZATION ONLY AUTHORIZED under
>     `MATERIALIZATION-20260906-V1-PROPOSED`. Authorization binds the accepted
>     `MATERIALIZATION_EXECUTION_REQUEST_V1.zip`, SHA-256
>     `<accepted-request-zip-sha256>`, and the unchanged frozen protocol
>     `FEATURE-POLICY-20260905-V1-FROZEN`. It covers one deterministic
>     materialization pass over the three exact bundled inventories into the
>     fixed output root stated by the request, including its preflight,
>     validation replay, atomic publication, and scoped staging cleanup on
>     failure. It does not authorize splitting, sampling, balancing, encoder
>     fitting, model fitting, training, a new acquisition, a config change, or
>     a changed output location. The materialization executor and guards must
>     match the accepted request; authorization fails closed if the storage
>     minimum or any input identity check fails. Authorized by the user at
>     `<authorization-time-utc>` after independent request acceptance
>     `<acceptance-reference>`.

Until that entry is installed with real values following explicit user action,
`authorization_granted=false` and `data_gate_unlocked=false`.
