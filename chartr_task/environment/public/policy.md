| Rule | Trigger | Evidence that resolves or prevents the flag | Result |
| --- | --- | --- | --- |
| TR1: unresolved treatment concern | A clinical record explicitly identifies a concern about the current treatment plan that requires review, and available evidence does not establish resolution | An authorized clinician explicitly addresses the same concern and records its disposition; or clear documentation establishes that the concern applies only to a superseded plan | Category treatment_review; reason UNRESOLVED_TREATMENT_CONCERN; destination clinical_review; status open |
| TR2: conflicting active plans | Two currently applicable instructions for the same episode disagree on the same treatment decision, with no documented cancellation, supersession, or authoritative reconciliation | An explicit correction, replacement, or cancellation, or an authorized clarification that explicitly addresses the disagreement, resolves it | Category treatment_review; reason CONFLICTING_ACTIVE_PLANS; destination clinical_review; status needs_clarification |
| FU1: overdue follow-up | A current follow-up requirement's due date is at or before the evaluation time, and no completion evidence exists | Completion evidence for the requirement; or treating-clinician documentation that revises, replaces, or cancels it | Category follow_up; reason OVERDUE_FOLLOW_UP; destination follow_up_coordination; status open |
| FU2: follow-up timing unclear | The due date of a current follow-up requirement cannot be established, including when current requirements for the same follow-up service give incompatible due dates with no documented reconciliation | Treating-clinician documentation that establishes a single due date | Category follow_up; reason FOLLOW_UP_TIMING_UNCLEAR; destination follow_up_coordination; status needs_clarification |

Policy details:

- Treatment review covers treatment plans and orders. Follow-up covers follow-up requirements. Review each category independently.
- A follow-up requirement is a follow-up plan authored by a treating clinician. Its due date is its stated due date, or its stated interval counted from the documented date of the event it names; if that event has not yet occurred, the requirement is not yet due. An interval of months ends on the same day of the month.
- Completion evidence is a record that the required service itself was performed; for a test, that record is its result.
- Only treating-clinician documentation that explicitly revises, replaces, or cancels a follow-up requirement changes it.
- If TR1 and TR2 describe the same underlying conflict, create one item and use CONFLICTING_ACTIVE_PLANS as its primary reason. Do not duplicate the issue.
- Evidence references should identify the concern or conflicting instructions and the current order/status or resolution records needed to support the chosen disposition. Cite only records relevant to the issue.

Maintain one item per review issue, including after it becomes resolved.

| Status | Meaning in this task |
| --- | --- |
| open | An explicit concern remains unresolved and needs review |
| needs_clarification | Current instructions conflict or cannot be applied as written, and require clinician clarification |
| resolved | Documentation establishes that the item's specific concern was addressed |
