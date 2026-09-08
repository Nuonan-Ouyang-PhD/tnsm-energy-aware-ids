# TNSM experiment continuation — fixed before model outcomes

Authority: user “继续 你直接完成全部所有的实验不需要经过我”.
This authorizes subsequent stages without repeated approval requests. Accepted
feature/label semantics and raw input bytes are preserved. This new plan fills
previously unspecified software-experiment details explicitly; it is not claimed
to have been specified or externally reviewed in the earlier protocol packages.

## Dependencies and scope

Start only after verified materialization publication. Use its 399 feature/label
pairs; binary classification only, separate native model per dataset. Four model
families and scenario sizes follow docs/REPRODUCTION_MATRIX.md. No cross-dataset
core or pooling. First model seed is 11; fixed trace seeds are
11,23,37,53,71,89,107,131,157,191. No test-driven hyperparameter tuning.

## Group split, fixed seed 11

TON uses unordered source/destination IP pairs, SHA256("11|" + sorted IPs joined
by "|"), integer first 16 hex modulo 100: train <60, validation <80, test else.
IPs are used only to assign groups and never supplied as features. This is pair
isolation, not host isolation; that limit must appear in results.

CIC groups entire capture CSV files, stratified by category. Sort captures by
SHA256("11|"+relative path); allocate approximately 60/20/20, at least one to
each split when at least three captures exist. A category with fewer than three
captures stays train-only and is explicitly reported as uncovered by holdout.

N-BaIoT groups entire devices, sorted by SHA256("11|"+device): first five train,
next two validation, final two test. Capture files never cross device splits.
Fix assignments before fitting; report group IDs and all membership counts.

## Equal upper-bound training budget and held-out pools

Use at most 200,000 uniformly selected rows without replacement from the train
partition per dataset, 100,000 validation, 100,000 test. If fewer rows exist, use
all. Seed 11 determines row positions independently of values/labels. This is a
declared downstream training/evaluation budget, not a change to full raw
materialization. Report actual counts and natural class proportions. No class
balancing, replication or oversampling during classifier fitting.

To prevent exact feature-vector leakage within these selected pools, canonical
parsed feature vectors are SHA256-keyed. Remove validation rows identical to
selected training rows; remove test rows identical to selected train/retained
validation rows. Report removed rows and any conflicting labels. This protects
the evaluated pools, not a claim of exhaustive deduplication of all 54M rows.
Keep duplicate rows within one split; do not hide loss of holdout coverage.

## Train-only preprocessing and classifiers

Numeric text: fixed T/True/true -> 1, F/False/false -> 0. Non-numeric or nonfinite
values become missing in the derived model input, with counts reported. Fit
median imputation and standard scaling only on training; retain all-empty
numeric columns. TEN frozen TON categorical columns use train-only one-hot
encoding, minimum frequency 5, maximum 128 categories/column, unknown ignored
or assigned to an existing infrequent bin. Raw/native CSVs remain unchanged.

TinyDT depth=6,min_split=20,min_leaf=10. LightLR L2,C=1,liblinear,max_iter=1000.
MedRF trees=25,depth=10,min_split=10,min_leaf=5,n_jobs=2. HeavyMLP widths=64/32/16,
ReLU,dropout=.2,Adam lr=.001,batch=1024,30 epochs,BCEWithLogitsLoss. CPU execution
with two Torch threads and deterministic algorithms; seed=11. No validation
early stopping or test-based model selection. All four use the same encoded
training rows within a dataset. Prediction threshold=0.5.

Report held-out accuracy, balanced accuracy, precision, recall, F1, ROC-AUC,
average precision, confusion counts and raw prediction caches, row IDs and
feature digests. Validation/test encoders are never fitted separately.

## Replay and physical prerequisites

Stationary: 3 datasets ×10 seeds ×200 windows ×100 rows. Five-phase drift:
TON/CIC ×10 seeds ×500 windows ×100 rows, exact phase lengths and ratios from
the existing template. If a binary pool is too small for the requested trace,
sampling with replacement is explicitly flagged along with unique-row counts;
rows never cross splits and each method receives the same trace. This is
controlled workload replay, not newly acquired traffic.

CFSM/Tabular-Q/DQN require a concrete state/reward/cost registry before policy
fitting. Existing repository drafts do not supply it. In particular, missing
power measurements cannot be replaced by an invented energy model. Physical
40-run paired study and 15 half-hour profiles require an actual logging meter,
wiring identity and export interface; read-only checks show the intended Pi is
reachable, but no meter interface has yet been identified. Continue independent
classification/cache work while resolving these dependencies. No energy-saving
or completed-formal-campaign claim is permitted without those measurements.
