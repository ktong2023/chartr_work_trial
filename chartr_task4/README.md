# chartr_task4 — cardiology population review on real data (v0.4.1)

The agent reviews a 100-patient clinic population (69 living) at 2026-09-24 12:00 America/New_York. It must save:
- a **review item** for every issue that needs clinical review;
- a **structured interpretation** of every living patient's most recent ECG: rhythm, rate, intervals, axis, conduction,
  and changes from that patient's previous ECG.

The population is the MIMIC-IV Clinical Database Demo on FHIR. The ECGs are the MIMIC-IV-ECG Demo (12-lead, 10 s,
500 Hz WFDB). Both are re-dated per patient and extended with a synthetic outpatient cardiology layer. The target is an
Opus 5 pass rate of 2–7/10, where failures are genuine reasoning or ECG-reading errors.

## Final confirmation protocol (fixed September 28, 2026, before any confirmation trial)

This batch confirms the pre-final release. Nothing in this section changes once the batch has started. Running it makes paid
model calls and needs the user's authorization.

**Frozen configuration**

| | |
|---|---|
| Frozen commit | `19edc3b` on `main`. The checkout may be a later `main` commit only if no evaluated file differs from `19edc3b` (step 2); only READMEs, `PROGRESS.md` and reports may change |
| Task | `chartr/cardiology-population-review` **0.4.1** (`task.toml`, service `chartr-task4-0.4.1`, baseline) |
| Answer key | `tests/expected.json` sha256 `821026182ca945b8a58f320f8741d0bbea4f8c2db52d85314cfd71fd8ba535e0` |
| Sources | digest `01889990daf1e991493c77348eaa0c7cbf4afd3e983ecba113eb4a78f89bd06b`, attested by the provider at every trial start; PhysioNet inputs pinned in `overlay/pinned.sha256` (446 files) |
| Harness | adapter 0.4.0 (`anthropic_agent.py` sha256 `95ce935a…3ead`), provider `chartr_environment.py`, Harbor 0.23.0, anthropic 1.8.0; host environment from `requirements.lock.txt` |
| Model and budgets | `claude-opus-5`; `-k 10 -n 10`; `max_turns=300`, `max_tokens=64000`, `api_timeout_sec=1800`, `wall_timeout_sec=7000`, `tool_timeout_sec=900`, `prompt_cache=true` |
| Host | Docker with ≥ 10 CPUs and 8 GB; no other ChartR trial running; `caffeinate` so the host cannot sleep |

**Exact commands** (bash, from the repository root)

1. Update the checkout: `git fetch origin && git checkout main && git pull --ff-only`
2. Frozen files unchanged (must print `frozen-files-ok`):
   ```bash
   git diff --quiet 19edc3b HEAD -- chartr_task4 ':(exclude)chartr_task4/README.md' anthropic_agent.py chartr_environment.py chartr_job.yaml requirements.lock.txt && echo frozen-files-ok
   ```
3. Preflight (every line must be `ok`): `python3 qa/task4_preflight.py 0.4.1`
4. Create the batch's unique output directory. It is never reused; the command refuses an existing path and records the
   dispatch state:
   ```bash
   D="$PWD/jobs/chartr/confirm-task4-0.4.1-$(date -u +%Y%m%dT%H%M%SZ)"; test ! -e "$D" && mkdir -p "$D" && { git rev-parse HEAD; python3 qa/task4_preflight.py 0.4.1; } > "$D/DISPATCH.txt" && echo "$D"
   ```
5. Run the batch (job name `batch`):
   ```bash
   caffeinate -dims env PYTHONPATH="$PWD" .venv/bin/harbor run -c chartr_job.yaml -p chartr_task4 -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 10 -n 10 --ak max_turns=300 --ak max_tokens=64000 --ak api_timeout_sec=1800 --ak wall_timeout_sec=7000 --ak tool_timeout_sec=900 --ak prompt_cache=true --env-file .env --job-name batch --jobs-dir "$D"
   ```
6. Score: `python3 qa/confirm_summary.py chartr_task4 "$D"`. If it reports `INCOMPLETE`, rerun the same command with
   `-k N -n N`, where N is the number of missing valid attempts. Use the next unused job name (`rerun-1`, `rerun-2`, …) in the
   same `$D`, then score again.
7. Write `$D/TRIAGE.md`, then commit `$D` to the `task4-pilot-results` branch.

**Counting rules** (applied by `qa/confirm_summary.py`)

- **Headline:** passes among the first 10 valid attempts, in start order. The 2–7 of 10 target is judged on this number alone.
  It is reported whatever it is, and no further batch is run to reach the target.
- **Invalid attempts** get no reward and are not attempts: API or adapter errors, cancellation, service faults, and evidence or
  integrity failures. Report them and rerun under the same command (step 6) until there are 10 valid attempts.
  - If one job has 3 or more invalid attempts, stop and fix the infrastructure without touching frozen files.
  - If a frozen file must change, the batch is void.
- **Budget failures:** valid attempts that end on output truncation, turn, wall or tool timeout, or context exhaustion count as
  failures in the headline. They are also listed as a separate category.
- **Provenance:** every trial's manifest must match the frozen task files (README excepted), provider, adapter, model and
  budgets. One mismatch voids the batch; the script exits 1.
- **Triage:** classify each failure from its saved items and trace as a model failure, a task/grader defect, or a budget
  failure.
  - A defect is fixed in a new version and reported separately.
  - This batch is never re-scored, and it is not pooled with earlier batches (the v0.4.0 3/10 stays a pilot result).

## Data and licence

- MIMIC-IV Clinical Database Demo on FHIR v2.1.0 and MIMIC-IV-ECG Demo v0.1 (PhysioNet), Open Data Commons Open Database
  License v1.0. They are fetched at image build time from the pinned PhysioNet versions, with every file checked against
  `environment/service/overlay/pinned.sha256` (446 files).
- The machine measurements of MIMIC-IV-ECG v1.0 (open access, ODbL) served only as one ECG reader when labelling. They are
  not shipped and are not seen by the agent.
- No credentialed PhysioNet data is used. This is a derived database and is not for clinical use.

## What the agent sees

- `instruction.md` (81 words), `/app/policy.md` and `/app/tools.md`.
  - The policy names the categories and the guideline.
  - `tools.md` defines each field and vocabulary. For example, the axis categories are given in degrees, and `qtc_ms` is
    defined as Bazett-corrected.
- Every operational rule is in dated clinic memos inside the chart: the QT watch list and the 500 ms threshold,
  ECG-after-start windows with the start dates each applies to, INR after dose changes, and who may change warfarin doses.
- Nothing tells the agent how to read an ECG. It gets raw WFDB records and pinned analysis libraries (numpy, scipy, wfdb,
  neurokit2).

## Build and assembly

- `qa/build_task4.py` (private) writes `environment/service/overlay/`. The overlay holds:
  - per-patient day offsets;
  - 5 removed Condition records (AF codes for two patients, and one acute coagulopathy code);
  - 2,896 added FHIR resources cloned from real record shapes;
  - the 208-ECG catalog for 55 patients;
  - int32 sample deltas for 9 edited ECGs.
- `environment/service/assemble.py` rebuilds `/data/sources.sqlite` and `/data/ecg` deterministically. The content digest
  is pinned in `tests/baseline.json`.
- Re-anchoring moves each patient by whole weeks close to whole years, so weekday and season are preserved.
- **Every living patient gets the same generated outpatient layer**, so cases do not stand out:
  - visits, including short return visits;
  - medication changes;
  - labs;
  - progress notes with optional routine free text;
  - nurse and pharmacist calls;
  - occasional outside-records summaries.

  Cases differ only in their clinical content.

### ECG catalog and edits

- The catalog holds the readable tracings: 135 normal-rhythm, 66 AF, 6 prolonged-QT (5 edited, 1 real) and 1 paced.
- Five harder tracings were added after 12-lead designer review:
  - sinus tachycardia with first-degree AV block and LBBB, then ventricular pacing;
  - two LBBB tracings;
  - a rate-related RBBB that resolves the same day.
- Candidate flutters were rejected because flutter waves could not be confirmed.
- **QT edits** time-warp the low-frequency J-point-to-T-end segment, keep the original high-frequency noise, and take the
  extra time from the T–P segment.
  - The four current QT edits target QTc 570–615 ms.
  - For each of them, every agreeing automated reading is at least 520 ms. The accepted range (agreeing readings ±20 ms)
    therefore never crosses the 500 ms review threshold.
  - The older look-alike keeps a 505 ms floor, because no decision rests on it.
- **Artifacts** are added to four tracings: EMG noise, baseline wander (two tracings) and LA/RA reversal.

### How ECG answers are set (actual rules per field)

The labels come from three automated readers plus designer review. It is not uniform three-reader agreement:

| Reader | What it is |
|---|---|
| M | The cart's own statements and intervals (MIMIC-IV-ECG v1.0 machine measurements) |
| N | neurokit2 DWT delineation on lead II |
| G | An in-house 12-lead median-beat method. It shares neurokit2's lead-II R-peak detection, so it is not fully independent of N |

| Field | Rule |
|---|---|
| Rhythm | Catalog label: the cart statement plus RR irregularity from two algorithms. Tracings that designer review could not settle accept several rhythms: 108780865 AF/sinus; 100924231 sinus/flutter/ectopic atrial; any "sinus or ectopic atrial" cart statement sinus/other. |
| Rate | All reads ±5 bpm (AF ±12). |
| QRS | M and G within 30 ms, then accepted range ±25 ms, floored at 120 ms where a bundle-branch block is required (v0.4.1). N's QRS is excluded: validated against M it runs +48 to +66 ms (median), from the DWT R-offset convention. |
| QTc (Bazett) | Anchored on M and N (both required, within 50 ms). The tangent (A) and G reads are admitted if within 60 ms of the anchors. Accepted range ±40 ms (inter-observer variability). Otherwise ungraded. QT edits use their own agreeing-read range. |
| PR | Numeric PR is not graded, because onset conventions differ by 30–50 ms. It must be null in AF. |
| First-degree AV block | Required only if the cart states it with PR ≥ 210 ms and a second reader agrees. Forbidden only if M and N, and G when it found a P wave, all read ≤ 160 ms. Otherwise allowed. |
| Bundle-branch block | Required only if the cart statement, G's morphology, and QRS ≥ 120 ms from both M and G all agree. Forbidden if both QRS reads are < 110 ms. Otherwise allowed. A forbidden block may still accept QRS ≥ 120 ms, because width alone does not establish a block. |
| Axis | One category if M and G agree ≥ 10° from a boundary. Neighbouring categories if near a boundary. Ungraded if M and G differ by more than 40° (indeterminate). |
| Changes | Rhythm and BBB changes are required only if true under every accepted reading of both ECGs. QTc ±60 ms changes use the same padded ranges as the QTc fields, so any pair of accepted readings implies an accepted change set. No QTc change is currently required. |

No blinded cardiologist adjudicated these labels. The ECG IDs whose rhythm was set by designer review are listed in
`qa/task4_interp_truth.py`.

## Answers (v0.4.0)

**20 review items on 18 patients:**
- UNTREATED_AF ×4. Two are code-based; for 10004235 and 10020306, AF appears in notes, an older ECG or inpatient rhythm
  charting, but not in diagnosis codes.
- ANTICOAGULANT_WITH_CONTRAINDICATION ×1.
- DUAL_ANTICOAGULATION ×1.
- RHYTHM_DOCUMENTATION_CONFLICT ×1.
- PROLONGED_QTC_ON_WATCH_LIST_DRUG ×4. One of these (10013049) has a note calling the QT "acceptable".
- ECG_AFTER_WATCH_LIST_START ×7, covering memo applicability by start date, an unreceived outside ECG, and inpatient starts.
- INR_AFTER_WARFARIN_DOSE_CHANGE ×2.

**Two optional QT items (neither required nor penalized).** Two watch-list patients' latest ECGs are artifact tracings
with ungraded QTc: 10018423 (LA/RA reversal) and 10019385 (baseline wander).

**37 required interpretations**, one per living patient with ECGs; 18 deceased patients' latest ECGs are optional.
- Rhythm: 31 sinus, 4 AF, 2 with several accepted readings.
- Required comparisons: new AF ×2, resolved AF ×2, and one resolved RBBB.
- Required conduction: one LBBB and one first-degree AV block.
- Graded fields: rhythm, rate and conduction on all 37; QRS on 36; axis on 35; QTc on 24; PR (null in AF) on 4.

**Look-alikes that must not be flagged:**
- a remote bleed;
- a clean anticoagulant switch;
- a nurse call about an extra tablet;
- routine pharmacist INR calls and refills;
- an older long-QT ECG followed by a normal one;
- sinus rhythm documented in paroxysmal AF;
- a watch-list start before any memo applied;
- deceased patients;
- inpatient watch-list orders.

## Grading (`tests/grade.py`)

The grader only accepts evidence collected by the controller. It checks attestation, the baseline digest, freezing,
audit continuity and zero service faults; invalid runs get no reward. The components are identification, item_fields,
ecg_interpretation, ecg_comparison, ecg_linkage and chart_rules, and all must pass.

Scope:
- Structured fields are graded against the specs above; ungraded ECG fields accept any value.
- Explanations are free text and are not graded.
- A pass therefore certifies the graded fields, not a complete clinical interpretation.

## QA

Run `T4_BUILD=<dir with sources.sqlite and ecg/> .venv/bin/python -m unittest qa.test_task4`. It runs 19 tests:

- **Answers:**
  - The reference scores 1 through the real CLI, and a no-op scores 0.
  - 17 wrong algorithms each score 0, and so do misreadings.
- **Measurement consistency (audit regressions):**
  - Every required QT item's accepted QTc range is at or above 500 ms.
  - Every pair of accepted QTc readings implies a change set the comparison accepts.
  - The grading ranges admit every agreeing reader.
  - A required bundle-branch block never accepts QRS below 120 ms (v0.4.1).
- **Invariance:** with every patient, record and ECG ID renamed and every result list shuffled, the reference still scores 1.
- **Leakage:**
  - Case vs control Mann-Whitney AUCs over 14 structural features of the added layer, including the minimum visit gap,
    the longest note and note line counts.
  - Simple structural rules (a visit gap under 60 days, a note of six or more lines, an outside-records note) must not
    isolate cases.
  - Added resources match real record shapes.
- **Public surface:** the public files contain no answers and no ECG method.
- **Service contract:**
  - Malformed or foreign writes are rejected.
  - Concurrent HTTP requests are atomic: no duplicate audit sequence numbers.
  - An audit failure is recorded as an infrastructure fault.
  - Forged snapshots are invalid.

Run `python3 qa/task4_preflight.py VERSION` before any paid run. It fails closed if git or Docker is unavailable; `qa.test_preflight` checks that.

## Running

The pilot setup follows Task 3:
- adapter 0.4.0 with opt-in prompt caching (`--ak prompt_cache=true`, a user decision; requests otherwise keep the
  original shape);
- `caffeinate`, so the Mac cannot sleep mid-run;
- all 10 trials concurrently;
- a 64K output cap with an 1,800 s request timeout.

Run `python3 qa/task4_preflight.py VERSION` first. It checks versions, pinned ECG files, a clean checkout, and that no
other ChartR trials are running.

```sh
caffeinate -dims env PYTHONPATH="$PWD" .venv/bin/harbor run -c chartr_job.yaml -p chartr_task4 -a anthropic_agent:AnthropicAgent \
  -m claude-opus-5 -k 10 -n 10 --ak max_turns=300 --ak max_tokens=64000 --ak api_timeout_sec=1800 --ak wall_timeout_sec=7000 \
  --ak tool_timeout_sec=900 --ak prompt_cache=true --env-file .env --job-name opus-pilot --jobs-dir "$PWD/jobs/chartr/task4-VERSION-TS"
```

**Where the time goes** (v0.3.4, 455 turns):
- API time is 87–93% of each run, and it is output-bound. Per-turn latency is about 1.4 s plus 12 s per 1K output tokens,
  plus 0.007 s per 1K input tokens. Runs write about 137K output tokens.
- Input re-processing is only about 6% of latency, so caching mainly cuts input cost: each run otherwise re-sends about
  19M input tokens.
- Tools take 100–300 s per run.
- Without `caffeinate`, v0.3.2 lost about 9 min per trial to host sleep.
- With 10 concurrent trials, a batch takes about as long as its slowest run.
- 10 concurrent oracle trials (20 containers) pass in 3 min 20 s on a 10-CPU, 8 GB Docker host.

`jobs/chartr/task4-0.1.0-1790554704` was run with the 60 s tool-timeout default. It is invalid infrastructure evidence
and is not a pilot result: all five runs ended at their first bulk export.

## Pilot history

- **v0.1.0**, `jobs/chartr/task4-0.1.0-1790555298` (Opus 5, 5 runs, 20–25 min each): raw score 0/5. Triage found four
  answer-key defects, all fixed in v0.1.1:
  - CHA2DS2-VASc vascular disease: coronary atherosclerosis with prior revascularization is now accepted.
  - AF evidence now also accepts charted ICU rhythm and clinic notes that name AF.
  - The dual-anticoagulation note that lists both drugs is accepted as a conflicting record.
  - The start-visit note is accepted as a trigger for ECG follow-up, as tools.md allows.

  The motion-artifact ECG was also withdrawn. Rescored against the v0.1.1 key, the batch is 1/5
  (`rescored_answer_key_v2.json`). Remaining failures, all reasoning or reading errors:
  - 4/5 missed AF for 10004235. It is documented only on an older ECG and in inpatient charting; these runs examined only
    the most recent ECGs.
  - One run cited a refill order as the trigger.
  - One run read ectopic beats that aren't there and gave HR 64 on a 58 bpm tracing.
  - One run read a QTc of 521 ms on a normal ECG with baseline wander.
- **v0.1.1**, `jobs/chartr/task4-0.1.1-1790560349` (5 runs): 1/5, with no key defects. 4/5 missed 10004235 without ever mentioning it; one
  of those runs also cited a note that does not mention AF as AF evidence.

  Combined with the rescored v0.1.0 batch: **2/10**. Pass or fail rests almost entirely on the 10004235 case, which
  8/10 runs missed.

## v0.2.0: more cases on the observed weakness

The v0.1 pilots failed almost only on AF evidence that sits outside the latest ECG. v0.2.0 adds three cases (20 items,
19 findings) so failures spread over more skills:

- **10020306, UNTREATED_AF.** AF appears only in inpatient rhythm charting (76 "AF (Atrial Fibrillation)" entries). She
  has no AF codes, no ECGs and CHA2DS2-VASc 9. Her acute coagulopathy code is removed so it can't be read as a standing
  contraindication.
- **10013049, PROLONGED_QTC_ON_WATCH_LIST_DRUG.** His latest ECG is lengthened just over threshold: tangent reads
  508–526 ms, other methods 557–582 ms. The note at the escitalopram start says "QT acceptable" about that same ECG. Being
  started in 2024, before any ECG-after-start memo, also makes him a look-alike with no follow-up requirement.
- **10019385, ECG_AFTER_WATCH_LIST_START.** Escitalopram was started on 2/12/2026, 17 days before the 14-day memo took
  effect, and an ECG followed 24 days later. That is completed under the 30-day memo; it would be overdue if the new memo
  were applied.

To keep the date-dependent case gradable, both ECG memos now state which start dates they cover. The QA suite adds two
wrong algorithms, both scoring 0: no charted rhythm, and trusting the documented QT.

- **v0.2.0**, `jobs/chartr/task4-0.2.0-1790573334` (5 runs): 0/5. Every run missed both UNTREATED_AF cases whose evidence lies
  outside the diagnosis codes and latest ECG: 10020306 (charted rhythm) and 10004235 (older ECG). Every other v0.2 addition
  was handled correctly in all five runs. See TRIAGE.md in that folder.

## v0.3.0: full ECG interpretation with serial comparison

The agent now saves one structured interpretation of every patient's most recent ECG: 55 patients (39 sinus, 15 AF,
1 paced). The earlier findings only covered AF and prolonged QTc.

**Interpretation fields:** rhythm, ventricular rate, PR, QRS and QTc (Bazett), axis category, conduction (RBBB, LBBB,
first-degree AV block), the prior ECG, and changes from it: new or resolved AF, flutter, paced rhythm or bundle-branch
block, and QTc change of 60 ms or more.

**Harder tracings.** Five real ECGs were added after 12-lead review:
- sinus tachycardia with first-degree AV block and LBBB, followed by ventricular pacing;
- two LBBB tracings with PVCs and borderline PR;
- a rate-related RBBB that resolves the same day.

Candidate atrial-flutter tracings were rejected because flutter waves could not be confirmed on review.

**Truth from three readers** (`qa/task4_interpret.py`, `qa/task4_interp_truth.py`): the cart's own measurements and
statements, neurokit2 DWT, and an in-house 12-lead global method.
- A field is graded only where the readers agree: QRS on 53 latest ECGs, PR on 33, QTc on 27, axis on 54.
- Otherwise any value is accepted.
- Conduction and change lists are graded as required sets plus allowed sets, so a borderline finding is neither
  demanded nor penalized.

**Grader components:** `identification`, `item_fields`, `ecg_interpretation`, `ecg_comparison`, `ecg_linkage`,
`chart_rules`.

**QA** adds these wrong algorithms, all scoring 0: interpretations without comparison, prior = oldest ECG, no conduction
findings. It also adds these misreadings, all scoring 0: paced read as sinus with LBBB, and the transient RBBB missed.
- **v0.3.0**, `jobs/chartr/task4-0.3.0-1790576029` (5 runs): 0/5, also 0/5 after rescoring against the v0.3.1 key. The v0.3.1 key widens QTc
  to plausible readers ±40 ms and QRS to ±25 ms, grades PR only via first-degree AV block, and limits rhythm conflicts to
  notes. Every run still misses the two hidden-evidence AF items. Separately, the ECG interpretation and comparison
  components fail in 5/5 runs on real misreads: slow AF read as sinus on a prior, a paced prior claimed, AF rates miscounted.
  See TRIAGE.md in that folder.

## v0.3.2: calibration

- **10020306:** her clinic notes now list "persistent atrial fibrillation" in the history line. Her AF diagnosis codes
  stay removed, so the evidence is note text plus inpatient rhythm charting.
- **Interpretations are required only for living patients:** 37 ECGs (33 sinus, 4 AF). Deceased patients' latest ECGs
  (18) are optional: neither required nor penalized. This makes the paced tracing (10023117, deceased) optional. The LBBB
  (10038992), first-degree AV block (10007058) and transient-RBBB comparison (10021487) remain graded.
- **v0.3.2**, `jobs/chartr/task4-0.3.2-1790609695` (5 runs): 0/5.
  - 10020306 is now found in 3/5 runs.
  - 10004235 is missed in 5/5; across all batches it has been found in 2 of 30 runs.
  - v0.3.3 accepts either reading for three rhythms that could not be settled on high-resolution review: 103992480
    (sinus/ectopic atrial), 100924231 (sinus tachycardia/2:1 flutter) and 108780865 (slow AF/sinus).
  - Rescored against the v0.3.3 key, 3/5 runs pass every ECG component, and one run (cCSHmmu) fails only on 10004235.

## v0.3.4: calibration

10004235's clinic notes now list "paroxysmal atrial fibrillation" in the history line, the same treatment as 10020306 in
v0.3.2. His AF diagnosis codes stay removed; the older AF ECG and inpatient charting become corroborating evidence.
- **v0.3.4**, `jobs/chartr/task4-0.3.4-1790613876` (5 runs): **1/5** (xCZrGaw passes every component). 10004235 and 10020306 are each found
  in 4/5 runs. The remaining failures are genuine: rate over-counting, a QT misread on the baseline-wander tracing, AF
  evidence citing records that don't establish AF, first-degree AV block called on normal PRs, and missed hidden AF.
  v0.3.5 leaves the axis ungraded when the readers disagree by more than 40°, and forbids first-degree AV block only when
  the cart's PR is 160 ms or less. Rescored, the batch is unchanged at 1/5.
- **v0.3.5**, `jobs/chartr/task4-0.3.5-1790617318` (**10 concurrent trials**, prompt caching): raw 1/10; **4/10 against the
  v0.3.6 key**. v0.3.6 makes three changes:
  - coded dysrhythmias are accepted as corroborating AF evidence, with at least one AF-establishing record still required;
  - first-degree AV block is forbidden only when both the cart and neurokit PR are 160 ms or less;
  - 100924231 also accepts an ectopic atrial rhythm.

  The six failures are genuine: hidden AF missed, a transient RBBB resolution missed, rhythm and rate misreads, and a
  QT misread on the baseline-wander tracing. See TRIAGE.md in that folder.

## v0.4.1: release-validation fix (September 28, 2026)

`RELEASE_VALIDATION_2026_09_28.md` found one key inconsistency of the kind the v0.3.6 audit found for QT. On 104941853 (10038992),
LBBB was required while the accepted QRS range began at 101 ms, so a key-accepted reading below 120 ms that correctly omitted LBBB
scored 0. Where a bundle-branch block is required, the QRS range now starts at 120 ms. That changes one graded bound in the key
and the reference's QRS midpoints; no case, record or other field changes.

- **Pilot impact:** none. All ten v0.4.0 runs read 120–136 ms there and called LBBB. Rescored against the v0.4.1 key the batch is
  unchanged, 3/10 with identical per-run rewards. v0.4.1 itself has not been piloted.
- **QA added:** the BBB/QRS consistency test and ID-renaming invariance (the brief asked for it; only record order had been checked).

## v0.4.0: response to the v0.3.6 audit (`TASK4_V036_AUDIT_2026_09_28.md`)

- **QT decision margin.** The three current QT edits whose accepted range dipped below 500 ms were re-edited, with every
  agreeing reading now at least 520 ms. QT-safety items are also:
  - required only when the whole accepted range of the latest ECG is at or above 500 ms;
  - absent when the whole range is below 500 ms;
  - optional otherwise.
- **Serial QTc changes** now use the same padded ranges as the QTc fields. As a result, no QTc change is required.
- **Service concurrency.** State access is serialized and each request is a `BEGIN IMMEDIATE` transaction. An audit failure
  is recorded as an infrastructure fault. Before the fix, 8-way concurrent HTTP reads reproduced duplicate audit sequence
  numbers; now they pass.
- **Reader documentation** reflects the actual per-field rules above. First-degree AV block is forbidden only when every
  available PR reader reads 160 ms or less.
- **Leakage.** Short return visits, routine note free text and outside-records notes were added for everyone. QA now checks
  structural rules and the longest note.
- **Docs and preflight.** The current-state summary is corrected, grading claims are qualified, and preflight fails closed.

## Classification of post-pilot changes

Raw and rescored results are reported separately. Rescores are development evidence, not independent confirmation.

- **Defect corrections** (the old key contradicted the public task or its own measurement uncertainty):
  - vascular-disease definition (v0.1.1);
  - AF evidence from charted rhythm, notes and older ECGs (v0.1.1);
  - the dual-anticoagulation note (v0.1.1);
  - the start-note trigger (v0.1.1);
  - interval tolerances (v0.3.1);
  - corroborating dysrhythmia codes, with an AF-establishing record still required (v0.3.6);
  - QT decision and comparison consistency (v0.4.0).
  - bundle-branch block and QRS consistency (v0.4.1).
- **Label adjudication after seeing runs** (designer review, not a blinded expert):
  - the withdrawn motion-artifact ECG (v0.1.1);
  - the three multi-reading rhythms (v0.3.3, v0.3.6);
  - the indeterminate-axis and PR-margin rules (v0.3.5, v0.3.6).
- **Task redesign or calibration** (this changes what is tested; earlier failures are not thereby reclassified as unfair):
  - new cases (v0.2.0);
  - full interpretation and harder tracings (v0.3.0);
  - AF in the note history of 10020306 (v0.3.2) and 10004235 (v0.3.4);
  - living-only interpretations (v0.3.2);
  - notes-only rhythm conflicts (v0.3.1). This changed the public definition, and the earlier nursing-chart flags were a
    plausible reading of the old policy.
- **Pilot scores:**

  | Version | Raw | Rescored |
  |---|---|---|
  | v0.3.4 | 1/5 | 1/5 against v0.3.6 |
  | v0.3.5 (10 trials) | 1/10 | 4/10 retrospective, against v0.3.6 |

  v0.4.0 has not been piloted. The earlier snapshots cannot be rescored against it, because its QT-edited tracings differ.

## Final pilot, v0.4.0 (frozen key, commit d1156b5)

- `jobs/chartr/task4-0.4.0-1790626310` (also on the `task4-pilot-results` branch): **3/10** (3kzLb4o, dsn6HkF, iXuDhuL). All 10 runs valid, 33–49 min each, 50 min for the batch.
- Every failure includes at least one genuine error:
  - first-degree AV block missed on PR misreads (2 runs, their only failure);
  - T waves counted as beats, giving wrong rates and one false AF;
  - non-AF records cited as AF evidence;
  - hidden AF missed;
  - a transient RBBB resolution missed.
- Two contested points (see TRIAGE.md) change no outcome: 10022017's prior-ECG rhythm, and an AF code as a corroborating
  conflict record.
