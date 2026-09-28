# chartr_task4 — cardiology population review on real data (v0.1.1)

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
