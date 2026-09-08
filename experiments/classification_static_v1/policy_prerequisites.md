# Adaptive scheduler and physical study prerequisites

The current repository reproduction matrix is the authority for the Pi 4B,
four-classifier pool, ten replay seeds, two-window CFSM cooldown, 40 sequential
paired physical runs, and fifteen half-hour idle/model profiles.

Read-only inspection also found the historical manuscript source:
`/Volumes/RESEARCH_DATA/10_PROJECTS/COMPLETE_RESEARCH_BY_SOURCE_PATH/Downloads/TNSM_revised_manuscript_source_reference_checked_with_template_response (1)/main.tex`.
Its method section specifies lagged threat context, temperature smoothing .9,
CFSM warning temperature 70 C and threat threshold .7, Tabular-Q alpha=.1,
gamma=.9, epsilon 1 to .01, 1000 episodes, DQN hidden width 64/batch 32, and
reward weights [.5,.2,.2,.1] for detection, measured power, measured latency and
thermal increment. Its Pi 3 hardware and historical result tables are NOT
reused as evidence. Where it conflicts, the current Pi 4B reconstruction matrix
takes precedence, including the newer 64/32/16 classifier MLP.

The manuscript does not fix numeric low/medium/high state bins, exact threat
aggregation, complete DQN optimizer/target-update schedule, thermal normalization,
or the empirical cost registry for this actual Pi 4B. These must be recorded
before fitting/evaluating adaptive policies. Local software verification may
use explicitly synthetic values but cannot fill a physical registry with them.

Physical checks performed during this task: pi4b8g resolves and SSH succeeds;
model is Pi 4B Rev 1.5, aarch64, NTP synchronized, temperature 30.6 C and
get_throttled=0x0 at the first check. USB enumeration shows only root buses and
the VIA hub, and no serial-by-id device was returned. This does not rule out a
Bluetooth meter or a meter logging on the Mac; its actual interface is still
needed. A fuller read-only snapshot is in execution/pi_readonly_snapshot.json.

The user has been asked only for the actual meter model/connection/export
interface, not for another permission. Until an interface is identified and
the recorded calibration exists, no energy-based training, energy oracle,
power-saving table, or finished physical campaign will be claimed. Continue
all independent data preparation/classifier/cache/replay work meanwhile.

The ten static replay seeds quantify workload-draw variation conditional on the
fixed model seed 11 and fixed split. They are not ten independently trained
model sets, independent raw traffic acquisitions, or independent hardware units.
