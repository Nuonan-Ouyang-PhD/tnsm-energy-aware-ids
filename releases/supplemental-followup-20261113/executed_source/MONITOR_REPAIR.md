# Monitor cadence recovery

The failed attempt is `supp02-b05-p6-ConfidenceCascade_0p3_0p7-idle`.
Its monitor failed before the first idle sample; it is not accepted evidence.
The preceding 29 accepted formal pairs and all original logs remain unchanged.

The old monitor read a snapshot, scanned /proc, collected thermal/throttle
telemetry, serialized/emitted both process snapshots, and then waited another
fixed second. These processing costs are therefore added to each sampling period.
The last successful snapshot had monotonic=916730.59170883 and its event was
emitted at epoch=1794530513.288624. With the preceding samples' clock relation,
this is approximately 0.7 seconds of processing after accounting acquisition.
This supports accumulated monitoring overhead as the failure mechanism.

The old failure path did not emit the rejected right-hand snapshot. Consequently
the exact rejected interval length and which sub-operation consumed its time
cannot be reconstructed. Do not claim proof of an exact OS scheduling cause or
that all interval overruns were impossible external interference.

The only worker change waits until last_actual_sample_time + 1 second instead
of waiting an extra second after processing. It also emits both snapshots when
rejecting a >1.5-second gap. Actual gaps >1.5 still reject. External CPU accounting,
the 5% limit, heartbeat/temperature/disk/voltage requirements, inference, model
selection, workload and all training artifacts are unchanged. New runtime and
derived lock are separate; original runtime and lock are preserved.

The 36 existing regressions pass. Evaluation of the actual worker wait expression
with 0.1/0.7/1.2 seconds of prior processing yields waits 0.9/0.3/0 seconds, not
an additional full second. Hardware warm-input gate is separately recorded and
is required before continuing the 31 remaining formal pairs.

Block 5 is now a second cross-period recovered block. Retain the previously
registered all-valid-block and exclude-block-1 analyses; additionally report
exclusion of all recovered blocks {1,5}, without choosing by outcomes. This is
an added disclosure/sensitivity analysis, not a change to accepted-run criteria.
