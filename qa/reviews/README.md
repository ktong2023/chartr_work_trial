# Task 3 independent reviews ([TASK_DESIGN_PRINCIPLES.md](../../docs/design/TASK_DESIGN_PRINCIPLES.md) section 6)

Each review gives a second model only what an agent sees: rendered charts (selected patients, every patient linked to
them through a laboratory result, the accessioning entries for their results, their review requests) and the public
`instruction.md`, `policy.md` and `tools.md` as they stood at the time. The reviewer decides every candidate
independently; its decisions are compared with the authored answers. Packets from 0.2.1 on are rendered by
`qa/task3_review_packet.py` (the answer key is written to a separate file that is not given to the reviewer).

| Folder | Fixture | Sample | Agreement | Outcome |
|---|---|---|---|---|
| `2026-09-27_v0.1.0_core29/` | 0.1.0 (`db0de73`) | the 29-patient core | 114/116, then 116/116 | Both misses were one wording ambiguity (whether pregnancy bears on `INADEQUATE_TREATMENT`); issue definitions fixed. Reviewer's raw reply was not retained; outcome recorded in `chartr_task3/README.md`. |
| `2026-09-27_v0.2.0_sample58/` | 0.2.0 (`40162ad`) | one patient per generated variant plus cross-chart partners (58) | 231/232 | The miss (P91bff86 `MISFILED_RESULT`) was a generator bug, a specimen dated after the evaluation time; fixed, with a build assertion. `reviewer_answers.txt` holds its decisions (`C`, `NI`, `CD-<code>`), in issue order `INADEQUATE_TREATMENT, FOLLOW_UP_OVERDUE, MISFILED_RESULT, PREGNANCY_TREATMENT_INADEQUATE`. |
| `2026-09-27_v0.2.1-pre_f3/` | 0.2.1 pre-release | all 18 rewritten F3 stage-inference patients | 72/72 | Its one substantive concern: two F3 patients (and, on checking the whole cohort, five more since 0.2.0) were overdue only for a test missed *after* their follow-up RPR had turned nonreactive, where some clinicians would stop testing. Fixed for all 300 patients: follow-up RPRs turn nonreactive only at the last scheduled test, and the build refuses any answer that depends on a missed window after a nonreactive follow-up. `final_build_diff.txt` shows the only change to these 18 charts afterwards (ten follow-up values, Nonreactive to 1:1); the answer key is identical. `reviewer_report.md` has its full reasoning and fairness notes. |
| `2026-09-28_v0.3.0-pre_variants59/` | 0.3.0 pre-release | one patient per generated variant (59) | 236/236 | Seven realism and wording concerns (contradicted outside series, month-old pending tests, a nursing note that made `RESULT_PENDING` arguable, conception timing, a 65-year-old with a positive hCG, record arrival dates, rejection reasons), all fixed cohort-wide. See `reviewer_report.md`. |
| `2026-09-28_v0.3.0-pre2_changed21/` | 0.3.0 pre-release 2 | every variant the fixes touched (21) | 84/84 | Earlier concerns resolved. New: two decisive specimens exactly on a window edge. The build now refuses any window whose status changes when edges move 4 days (15 patients adjusted, incl. core p11). |
| `2026-09-28_v0.3.0_final60/` | **0.3.0 release (piloted)** | one patient per variant + partners + core p11 (60) | **240/240** | No edge-dependent answers remain; only the designed judgment calls. |
