# Adaptive scheduler V1 design decisions

Date: 2026-09-07 (Australia/Melbourne)

`scheduler_experiment_v1.json` is the only executable scheduler configuration in
this directory.  It is a pre-evaluation design record, not a claim that a policy
has been trained, selected, tested, or measured in the paired physical campaign.

## Source precedence

The current reconstruction matrix fixes the Pi 4B, four-classifier pool,
100-sample/one-second windows, test replay seeds, two-window CFSM cooldown, and
40-run paired physical design.  The historical manuscript supplies only the
traceable method values explicitly retained by `policy_prerequisites.md`:
temperature smoothing 0.9, CFSM 70 C and 0.7 thresholds, Tabular-Q alpha 0.1 and
gamma 0.9, epsilon 1.0 to 0.01, 1000 episodes, DQN hidden width 64 and batch 32,
and reward weights `[0.5, 0.2, 0.2, 0.1]`.  Its Pi 3 setup, old classifier shape,
oracle claims, and result tables are not reused.

The requested `docs/REPRODUCTION_MATRIX.md` is absent from this reconstructed
working tree.  The configuration records the hash and absolute path of the
traceable source-repository copy that was read.  It is not copied or edited.

## Causality and leakage boundary

Before choosing action `a_t`, code may see only the current pre-action kernel
temperature and queue depth, the previous completed window's selected-model
mean attack probability and arrival count, and the previous action.  Current or
future labels, phase IDs, and prediction caches are forbidden.  In particular,
the evaluator commits the action before it asks the outcome provider for that
model's result.

Policy updates use `train` records only.  Empirical normalization/calibration is
a distinct `calibration` role.  Checkpoint selection uses `validation` only.
`test` labels are accepted only by a second posthoc pass after a frozen schedule
has completed.  The CLI rejects labels embedded in an online test trace.

The already prepared compact train/validation NPZ files contain labels and four
prediction columns but no online telemetry.  Their adapter never reads the
`analysis_only_phase_ids` member.  If optional telemetry members are absent it
uses the dated, neutral, label-independent values recorded in the configuration:
35 C, empty 100-sample queue, and 100 arrivals/window.  Those values are not
presented as measured window telemetry, and training under them cannot support a
thermal-, queue-, or load-adaptation claim.  A physical runtime must supply live
signals instead.

## Newly fixed choices

The sources did not specify numeric state bins, the exact threat aggregate,
complete CFSM transition priority, exact detection reward, reward
normalizations, complete DQN optimization settings, scheduler train/validation
seeds, or checkpoint selection.  Those values are explicitly listed under
`explicit_design_choices_made_2026_09_07`; none is represented as a historical
decision.

CFSM is a fixed rule baseline and is never trained.  A switch at window `t`
locks the next two complete windows, so the earliest ordinary next switch is
`t+3`.  A 70 C thermal condition may force an immediate one-rank lighter action
despite cooldown.  Queue and load are intentionally unused by CFSM but remain
available to the two RL baselines.

The comparison formerly called an oracle is implemented as the
**Label-Informed Per-Window Utility Reference**.  It selects the best scalar
utility independently after each window using labels and all four outcomes.  It
does not optimize a trajectory, model switching, or future thermal dynamics, is
not deployable, and is not described as globally optimal.

## Cost boundary

The configuration binds the completed TON-IoT static-profile means.  These are
whole-Pi, load-side USB measurements at one 100-row encoded batch per second
with all models resident.  A training trace may identify them only as a static
profile lookup proxy.  They are not current-window measured energy, do not
establish CIC-IoT2023 or N-BaIoT power, and do not supply unmeasured switch or
first-batch response.  Every window log carries a cost-origin field so those
categories cannot be silently conflated.

## Execution boundary

The software CLI supports configuration validation, Tabular-Q/DQN training,
policy freezing, frozen software evaluation, fixed CFSM evaluation, and the
separate offline label-informed reference.  Formal held-out evaluation and
physical execution are deliberate later actions; creating this infrastructure
does not run or authorize either.
