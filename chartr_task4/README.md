# chartr_task4 — cardiology population review on real data (v0.3.0)

The agent reviews a 100-patient clinic population at 2026-09-24 12:00 America/New_York. It saves a review item for every
issue that needs clinical review, and an ECG finding for every patient whose most recent ECG shows atrial fibrillation or a
prolonged QTc. The population is the MIMIC-IV Clinical Database Demo on FHIR, and the ECGs are the MIMIC-IV-ECG Demo
(12-lead, 10 s, 500 Hz WFDB). Both are re-dated per patient and extended with a synthetic outpatient cardiology layer.

## Data and licence

- MIMIC-IV Clinical Database Demo on FHIR v2.1.0 and MIMIC-IV-ECG Demo v0.1 (PhysioNet), Open Data Commons Open Database
  License v1.0. They are fetched at image build time from the pinned PhysioNet versions, with every file checked against
  `environment/service/overlay/pinned.sha256` (436 files).
- The build also used the machine measurements of MIMIC-IV-ECG v1.0 (open access, ODbL). These served only as a third ECG
  reader when labelling. They are not shipped and are not seen by the agent.
- No credentialed PhysioNet data is used. This is a derived database and is not for clinical use.

## What the agent sees

- `instruction.md` (86 words), `/app/policy.md` and `/app/tools.md`.
  - The policy names the categories and the guideline.
  - Every operational rule is in dated clinic memos inside the chart: the QT watch list and threshold, ECG-after-start windows
    (one of which replaces another), INR after dose changes, and who may change warfarin doses.
- Nothing tells the agent how to read an ECG. It gets raw WFDB records and the same pinned analysis libraries used to label
  them (numpy, scipy, wfdb, neurokit2).

## Build and assembly

- `qa/build_task4.py` (private) writes `environment/service/overlay/`. The overlay holds per-patient day offsets, 3 removed
  records, 2,415 added FHIR resources cloned from real record shapes, the 203-ECG catalog, and int32 sample deltas for
  8 edited ECGs.
- `environment/service/assemble.py` rebuilds `/data/sources.sqlite` and `/data/ecg` deterministically. The content digest
  is pinned in `tests/baseline.json`.
- Re-anchoring moves each patient by whole weeks close to whole years, so weekday and season are preserved and local
  wall-clock times are kept.

### ECG labels

Three readers:

- an in-house algorithm;
- neurokit2 (dwt and cwt delineation, leads II and V5);
- the MIMIC machine statements and intervals.

Only ECGs where the readers agree are catalogued (132 normal, 66 AF, 5 prolonged QTc).

### ECG edits

- Four ECGs have a lengthened QT. The low-frequency J-point-to-T-end segment is time-warped, the original high-frequency
  noise is kept, and the extra time is taken from the T–P segment.
  - The targets are just above threshold: QTc (Bazett) of 560–590 ms.
  - After the edit, every agreeing read is at least 505 ms, and the graded range covers every agreeing read ± 20 ms.
- Four ECGs have realistic acquisition artifacts: EMG, baseline wander (two) and LA/RA reversal. A fifth, a motion artifact,
  was withdrawn in v0.1.1: on that low-voltage tracing it made the rhythm unreadable.

## Answers (17 review items, 18 ECG findings)

| Reason | Patients (MIMIC subject) | What must be reasoned |
|---|---|---|
| UNTREATED_AF | 10039997, 10023771, 10004235 | CHA2DS2-VASc with the sex-specific threshold. For 10004235, AF is documented only on an older ECG. |
| ANTICOAGULANT_WITH_CONTRAINDICATION | 10004457 | An outside-records note of a recent GI bleed, while apixaban is still current. |
| DUAL_ANTICOAGULATION | 10014354 | Switched to apixaban, but the rivaroxaban order was never stopped. |
| RHYTHM_DOCUMENTATION_CONFLICT | 10015272 | The note says sinus rhythm; the same-day ECGs show AF. |
| PROLONGED_QTC_ON_WATCH_LIST_DRUG | 10023239, 10004422, 10012853 | Measure QTc on the most recent ECG. Link it to the current watch-list order and the latest K and Mg results. |
| ECG_AFTER_WATCH_LIST_START | 10039831, 10029291, 10018423, 10022880, 10021312, 10004422 | Status is one of overdue, not_due, completed or cannot_determine. The right memo depends on the start date; there is an unreceived outside ECG; only Cardiology Clinic starts count. |
| INR_AFTER_WARFARIN_DOSE_CHANGE | 10016150, 10012853 | A clinician change that was completed, and a pharmacist change that is overdue. |

There are also 18 findings on patients' most recent ECGs (15 AF, 3 QTC_PROLONGED), with heart rate and QTc graded against
ranges.

**Look-alikes that must not be flagged:**

- a remote, resolved bleed;
- a clean warfarin-to-apixaban switch;
- a nurse call about an extra tablet with no change made;
- routine pharmacist INR calls and nurse refill calls;
- an older long-QT ECG followed by a normal current ECG;
- sinus rhythm documented in paroxysmal AF;
- artifact ECGs;
- deceased patients;
- inpatient watch-list orders.

## Grading (`tests/grade.py`)

The grader only accepts evidence collected by the controller. It checks attestation, the baseline digest, freezing, and
audit continuity; invalid runs get no reward. It reports five components, and reward is 1 only if all of them pass:

- `identification`: the exact set of (patient, category, reason), with no extras or duplicates.
- `item_fields`: every structured field of every item. These are the record IDs the item rests on, the risk score and its
  factors, status, due date, completion record, and QTc and HR ranges.
- `ecg_findings`: the exact (ECG, finding) set on each patient's most recent ECG, with heart rate and QTc in range.
- `ecg_linkage` and `chart_rules` are diagnostic subsets: the item fields that depend on reading an ECG, and the follow-up
  items that depend on clinic memos.

Explanations are free text and are not graded.

## QA

Run `T4_BUILD=<dir with sources.sqlite and ecg/> .venv/bin/python -m unittest qa.test_task4`. It checks:

- The reference (`solution/reference.py`) scores 1 through the real CLI, and a no-op scores 0.
- 12 wrong algorithms each score 0. Examples: AF codes only; oldest ECG instead of most recent; the old memo applied
  forever; the new memo applied too early; non-clinic starts counted; unreceived results ignored; a warfarin dosing mention
  counted as a change; a rhythm conflict taken from another day; deceased patients reviewed.
- Misreadings score 0: artifacts read as AF, and the remote bleed read as current.
- The grading ranges admit every agreeing ECG method.
- Case patients cannot be told apart from living controls by the volume of the added layer: Mann-Whitney AUCs are
  0.51–0.68 across 10 features.
- Added resources match real record shapes and timestamp formats.
- The public surface contains no answers and no ECG method.
- Service contract: malformed or foreign writes are rejected, the snapshot freezes, and forged snapshots are invalid.

## Running

Pilots use the pinned adapter with task-sized limits. A full export of one resource type (814K Observations) takes about
a minute, so the per-command tool timeout must be raised from the adapter default of 60 s:

```sh
PYTHONPATH="$PWD" .venv/bin/harbor run -c chartr_job.yaml -p chartr_task4 -a anthropic_agent:AnthropicAgent -m claude-opus-5 \
  -k 5 -n 5 --ak max_turns=300 --ak max_tokens=32000 --ak api_timeout_sec=900 --ak wall_timeout_sec=7000 \
  --ak tool_timeout_sec=900 --env-file .env
```

`jobs/chartr/task4-0.1.0-1790554704` was run with the 60 s default. It is invalid infrastructure evidence and is not a
pilot result: all five runs ended at their first bulk export.

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
