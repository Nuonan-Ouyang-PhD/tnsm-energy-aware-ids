# Preparation tests, not formal profile data

Seven local tests cover the read-only packet command, signed units, stale/corrupt
responses, voltage/current guards, actual-interval integration, missing-sample
rejection and the Pi heartbeat-loss guard.

The initial clock-check prototype included SSH process startup in the latency
bound, producing offset intervals about[0.047,0.379]s; no profile was started.
It was replaced before collection by five ping/response measurements on one
already-established connection, retaining the <=0.25s bound rather than loosening
it. Remote/publication artifacts and model choices were not changed by this fix.
