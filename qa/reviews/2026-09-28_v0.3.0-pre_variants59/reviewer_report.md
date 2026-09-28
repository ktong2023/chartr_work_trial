# Reviewer report: one patient per variant (0.3.0 pre-release build)

The reviewer was a second model (an independent subagent) given only the four files in this folder. Agreement with
`answer_key.json` was **236/236** (59 patients × 4 candidates). Its decisions are in `reviewer_answers.txt`, in issue
order `INADEQUATE_TREATMENT, FOLLOW_UP_OVERDUE, MISFILED_RESULT, PREGNANCY_TREATMENT_INADEQUATE`. Its rationale matched
the authored reasoning for every non-NI answer. That covers identities resolved and unresolved through the accessioning
log, author corrections and non-author disputes, received outside records over later notes, stage from exam and
history, seroconversion within 12 months, the 18-day gap, doxy-PEP, and pending results.

Its fairness notes, condensed, and what was done about each:

| Concern | Action (0.3.0 final) |
|---|---|
| Incomplete outside series: the patient's "Pt reports series completed at [clinic]" could be read as later care whose record was not received (`CD-ORNR`) rather than a contradiction of the received record. | Reworded to "Per pt, the second and third injections were both given at [clinic]", so the report plainly concerns the doses the record covers. The other wording, "the last two were at [clinic]", was already unambiguous. |
| A pending follow-up RPR "in process" for about 5 months; pending hCGs for about 70 days. Implausible. | Pending follow-up RPRs are now collected 4–30 days before the evaluation time, with the window just closed. F4 diagnoses and pending hCGs are 32–44 days old. |
| Second patient of a disputed pregnancy test: a nursing note "hCG drawn" in her own chart makes `RESULT_PENDING` arguable next to `UNRESOLVED_SOURCE_CONFLICT`. | That note now appears only in the misfile variant, where ownership is resolved. |
| A positive hCG 7 days after a 14-day doxycycline course: conception after the course is conceivable. | The positive test is now within 10 days of the diagnosis whose course it bears on, so it falls during treatment. |
| A positive hCG accessioned to a 65-year-old external patient is implausible and could tip the identity question. | External patients named on pregnancy-test conflicts are 19–43 years old. |
| A received outside record dated before the treatment date a later clinic note gives. | The outside record now arrives 2–8 days after the misstated date. |
| "Specimen clotted" is an odd rejection reason for a serum RPR. | Replaced with hemolyzed or quantity-not-sufficient. |
| Pregnancy unknown or unresolved but treatment adequate either way (answered NI); a serofast 1:1 titer and the 24-month test; the 30-day delivery rule applying to PRG, not ADQ; early-latent single dose in pregnancy. | No change. These are the designed relevance and standard-of-care decisions, and the reviewer answered them as authored, noting only that others might disagree. |

The fixes regenerated every chart, so this packet's patient IDs do not match the final build. The changed variants were
re-reviewed on the final build (`2026-09-28_v0.3.0_changed21/`). While the fixes were being applied, the build also
refused a latent F6 generator case: a disputed dose date 20–28 days later could push the 12-month window past the
evaluation time. The charted anchor now leaves room for both windows.
