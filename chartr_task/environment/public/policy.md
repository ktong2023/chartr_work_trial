| Rule | Trigger | Evidence that resolves or prevents the flag | Result |
| --- | --- | --- | --- |
| TR1: unresolved treatment concern | A clinical record explicitly identifies a concern about the current treatment plan that requires review, and available evidence does not establish resolution | An authorized clinician explicitly addresses the same concern and records its disposition; or clear documentation establishes that the concern applies only to a superseded plan | Reason UNRESOLVED_TREATMENT_CONCERN; destination clinical_review; status open |
| TR2: conflicting active plans | Two currently applicable instructions for the same episode disagree on the same treatment decision, with no documented cancellation, supersession, or authoritative reconciliation | An explicit correction, replacement, cancellation, or authorized clarification resolves the disagreement | Reason CONFLICTING_ACTIVE_PLANS; destination clinical_review; status needs_clarification |

Policy details:

- If TR1 and TR2 describe the same underlying conflict, create one item and use CONFLICTING_ACTIVE_PLANS as its primary reason. Do not duplicate the issue.
- Evidence references should identify the concern or conflicting instructions and the current order/status or resolution records needed to support the chosen disposition. Cite only records relevant to the issue.

Maintain one item per treatment-review issue, including after it becomes resolved.

| Status | Meaning in this task |
| --- | --- |
| open | An explicit concern remains unresolved and needs clinical review |
| needs_clarification | Incompatible current instructions require clinician reconciliation |
| resolved | Documentation establishes that the item's specific concern was addressed |
