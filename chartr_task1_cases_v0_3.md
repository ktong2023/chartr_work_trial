# ChartR Task 1 — private case sheet, v0.5.0

**Private. Contains expected answers. Never copy into `chartr_task/environment/`.**
Supersedes `chartr_task1_cases_v0_2.md`. Canonical facts live in `qa/build_fixture.py`;
expected answers in `chartr_task/tests/grade.py`. Record IDs are opaque hashes of the
private keys (`rid()` in the generator).

Evaluation time: 2026-09-24 12:00 UTC. Twenty-four patients, two categories, 19 expected final
items (7 seeded, 12 created). Every other (patient, category) pair must have no item.

## What changed from 0.2.0

- **Facts live in prose, not answer-bearing fields.** Plans carry no `due-by` field, orders
  are not linked to plans, and plan statuses stay `active` after later documentation replaces
  them (P110, P118). The public disclosure (tools.md): status fields, dates and links are not
  always updated; later documentation that explicitly corrects, discontinues or replaces an
  earlier record governs, subject to the policy's authority rules.
- **Policy clause added:** a requirement whose named event has not yet occurred is not yet due.
- **Ten new multi-step cases** (P111–P120), each with an obvious shortcut that gives the wrong answer.

## Cases

| Patient | Key facts | Expected | Tempting wrong answer |
|---|---|---|---|
| P101 | As before | TR create `open` | — |
| P102 | As before; plan D09 due 2027-03-15 (text only) | TR resolve Q2146; FU none | FU item for planned serology |
| P103 | As before | TR create `needs_clarification` | — |
| P104 | Weekly ×3 ending Apr 1; plan 6 months after final dose | none | First-dose anchor → overdue |
| P105 | Seeded Q2203; staff recall removal; patient self-report | Leave Q2203 `open` | Resolve |
| P106 | Plan due Sept 5; visit booked for Oct 1 | FU create `open` | "Scheduled" |
| P107 | Two clinicians' plans, 3 vs 6 months, no reconciliation | FU create `needs_clarification` | Pick a plan |
| P108 | Seeded Q2217; RPR resulted Sept 16 | Resolve Q2217 | Keep open; flag 12-month plan |
| P109 | Plan due Aug 10; unrelated Sept 8 visit + HIV test | FU create `open` | Visit = completion |
| P110 | Seeded Q2081; Aug 28 note replaces the Jan plan in prose; old plan still `active` | Resolve Q2081 | Two active plans → FU2; keep open |
| P111 | Duplicate single-dose order discontinued in a clinician note; order still `active` | none | TR2 on two active orders |
| P112 | Plan record says 6 months; clinician addendum corrects to 3 months (HIV) → due Jul 10 | FU create `open` | Read the plan record → not due |
| P113 | Seeded Q2119; patient portal claim, then scanned outside RPR result (Aug 28) | Resolve Q2119 | Outside report not accepted |
| P114 | Pregnancy test resulted negative; no clinician treatment decision; doxycycline still draft | TR create `open` | "Result arrived → resolved" |
| P115 | 6-month RPR done Jul 14; 12-month plan not due | none | Stale 6-month plan → overdue |
| P116 | Seeded Q2187; Sept 12 RPR later documented as another patient's result | Leave Q2187 `open` | Resolve on the misfiled result |
| P117 | Weekly ×3 and single-dose orders both active since March; one dose given; RPR plan due by 2026-09-02, no result | TR create `needs_clarification` + FU create `open` | Stop after the treatment item; choose a regimen; FU as timing unclear |
| P118 | Series restarted after a missed dose (final dose Apr 3); plan revised from 3 to 6 months in prose → due Oct 3 | none | Wrong anchor or old interval → overdue; two plans → FU2 |
| P119 | Seeded Q2209 (isotretinoin interaction); later clinician note addresses only the penicillin allergy | Leave Q2209 `open` | Resolve on the allergy note |
| P120 | Clinician plan 6 months (Nov 5); nurse-entered 3-month recall plan | none | Nurse plan → overdue or FU2 |
| P121 | Weekly ×3 order (Sept 8) + later single-dose order after a history-based reassessment to secondary syphilis; weekly order never cancelled | TR create `needs_clarification` | Later reassessment supersedes |
| P122 | IV penicillin order for possible ocular syphilis + later single-dose order after normal eye exam and CSF; IV order never cancelled | TR create `needs_clarification` | Normal CSF cancels the IV plan |
| P123 | P117's twin: outside records → single-dose order, but a later note explicitly cancels it and continues the weekly series | none | Two active orders → TR2 |
| P124 | P118's twin: HIV-negative rationale for 6-month RPR, but no explicit "replaces" → plans at 3 (Sept 10) and 6 months (Dec 10) | FU create `needs_clarification` | Unstated revision assumed; earlier plan → overdue |

## Evidence acceptance (required groups; one citation from each)

| Case | Required |
|---|---|
| P101 TR | S02; S01 or S03; S04 |
| P102 TR | D03; D01 or D04 |
| P103 TR | M02; M04 |
| P105 / P106 / P109 / P116 FU | the plan |
| P107 FU | plan A; plan B |
| P108 FU | the Sept 16 result or the note reviewing it |
| P110 FU | Aug 28 note; old or replacement plan |
| P112 FU | the addendum |
| P113 FU | the scanned outside report |
| P114 TR | the clinician note; the draft order |
| P117 TR | order A; order B |
| P117 FU | the plan (0.3.1: overdue by date; 0.3.0's completion-timed version was ambiguous) |
| P119 TR | the pharmacist's telephone note |
| P121 / P122 TR | order A; order B |
| P124 FU | plan A; plan B |

Allowed sets are in `grade.py`: every record bearing on the issue, including near-miss
records. Routine records are excluded.

## Anti-shortcut checks (`qa/test_clinic.py`)

ID order never separates citable from routine records in any chart; IDs are not
chronological; every type, role, label and author on a citable record also appears on a
routine one; signed notes appear on both sides (23 vs 14). Only Registration, Vital
signs and Administrative note labels, and one registration clerk, are routine-only.

## Calibration switch

Remove patients from `COHORT` in `qa/build_fixture.py` and regenerate; the grader,
reference and tests skip absent patients. Change cases, never rules, between pilot batches.

## 0.5.0 event-history cases (P104, P106, P109, P111, P113, P115, P116, P120 switched off)

| Patient | Event chain | Expected | Shortcut that fails |
|---|---|---|---|
| P125 | BPG series (dose 9/2) → reaction → clinician holds BPG, starts doxycycline → allergy confirmed; BPG never resumed | none | Both orders `active` → TR2 |
| P126 | Plan due 9/2 → 6/15 explicit revision to 12/15 → 6/16 revision retracted (wrong patient) | FU create `open` | Apply the revision → not due; or FU2 |
| P127 | Doses 3/9, 3/16 (charted twice), 3/23 (charted, not given), 3/30 → completion 3/30 → due 9/30 | none | Count charted doses → overdue |
| P128 | Seeded Q2131; 8/18 specimen rejected; 9/2 recollection valid (report corrected 1:4 → 1:2) | Resolve Q2131 | Keep open; or cite the rejected result |
| P129 | Doxycycline 9/1 → held 9/5 → resumed 9/9 → allergy clinic starts BPG series 9/12 (doses 9/12, 9/19); doxycycline never stopped | TR create `needs_clarification` | Hold read as stop; or implicit supersession |
| P130 | Seeded Q2104 resolved on an 8/20 INR clearance note; note retracted 9/5 (wrong patient); no injections given | Reopen Q2104 (`open`) | Leave resolved; or create a new item |
| P131 | 6-month plan → clinician explicitly revises to 12 months → nurse "per protocol" revision to due 8/15 | none | Latest revision → overdue; or FU2 |
| P132 | Doses 2/23, 3/2, 3/15 → erroneous restart (3/22, 3/29 extra) → addendum: series completed 3/15 → due 9/15 | FU create `open` | Use the restart → not due |

Required evidence: P126 plan A; P128 the 9/2 result or its correction; P129 both orders;
P130 the concern (clinician note or nurse note); P132 the plan.
