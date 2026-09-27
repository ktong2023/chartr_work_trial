# Retrospective clinic reconciliation protocol

Evaluation time: **2026-09-24, 12:00 UTC**. All patients are synthetic. Apply this clinic's specified retrospective review protocol; do not prescribe or choose a different clinical standard. Save one determination for **each target episode and each of its two checkpoints**, even when no requirement remains. Reconcile all the patient's checkpoints together.

## Reconstruct the effective record

Structured fields are original entries. Signed, final DocumentReference notes may amend individual fields. Clauses are numbered within each note. An amendment affects only the named entry and field; other fields retain their values. The latest effective amendment to a field wins. A new record does not silently replace an old one. A withdrawal removes only the named clause. Withdrawing a withdrawal restores the clause it had withdrawn, subject to any other effective withdrawals or later amendments. Earlier documentation is always referenced; determine effective clauses before deriving clinical state. Documentation after the evaluation time has no effect.

Authority is recorded in `author-role`. A `clinician` may amend MedicationAdministration, ServiceRequest and clock-pause Basic records. A `laboratory` author may amend Specimen and Observation records. Other roles cannot amend these facts. A withdrawal has authority only when its author has the same role as the note containing the referenced clause. An unauthorized clause has no effect. Original entries remain usable unless effectively amended or revoked; author names alone confer no authority.

Field meanings used in amendments:

| Field | Interpretation |
|---|---|
| `date` | Administration date on MedicationAdministration; collection date on Specimen |
| `course` | MedicationAdministration's MedicationRequest reference |
| `courses` | Complete replacement list of course references on a plan, pause, or specimen; comma-separated IDs |
| `start`, `end` | Boundaries of a clock-pause interval |
| `status` | Status of the named record |
| `routine`, `accelerated` | Complete pair of calendar-month offsets for a plan's first and second checkpoints |
| `titer` | RPR reciprocal dilution as an integer on Observation |

Use a course's MedicationRequest episode link to establish scope. For doses, plans, pauses, and specimens, the effective course association governs. A corrected association can change more than one episode's determination. MedicationRequest episode links themselves are fixed.

## Paused clocks and course completion

Active Basic records with code `Review-clock pause` suspend both the inter-dose clock and follow-up clock for their associated courses. Intervals include their start date and exclude their end date: `[start,end)`. Combine overlapping intervals as a union; a calendar day is paused at most once. Revoked pauses have no effect. A pause does not invalidate an administration or specimen collected during it.

For a course, take distinct completed administrations whose effective date is at or before the evaluation date. Sort by date, breaking ties by ID. All administration records here represent distinct physical events. Between consecutive dates `a` and `b`, count unpaused calendar days in `[a,b)`. If this exceeds 14, begin a new sequence. Exactly 14 is allowed. The first sequence to reach three administrations completes the course on its third date; later doses do not change completion. If no sequence completes, retain only the last incomplete sequence and leave completion and due dates null. Corrections require recomputing sequence membership, not just changing the date on an old selected sequence.

## Governing plan and conditional schedule

For an episode, consider active ServiceRequest plans associated with that episode's course. An active plan's explicit `replaces` link removes its named older plan from consideration; revoked plans have no effect, including no replacement effect. Do not infer replacement from recency. Zero remaining plans means `no_requirement`; more than one means `unclear`. These statuses use null plan/course/branch/date/paused-days/result fields and empty doses for both checkpoints.

A single governing plan names a baseline report and a comparison report, routine and accelerated month pairs, and a minimum specimen separation. Use the effective reports and their specimens. Each comparison requires final or corrected RPR reports, positive reciprocal titers, available specimens, specimen dates no later than evaluation, and reports issued by evaluation time. If a designated report or specimen is unavailable or invalid, both determinations are `unclear` with the empty fields above. Do not substitute another report for a designated comparison.

Use `accelerated` if the comparison specimen is later than the baseline specimen **and** its titer is at least four times the baseline; otherwise use `routine`. The pair's first offset applies to checkpoint `first`, the second to `second`. This is the recorded plan's condition, not an invitation to infer a different schedule.

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
- With a complete course and valid plan, an unassigned `second` whose `first` is unassigned is `blocked`, regardless of its due date.
- Other unassigned checkpoints are `overdue` when their due date is at or before the evaluation date, otherwise `not_due`.
- Preserve the governing plan/course, branch, counted doses, completion date, due date, and paused-day count in these rows. `result` is null unless `completed`.

Explain the determination briefly. The saved fields, not a final chat response, constitute the submission.
