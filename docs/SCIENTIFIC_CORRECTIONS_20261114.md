# Scientific corrections and interpretation boundary

Historical bytes, original results and failures remain archived. Corrections do
not retrospectively convert an earlier implementation into the corrected one.

* Historical R2 formed queue observations after appending arrivals and used a
  hard-coded normalization; RL used lagged arrivals while DeadlineGuard used
  current arrivals. The resulting TinyDT behavior is not a fair test of the
  corrected common-interface policies' load generalization.
* Fifteen historical minus-temperature/queue/arrival ablations removed constant
  training coordinates. They do not establish robustness to changing those inputs.
* Historical action-independent temperature proxies do not measure model-caused
  heating; training/descriptive reward conventions also differed. The corrected
  follow-up has no thermal reward or thermal-control claim.
* Historical DQN block 4 has suspected external-load interference, without the
  later process-aware gate. Keep the observation and uncertainty; do not identify
  a CPU joule contribution from timing or silently delete the block.
* The reward criterion is an immediate pairwise utility comparison for specified
  costs/support, not a theorem of long-horizon policy collapse or global LightLR
  optimality. TinyDT-favouring windows preclude that universal claim. The audit
  is retrospective, not proof that test results were unseen.

## Corrected follow-up

The new state uses current scheduled arrivals, raw FIFO carryover BEFORE current
arrivals, prior selected-detector threat and prior action. Temperature is safety
telemetry. Shared information does not imply identical computation: Cascade
observes current-row LightLR confidence AFTER entry inference, unlike pre-window
RL action commitment. DeadlineGuard uses fixed calibrated MedRF p95 service cost.
Training adds deadline/backlog penalties but the fixed simulator never develops
backlog; queue competence is therefore unidentifiable. Historical TON power is a
training proxy, not new measured costs for three datasets.

All 60 accepted runs in ten blocks are retained. Q/DQN and Static-LightLR use
LightLR throughout; DeadlineGuard and Static-MedRF use MedRF throughout. All
methods have zero recorded deadline-miss windows in this follow-up. Hence the old
43.7-J/512-miss DeadlineGuard switching narrative is NOT the new study's result.
No equivalence follows from RL/static energy CIs crossing zero.

Block 1 spans the first external-load interruption; block 5 spans monitor-gap
recovery. The first failure coincides with man-db maintenance. The second supports
a monitor-overhead mechanism, but its rejected right snapshot was not saved, so
the exact gap and sub-operation cannot be recovered. The new instrument changes
only wait cadence and rejected-gap logging, retaining 1.5 s and 5% gates.

Report all valid blocks, exclusion of block 1, and exclusion of blocks 1 and 5;
for each report raw and preceding-idle-adjusted endpoints. Preserve actual
registration timestamps. No result-driven selection, imputation, historical
pooling, retraining, threshold change or new measurement is permitted here.

## Acceptance status

Author-side validation reports 197,922 checks and a separate 12.5-million-transition
sequence audit. These are not independent acceptance. Independent byte-level/raw
log review remains incomplete because the review environment could not open ZIPs.
The manuscript and response are working drafts, not a certified submission release.
