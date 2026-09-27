# ChartR Task 1 — private case sheet, v0.2.0

**Private. Contains expected answers. Never copy into `chartr_task/environment/`.**
Canonical facts live in `qa/build_fixture.py`; expected answers in `chartr_task/tests/grade.py`.
Record IDs are opaque hashes of the private keys below (`rid()` in the generator).

Evaluation time: 2026-09-24 12:00 UTC. Ten patients, two categories, 9 expected final items
(4 seeded, 5 created). Every other (patient, category) pair must have no item.

## Cases

| Patient | Key facts | Expected | Tempting wrong answer | Skill tested |
|---|---|---|---|---|
| P101 | Unchanged from 0.1.4 | TR create `open` | — | Unresolved concern |
| P102 | Unchanged; adds plan D09 (RPR due 2027-03-15) | TR resolve Q2146; FU none | FU item for "serologic follow-up planned" | Not yet due |
| P103 | Unchanged | TR create `needs_clarification` | — | Unreconciled active orders |
| P104 | BPG weekly ×3: Mar 18, Mar 25, Apr 1. Plan: RPR 6 months after the final dose. Recall reminder Sept 17; visit booked for Sept 29 | none | Count from first dose → "overdue since Sept 18" | Date calculation across records |
| P105 | BPG Mar 1. Plan: RPR 6 months after treatment. Seeded Q2203 open. Scheduling staff removed patient from recall list; portal message claims outside testing, no result | Leave Q2203 `open`; no duplicate | Resolve on recall removal or self-report | Authority; what counts as completion |
| P106 | BPG Mar 5. Plan due-by Sept 5. Visit booked Sept 18 for Oct 1. Nurse note: injection soreness, resolved | FU create `open`; TR none | "Scheduled, so fine"; TR item for soreness | Due date vs. future plans |
| P107 | BPG Jun 2. Plan A (Moreno): RPR 3 months after treatment → Sept 2. Plan B (Raman, Jul 15): 6 months → Dec 2. Neither references the other | FU create `needs_clarification`; TR none | Later plan wins; earlier plan wins (`open`); filed as TR conflict | Incompatible requirements; category choice |
| P108 | BPG Mar 1. Plan due-by Sept 1 + 12-month plan. Seeded Q2217 open. RPR ordered Sept 15, resulted Sept 16 (1:2) | Resolve Q2217; no 12-month item | Keep open (completed late); create new item; flag 12-month plan | Completion; update instead of create |
| P109 | BPG Feb 10. Plan: RPR 6 months after treatment → Aug 10. Sept 8 nurse visit (hepatitis B vaccine) with HIV test | FU create `open` | Recent visit + lab = completed | Relevance of completion evidence |
| P110 | Doxycycline Jan 20, stopped after ~5 days. Plan due-by Jul 20; seeded Q2081 open. Aug 28 clinician re-treats and explicitly replaces the plan (new due 2027-03-10; old plan revoked) | Resolve Q2081; no new FU item; TR none | Keep open (RPR never done); flag new plan; record the addressed TR concern | Clinician revision; cross-category dependency |

## Evidence acceptance (role-based)

Required groups (one citation from each):

| Case | Required |
|---|---|
| P101 TR | S02; S01 or S03; S04 |
| P102 TR | D03; D01 or D04 |
| P103 TR | M02; M04 |
| P105 FU | P105 plan |
| P106 FU | P106 plan |
| P107 FU | plan A; plan B |
| P108 FU | the Sept 16 RPR result or the clinician note reviewing it |
| P109 FU | P109 plan |
| P110 FU | Aug 28 clinician note; old or replacement plan |

Allowed sets are listed in `grade.py`. They include every record bearing on the issue's
existence, timing, completion or resolution, including the near-miss records a reviewer
would cite to explain the disposition. Routine records (registration, vital signs,
unrelated visits, messages and labs) and D09 (for the Darrow treatment item) are excluded.

## Anti-shortcut measures (checked by `qa/test_clinic.py`)

- Record IDs are opaque hashes: not chronological, not grouped by patient, type or relevance,
  and never threshold-separable into citable and routine records within any chart.
- Every resource type, author role, note label and author name found on a citable record
  also appears on a routine record. Signed clinician notes appear on both sides (14 vs 6).
- Routine content includes orders, results, visits and signed notes, not only registration/vitals.
- Seeded item IDs follow creation order and share no number with their patient.
- Near-miss features are mixed across outcomes: explicit past `due-by` (P106 open, P108
  resolved, P110 revoked); interval-only plans (P104 none, P105 open, P107 unclear, P109 open);
  planned visits (P104 none, P106 open); recall notes (P104 none, P105 open); seeded items
  (three resolved, one kept open).

Only plainly routine labels (Registration, Vital signs, Administrative note) and one
registration clerk appear exclusively on non-citable records.

## Reserve cases (calibration knob; not in 0.2.0)

- The right test result, but from a previous episode.
- A treatment concern answered by a clinician in an earlier episode.
- A follow-up plan with no timing at all (FU2 without a conflict).
