# Retrospective clinic reconciliation protocol

Evaluation time: **2026-09-24, 12:00 UTC**. All patients are synthetic. Apply this clinic's specified retrospective review protocol; do not prescribe or choose a different clinical standard. Save one determination for **each target episode and each of its two checkpoints**, even when no requirement remains. Reconcile all the patient's checkpoints together.

## Reconstruct the effective record

Structured fields are the original chart. Clinic staff document changes in signed, final DocumentReference notes written in ordinary clinical language. Read what each statement explicitly says:

- A statement changes a fact only when it explicitly corrects it, reassigns it, cancels or reactivates it, marks it not given, given, unavailable or entered in error, or retracts an earlier change. Statements that review, confirm (for example "correct as charted"), question or describe plans change nothing.
- Notes identify records by their charted details: a treatment series by the date it started; an injection by the date it was charted and the series it was charted under; a review hold by its start date; a specimen by its charted collection date; an RPR report by its specimen's charted collection date; a follow-up plan by the date it was entered and the series it was entered for. Charted details always mean the original structured entry, never an amended value.
- A change affects only the fact it names; other facts keep their values. When effective changes to the same fact conflict, the one in the latest-dated note wins. A new note never silently replaces an old one.
- A retraction removes only the specific change it identifies; other changes in that note stand. Retracting a retraction reinstates the change it retracted, subject to any other effective retraction or later change.
- Documentation dated after the evaluation time has no effect.

Authority is recorded in `author-role`. A `clinician` may change injections (MedicationAdministration), follow-up plans (ServiceRequest) and review holds. A `laboratory` author may change specimens and RPR reports. Other roles cannot change these facts or order holds. A retraction has authority only when its author has the same role as the author of the note containing the change it retracts. An unauthorized statement has no effect. Signatures and author names confer no authority.

How statements map to facts:

| Statement about | Fact changed |
|---|---|
| An injection "actually given on" / "should be dated" a date | Administration date |
| An injection belonging to, or reassigned to, another series | The injection's course (MedicationRequest) |
| An injection "not given" / "not administered"; later "given after all" / "in fact administered" | Administration status not-done / completed |
| A hold's scope ("should apply to X and Y only") | Complete replacement list of the hold's series |
| A hold "lifted on" / "clocks resumed" a date | That date is the first unpaused day (interval end) |
| A hold that "ran through" / whose "last held day" is a date | That date is the last paused day (interval end is the next day) |
| A specimen's collection date ("mislabeled; actual collection date") | Collection date |
| The series a specimen was "drawn as follow-up for" / "supports ... only" | Complete replacement list of the specimen's series |
| A specimen "lost" / "unavailable" | Specimen status unavailable |
| A report's corrected titer "1:N" | Reciprocal titer N |
| A report "entered in error" / "resulted on the wrong patient" | Report status entered-in-error |
| A plan "discontinued" / "cancelled"; "reactivated" | Plan status revoked / active |
| A plan "linked to" another series | Complete replacement list of the plan's series |
| A plan's routine checkpoint months | The plan's routine month pair |

A signed clinician note can also order a review hold without a structured Basic record, naming the series, the start date, and either the resume date (first unpaused day) or the last held day. Such a hold has the same effect as an active structured hold.

Use a course's MedicationRequest episode link to establish scope. For injections, plans, holds and specimens, the effective course association governs. A corrected association can change more than one episode's determination. MedicationRequest episode links themselves are fixed.

## Ranges, conflicting reports and unreceived results

- An administration recorded with a date range occurred on one unknown date within that range, inclusive.
- When final or corrected reports on the same specimen give different titers and no effective change settles which is right, the specimen's titer is one unknown value among those reported.
- A course's counted doses and completion date, and a plan's schedule branch, are established only when they are the same for every date or value these facts allow. If the governing plan's branch or the course's counted doses and completion date cannot be established, both determinations are `unclear` with the empty fields described below.
- An RPR that a signed note documents as collected elsewhere on a stated date, with no report in the chart, is an unreceived result. It cannot complete a checkpoint.

## Paused clocks and course completion

Active review holds (structured Basic records with code `Review-clock pause`, or holds ordered in a signed clinician note) suspend both the inter-dose clock and follow-up clock for their associated courses. Intervals include their start date and exclude their end date: `[start,end)`. Combine overlapping intervals as a union; a calendar day is paused at most once. Revoked pauses have no effect. A pause does not invalidate an administration or specimen collected during it.

For a course, take distinct completed administrations whose effective date is at or before the evaluation date. Sort by date, breaking ties by ID. All administration records here represent distinct physical events. Between consecutive dates `a` and `b`, count unpaused calendar days in `[a,b)`. If this exceeds 14, begin a new sequence. Exactly 14 is allowed. The first sequence to reach three administrations completes the course on its third date; later doses do not change completion. If no sequence completes, retain only the last incomplete sequence and leave completion and due dates null. Corrections require recomputing sequence membership, not just changing the date on an old selected sequence.

## Governing plan and conditional schedule

For an episode, consider active ServiceRequest plans associated with that episode's course. An active plan's explicit `replaces` link removes its named older plan from consideration; revoked plans have no effect, including no replacement effect. Do not infer replacement from recency. Zero remaining plans means `no_requirement`; more than one means `unclear`. These statuses use null plan/course/branch/date/paused-days/result fields and empty doses for both checkpoints.

A single governing plan's text names a baseline RPR and a comparison RPR (each by its specimen's collection date), routine and accelerated month pairs, and a minimum separation between follow-up specimens (in days or weeks; a week is 7 days). Use the effective reports and their specimens. Each comparison requires final or corrected RPR reports, positive reciprocal titers, available specimens, specimen dates no later than evaluation, and reports issued by evaluation time. If a designated report or specimen is unavailable or invalid, both determinations are `unclear` with the empty fields above. Do not substitute another report for a designated comparison.

Use `accelerated` if the comparison specimen is later than the baseline specimen **and** its titer is at least four times the baseline ("4x", "fourfold"); otherwise use `routine`. The pair's first offset applies to checkpoint `first`, the second to `second`. This is the recorded plan's condition, not an invitation to infer a different schedule.

## Due dates

First add the selected number of calendar months to course completion, clamping to the destination month's last day if necessary. Let `N` be the number of calendar days from completion to that unpaused target. The actual due date is the earliest date `d` such that `[completion,d)` contains `N` unpaused days for that course. Pauses crossed by an extension also count; adding the number of pauses before the original target just once can be insufficient. Report `paused_days` as the number of distinct paused days in `[completion,due)`. An incomplete course has null dates, zero paused days, and `not_due` for both checkpoints; retain its plan, course, branch, and last incomplete sequence.

## Completion evidence and joint allocation

A report can be a checkpoint completion candidate only if:

- It is an RPR Observation effectively `final` or `corrected`, issued at or before evaluation time.
- Its referenced Specimen is effectively `available` and its effective collection date is no later than evaluation.
- That specimen's effective course list includes the governing course.
- Its effective collection date is after course completion and in the inclusive window **[due minus 21 days, due plus 35 days]**.

The Specimen collection date governs even when an Observation's original effectiveDateTime differs after correction. Report copies referring to the same specimen represent one collection, not additional evidence. Result magnitude is used for the plan's designated comparison only; it does not alter completion eligibility.

Across all target episodes of a patient, **one physical specimen may be assigned to at most one checkpoint**, even if several reports or course associations make it eligible elsewhere. Do not reuse a specimen across episodes or checkpoints. The `second` checkpoint can be completed only if `first` is also completed and the second specimen was collected at least the governing plan's minimum separation after the first specimen. These are ordinary calendar days, unaffected by pauses.

Choose a valid joint assignment that **maximizes the total number of completed checkpoints for the patient**. There is no tie-break preference: any maximum assignment is accepted, including different unmatched checkpoints where maxima differ. A locally valid choice may prevent a better joint assignment. Do not maximize each episode separately or prefer the earliest report regardless of the rest of the chart.

After choosing the assignment:

- An assigned checkpoint is `completed`, even if its due date is still in the future.
- An unassigned checkpoint is `cannot_determine` if an unreceived result would have been eligible for it had it been received: collected after course completion and inside the checkpoint's window and, for `second`, at least the minimum separation after the specimen assigned to `first`.
- With a complete course and valid plan, an unassigned `second` whose `first` is unassigned is `blocked`, regardless of its due date.
- Other unassigned checkpoints are `overdue` when their due date is at or before the evaluation date, otherwise `not_due`.
- Preserve the governing plan/course, branch, counted doses, completion date, due date, and paused-day count in these rows. `result` is null unless `completed`.

Explain the determination briefly. The saved fields, not a final chat response, constitute the submission.
