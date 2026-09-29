# Release validation: Tasks 3 and 4 on `main` — September 28, 2026

## Verdict

**Pre-final release on `main`: Task 3 v0.3.1 (task files unchanged) and Task 4 v0.4.1.**

Every acceptance requirement that can be executed offline passes. All seven validation findings are resolved (see
[Resolutions](#resolutions-pre-final-release)).

The one medium finding, F1, was a Task 4 key inconsistency: LBBB was required while the accepted QRS allowed less than 120 ms. It
is fixed by raising that QRS floor to 120 ms, which moves one graded bound. The v0.4.0 pilot rescores unchanged at 3/10.
v0.4.1 has not been piloted.

**Scope.** The full validation below ran on a clean clone of `3316277`, the baseline. The release commit adds the resolutions and
was re-verified:
- offline suites, all passing;
- invariance/sensitivity harnesses, Task 3 21/21 and Task 4 28/28;
- free Harbor oracle, no-op and boundary checks;
- both preflights.

**Constraints observed.** The only clinical expectation changed is the F1 bound the task owner approved. `.env` was not read. No
paid model call was made.

Machine-readable manifest: `RELEASE_MANIFEST_2026_09_28.json`. Evidence, logs and scripts: `jobs/chartr/release-validation-2026-09-28/`
(gitignored).

## What was validated

| | Task 3 | Task 4 |
|---|---|---|
| Commit | `3316277` (`main` = `origin/main`), cloned fresh from GitHub | same |
| Task version | `chartr/cohort-audit` 0.3.1 | `chartr/cardiology-population-review` 0.4.0 |
| Same files as the final pilot | Yes, all task files; README differs. The shared provider changed only to add the Task 4 path | Yes, 37/37 task files except README; provider hash identical |
| Environment | New venv from `requirements.txt`: Python 3.13.5, harbor 0.23.0, anthropic 1.8.0, jsonschema 4.26.0. Docker 29.8.0 (10 CPU, 8 GB) | same |

The table above is the baseline that was fully validated. The release code commit is `19edc3b` (Task 4 v0.4.1; Task 3 task
files unchanged apart from a README note). It was re-verified as described in the verdict, and both preflights pass on it.

## Requirements-to-evidence checklist

Result key: **PASS** means an executed check passed; **LIMIT** means a documented scope limit, not a defect; **OPEN** means a finding still to resolve. Sources: `TASK3_BUILD_PROMPT.md` (T3 brief), `TASK1_MIMIC_UPGRADE.md` (T4 brief), `TASK_DESIGN_PRINCIPLES.md`, the three audits, and the task READMEs.

### Release engineering (both tasks)

| # | Requirement (source) | Evidence | Result |
|---|---|---|---|
| R1 | Reproducible from a clean checkout (user request; briefs) | Fresh GitHub clone at `3316277`. A new venv from pins, the PhysioNet fetch and all suites ran there, and the tree was still clean afterwards | PASS |
| R2 | Pinned dependencies, no `.venv` upgrade (briefs) | Top-level pins match. 7 transitive packages drifted in a fresh environment (F5). `requirements.lock.txt` now reproduces the working `.venv` exactly | PASS (F5 resolved) |
| R3 | Preflight passes only on the frozen release and fails closed (v0.3.1 audit #2; v0.3.6 audit) | Both pass on the clean checkout. Both exit 1 on wrong version, no `.git`, and a dirty task directory; Task 4 also exits 1 with Docker unreachable. `qa.test_preflight` now covers this (F6) | PASS (F6 resolved) |
| R4 | Task 1 behaviour unchanged (T3 brief) | `qa.test_clinic` 19/19 | PASS (offline only) |
| R5 | Invalid runs never scored 0 (T3 brief; adapter) | Adapter 15/15. For both tasks, a mocked API error ends as `evaluation_error` with no reward after 3 logged retries; mocked turn exhaustion scores a valid 0 | PASS |
| R6 | Private boundary holds (both briefs; audits) | For both tasks: boundary probe exit 0, no bind mounts, attested digest, snapshot frozen with 0 faults, forged snapshot ignored | PASS |

### Task 3

| # | Requirement (source) | Evidence | Result |
|---|---|---|---|
| T3.1 | Rules engine recomputes every authored answer; build reproducible (brief: validation) | `test_rules_agree…`; a fresh rebuild is byte-identical to the committed fixture, key and answers | PASS |
| T3.2 | Reference 1, no-op 0 (brief) | Offline, and Harbor oracle 1 / no-op valid 0. No-op errors (missing 34, missed 78, overclaim 54) equal the README | PASS |
| T3.3 | Wrong algorithms fail on their targets: never abstain, abstain on any gap, flag all, per-patient, received/unreceived outside records, pending as negative, latest wins, and more (brief) | `test_each_wrong_algorithm…`, 13 algorithms | PASS |
| T3.4 | Zero tolerance; absence means not_an_issue; requested candidates need an explicit item; code must match (brief: grading) | Offline test. Every single wrong decision on every candidate fails: 3,366/3,366, with that candidate the only failure. Duplicates and foreign episodes fail | PASS |
| T3.5 | Evidence must exist and belong to the patient; cross-chart rule matches `tools.md` (v0.2.0 audit #2) | `test_evidence_validity`. **Reintroducing the pre-0.2.1 rule makes it fail** | PASS |
| T3.6 | Unique accession identity (v0.2.0 audit #1) | `test_every_result_has_unique_identity_evidence`. **A reintroduced collision makes it fail** | PASS |
| T3.7 | Stage-inference charts name no stage (v0.2.0 audit #3) | `test_stage_inference…`. **An injected stage word makes it fail** | PASS |
| T3.8 | Renamed IDs leave answers unchanged (brief) | I1: every ID re-salted (0 overlap), served and graded end to end: key identical, reward 1 | PASS |
| T3.9 | Shuffled records leave answers unchanged (brief) | I2: every patient's records re-ordered (2,125 IDs, accessions and collectors changed): key identical, reward 1. Also I3: 89 patients renamed; I4: six submission-format variants | PASS |
| T3.10 | Reworded notes leave answers unchanged (brief) | N2: the key does not depend on routine note wording. Whether a *solver's* answer survives rewording cannot be tested offline (no public-record solver); the evidence is the sampled independent reviews (240/240 on 60 patients) | LIMIT |
| T3.11 | Decisive clinical changes move the answer (user request; brief: both directions) | D1–D5: pending→rejected specimen, identity conflict resolved, outside RPR received, 23-day dose gap, outside delivery record missing. In each case the build **refuses** a stale key; the updated key moves on that patient only; the old answers fail on exactly that candidate with the predicted error | PASS |
| T3.12 | Decisive facts carried only in note text (design principle 6) | N1: re-signing a dose-date correction by a clinician who did not give the injection makes the answer `cannot_determine` under the public policy; the baseline build kept `confirmed` (F4). The build now checks every F6 correction and dispute signature and **refuses N1**. Other prose-only facts rest on authoring and review | PASS for authority; LIMIT otherwise |
| T3.13 | Service contract (brief) | Recoverable 400s, freeze, linear audit, tamper detection (offline tests) | PASS |
| T3.14 | README accuracy (v0.3.1 audit #1, #4) | Three separate statements for 0.3.0/0.3.1, correct CJ4ZKQH description; all current-state counts match the artifacts (200/800/4,482; 83 confirmed; 61 CD = 41/12/8; 34 requested; 139/259 chained) | PASS |

### Task 4

| # | Requirement (source) | Evidence | Result |
|---|---|---|---|
| T4.1 | Open ODbL datasets only, fetched at build from pinned versions, checksums recorded (brief) | 446/446 files fetched and verified. The assembled database digest `01889990…` equals the baseline; a `--no-cache` service image build gives the same digest (see manifest) | PASS |
| T4.2 | Raw WFDB only; no machine measurements or interpretations reachable (brief C) | 0 comment lines in 208 served headers; public-surface test; boundary probe | PASS |
| T4.3 | Reference 1, no-op 0 (brief) | Offline, and Harbor oracle 1 (6/6 components) / no-op valid 0 | PASS |
| T4.4 | Wrong algorithms and misreadings fail (brief) | 17 algorithms, each failing named components; artifact-as-AF, missed LBBB, missed transient RBBB, remote bleed | PASS |
| T4.5 | QT decision consistent with accepted QTc (v0.3.6 P1) | Test, **caught when reintroduced**. Joint sweep: all 9 watch-list latest ECGs are required above / optional straddling or ungraded / absent below exactly as the rule says. Every automated reading on the 4 QT edits is ≥ 521 ms | PASS |
| T4.6 | Serial QTc changes consistent with accepted readings (v0.3.6 P1) | Test, **caught when reintroduced**. The audit's three counterexample pairs are now accepted | PASS |
| T4.7 | Concurrent requests atomic; audit failure is a fault (v0.3.6 P1) | Tests. **Removing the lock/transaction gives HTTP 500s; an audit failure that is not recorded escapes; both caught** | PASS |
| T4.8 | Reader rules documented per field (v0.3.6 P2) | README field table matches the key structure | PASS |
| T4.9 | Cases not separable by structure (v0.3.6 P2) | AUCs 0.46–0.70 (max note length 0.70, down from 0.835). Visit gap under 60 days: 15/18 cases vs 37/51 controls (the audit's signal was 6 vs 0). The test's threshold (\|AUC−0.5\| < 0.3) is loose | PASS |
| T4.10 | Structured fields graded within tolerance; explanations ungraded (brief) | Every range edge accepted; every accepted alternative reading (17) accepted; ungraded fields free. 469/469 single-field errors fail (1 more is rejected by the service); every removed item/interpretation fails; extras fail | PASS |
| T4.11 | Numeric tolerances consistent with categorical decisions, for every field (v0.3.6 audit recommendation) | QT and rhythm changes are consistent, and AF always accepts a null PR. LBBB was required on 104941853 while the accepted QRS went down to 101 ms (F1). v0.4.1 floors it at 120, with a new test. 11 ECGs forbid BBB while accepting QRS up to 121–134 ms; this is consistent because width alone is not a block (F2, documented) | PASS (F1, F2 resolved) |
| T4.12 | Shuffled record order leaves answers unchanged (brief) | The reference solver, which recomputes every rule from public records, scores 1 with every search result and the ECG list shuffled | PASS |
| T4.13 | Renamed IDs leave answers unchanged (brief) | New test: every patient, record and ECG ID renamed and every list shuffled; the reference still scores 1 (F3) | PASS (F3 resolved) |
| T4.14 | Decisive chart and ECG changes move the answer (user request) | Current anticoagulant added → UNTREATED_AF dropped. 10020306's AF charting removed → item dropped. INR drawn inside the window → status `completed`. QT ECG read 480 → item dropped. AF read as sinus → fails. First-degree block missed → fails. Each scores 0 against the fixed key | PASS |
| T4.15 | Superficial chart and ECG changes do not (user request) | Old stopped anticoagulant added → 1. QT reading +10 ms still inside range → 1 | PASS |
| T4.16 | Synthetic records indistinguishable from real (brief A) | Structural shape and timestamp-precision test passes. No independent reviewer attempt is recorded | LIMIT |
| T4.17 | Independent expert validation of labels (brief; v0.3.6 P2) | README states no blinded cardiologist adjudicated the labels | LIMIT |
| T4.18 | README accuracy (v0.3.6 audit) | All current-state counts match: 100/69 patients, 2,896 added resources, 5 removed, 208 ECGs (135/66/6/1) for 55 patients, 9 edits, 446 pins, 20 items on 18 patients by reason, 2 optional items, 37 + 18 interpretations, 31/4/2 rhythms, graded QRS/axis/QTc/PR 36/35/24/4, 81-word instruction | PASS |
| T4.19 | Pilot evidence preserved and shareable | The v0.4.0 job is on `task4-pilot-results` (135/135 files identical to local). My first report missed this; the docs were stale (F7) | PASS (F7 resolved) |

## Findings on the baseline, with minimal reproductions (all resolved; see Resolutions)

**F1 — medium, Task 4 key. LBBB required while the accepted QRS rules it out.** ECG 104941853 (patient 10038992) has `qrs_ms` range 101–155 and conduction `required: [LBBB]`. LBBB by standard criteria needs QRS ≥ 120 ms; `grade.py` accepts any QRS in range but fails the conduction field without LBBB.

```text
qrs_ms=110 conduction=[LBBB, 1AVB]  -> reward 1   (accepted, though self-contradictory)
qrs_ms=110 conduction=[1AVB]        -> reward 0   (consistent reading, fails conduction)
qrs_ms=130 conduction=[LBBB, 1AVB]  -> reward 1
```

Reproduce from the checkout root:

```bash
T4_BUILD=<dir with sources.sqlite and ecg/> .venv/bin/python jobs/chartr/release-validation-2026-09-28/validation/scripts/repro_lbbb_qrs.py
```

Cause: the QRS range is the M/G agreement padded by ±25 ms, while the LBBB requirement uses M and G ≥ 120 ms without padding. The effect is the same as the audit's QT P1.

Pilot impact: none; all 10 v0.4.0 runs read 120–136 ms and called LBBB.

Options for the owner (the first was chosen and applied in v0.4.1):
- raise the QRS floor to 120 wherever BBB is required;
- or accept "no BBB" when the submitted QRS is below 120.

Either needs a new version and key. The audit warned against squeezing tolerances after seeing runs; this finding comes from a key sweep, not from any run.

**F2 — low, Task 4 key.** 11 latest ECGs forbid BBB while accepting QRS up to 121–134 ms (list in `t4-metamorphic.json`). A wide QRS alone does not establish BBB, so this is weaker than F1. No run called BBB on them.

**F3 — low, Task 4 QA gap.** The brief requires renamed-ID invariance. Task 4 has no ID-renaming harness; IDs are MIMIC-derived UUIDs baked into the overlay and key. Record-order invariance is covered (T4.12).

**F4 — limit, Task 3.** The build refuses any mismatch between authored facts and the rules engine (proven by D1–D5), but it cannot see a decisive fact that exists only in rendered prose, such as who signed a correction (N1). Those facts rest on authoring and the sampled independent reviews.

**F5 — low, both.** `requirements.txt` pins harbor, anthropic and jsonschema only. A fresh install resolves litellm 1.103.0, boto3/botocore 1.43.104, uvicorn 0.54.0, filelock 4.0.5, platformdirs 4.12.1 and pyjwt 2.15.1, newer than the working `.venv`. Nothing failed; a full lock file would make the environment exactly reproducible.

**F6 — low, both.** The preflights now fail closed (verified directly: no `.git`, dirty tree, Docker down, wrong version), but no automated test guards that.

**F7 — low, Task 4 provenance (reported in error).** I first reported `jobs/chartr/task4-0.4.0-1790626310` as local-only, following `PROGRESS.md`. It was already on `task4-pilot-results` (commit `47aa226`; 135/135 files hash-identical to the local copy). Only the documentation was stale.

No blockers stopped the validation. The only interruptions were infrastructure: the tool safety check was unavailable for a period mid-session.

## Resolutions (pre-final release)

| Finding | Resolution | Verification |
|---|---|---|
| F1 | `qa/task4_interp_truth.py` floors the QRS range at 120 ms wherever a BBB is required; key regenerated with `qa/build_task4.py` (the build reproduces the committed files byte for byte before the change). The only graded change is 104941853's `qrs_ms`, 101 → 120. Task 4 bumped to 0.4.1 | New test `test_bbb_decisions_consistent_with_accepted_qrs` fails on the v0.4.0 key and passes now. The repro now rejects QRS 110 whether or not LBBB is claimed. The v0.4.0 pilot rescores 3/10, identical per run |
| F2 | No key change. A forbidden block accepting a wide QRS is consistent, because width alone does not establish a block. Documented in the Task 4 reader table and the F1 test | Joint sweep passes |
| F3 | New `test_id_renaming_and_order_do_not_change_answers` | Passes; asserts the reference only ever saw renamed IDs |
| F4 | `qa/build_task3.py` `check_rendered_corrections`: every F6 date the engine takes from a correction must be signed by the administering nurse, and every dispute by someone else | The build is byte-identical; the N1 probe is now refused; Task 3 harness 21/21 |
| F5 | `requirements.lock.txt` (94 packages, from the working `.venv`); `requirements.txt` points to it | A fresh `uv` venv from the lock freezes identically; adapter tests pass in it |
| F6 | `qa/test_preflight.py`: outside Git, wrong version, Docker unreachable | 3/3; a reverted fail-open preflight would be caught |
| F7 | Correction: the artifacts were already on `task4-pilot-results`. `PROGRESS.md` and the Task 4 README now say so | 135/135 files hash-identical |

## How to rerun (free)

From a clean clone at `3316277`:

```bash
uv venv --python 3.13 .venv && uv pip install --python .venv/bin/python -r requirements.lock.txt
```

```bash
.venv/bin/python chartr_task4/environment/service/fetch.py chartr_task4/environment/service/overlay/pinned.sha256 data/physionet
```

```bash
.venv/bin/python -m unittest qa.test_task3 qa.test_adapter qa.test_clinic qa.test_preflight
```

```bash
T4_DATA="$PWD/data/physionet" .venv/bin/python -m unittest qa.test_task4
```

Harbor oracle, no-op, boundary and mocked-adapter runs are in `validation/scripts/harbor_task.sh`. The metamorphic and mutation checks are `t3_metamorphic.py`, `t4_metamorphic.py` and `audit_mutations.py` in the same folder. None of them reads `.env` or calls the API.
