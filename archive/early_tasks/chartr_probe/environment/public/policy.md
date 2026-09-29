# Clinic review protocol

This protocol defines the clinic's retrospective follow-up determinations. It does not ask you to select or prescribe treatment. The evaluation time is 2026-09-24 at 12:00 UTC.

## Source interpretation and amendments

Read the whole chart, including other episodes. Structured fields are the original entries; signed treating-clinician amendments may change them. An amendment applies only to its named entry and field. Unmentioned fields keep their prior values. A newer independent entry does not replace an earlier entry. The latest effective amendment to a field governs that field. Only treating-clinician amendments have authority under this review protocol.

Amendments use the following field names in their text:
- `date`: administration date for MedicationAdministration; specimen date for Observation.
- `course`: the MedicationRequest associated with a dose, result, or follow-up plan.
- `months`: the calendar-month interval in a follow-up plan.
- `status`: the status of the named source entry.
- `replaces`: the earlier follow-up plan expressly replaced by a plan, or `none` to remove that relationship.

A retraction of one amendment clause removes only that clause's effect. It restores the value that would apply without that clause, including any other effective amendments. Retraction does not retract the underlying source entry. A retraction can itself be retracted: `withdrawal` names that retraction clause. References always point to earlier documentation; evaluate which clauses are effective before calculating clinical state. Documentation after the evaluation time has no effect.

A course belongs to the EpisodeOfCare referenced on its MedicationRequest. For doses, plans, and results, the effective course association determines which episode they concern; a chart's original episode tag does not override a corrected course association. Do not combine events from different courses or episodes.

## Governing follow-up plan

For the target episode, consider active ServiceRequest plans associated with its courses after amendments. An active plan's explicit `replaces` relationship removes the named older plan from consideration. A revoked plan has no effect, including no replacement effect. Do not infer replacement from recency. A determination requires a single governing plan; if multiple active plans remain, record `unclear` and leave all plan/course/date/result fields null and doses empty. If none remain, record `no_requirement` with those same empty fields.

## Course reconstruction

For a single governing plan, follow its effective course association. Consider MedicationAdministration records whose effective status is `completed`, date is not in the future, and effective course matches. Sort by effective administration date, breaking a same-date tie by ID. In this fixture administrations are distinct physical events; no two records describe the same administration.

The recorded courses require a sequence of three administrations. Start a new sequence whenever the gap from the immediately preceding administration exceeds 14 calendar days. A gap of exactly 14 days remains within the sequence. The first sequence to reach three administrations establishes course completion at its third administration. Later administrations do not change a completed course. Reconstruct the sequence from the effective facts; corrections can invalidate a previously apparent completion. If no sequence completes, report only the last, still-incomplete sequence and a null completion date.

## Timing, completion, and output

A plan's due date is its effective month interval added to course completion. Use calendar months, clamping to the destination month's final day if necessary. An incomplete course has no due date yet and is `not_due`, not `unclear`.

A follow-up completion record must be an RPR Observation for the effective governing course, with effective status `final` or `corrected`. Its specimen date must be after course completion, at least the due date minus 30 calendar days, and no later than the evaluation date. Its issued time must also be at or before the evaluation time. The 30-day opening boundary is inclusive; results after the due date also complete the requirement. A result's magnitude is not part of this determination. Any qualifying result may be submitted.

When a qualifying result exists, status is `completed`, even if the due date has not arrived. Otherwise status is `overdue` if the due date is at or before the evaluation date, and `not_due` if it is later or the course is incomplete. Retain the governing plan, course, counted administration IDs, and computed dates in these determinations. `result` is null unless status is `completed`.
