| Rule | Trigger | Evidence that resolves or prevents the flag | Result |
| --- | --- | --- | --- |
| TR1: unresolved treatment concern | A clinical record explicitly identifies a concern about the current treatment plan that requires review, and available evidence does not establish resolution | An authorized clinician explicitly addresses the same concern and records its disposition; or clear documentation establishes that the concern applies only to a superseded plan | Reason UNRESOLVED_TREATMENT_CONCERN; destination clinical_review; status open |
| TR2: conflicting active plans | Two currently applicable instructions for the same episode disagree on the same treatment decision, with no documented cancellation, supersession, or authoritative reconciliation | An explicit correction, replacement, cancellation, or authorized clarification resolves the disagreement | Reason CONFLICTING_ACTIVE_PLANS; destination clinical_review; status needs_clarification |

Policy details:

- An assessment request, laboratory order, referral, or message to a clinician is not proof of completion or resolution.
- Compare instructions addressing the same episode, decision, and period. Different stages of an explicitly sequential plan are not automatically contradictions.
- Use event/effective dates to establish applicability. Use authorship time to understand documentation order. Upload time alone does not establish clinical precedence.
- An explicit replacement relationship takes precedence over simple recency. A later independent plan does not automatically cancel another active order.
- Signed treating-clinician documentation can establish a treatment decision or resolution. Nursing and administrative notes can document concerns and operational facts but do not independently override a signed plan.
- In Morgan's case, both authors have equal authority. Neither has a special precedence rule.
- A medication list changing without documentation addressing the original concern is not sufficient resolution for this task.
- Missing information warrants a flag only when it leaves a documented in-scope treatment concern unresolved. Do not flag every absent chart field.
- A draft plan that is explicitly awaiting review is not automatically a conflicting active plan.
- If TR1 and TR2 describe the same underlying conflict, create one item and use CONFLICTING_ACTIVE_PLANS as its primary reason. Do not duplicate the issue.
- Resolving a review item closes that documented concern only. It does not mean an allergy disappeared, treatment was successful, or all future follow-up is complete.
- Evidence references should identify the concern or conflicting instructions and the current order/status or resolution records needed to support the chosen disposition. Additional relevant references are permitted; indiscriminately attaching the entire chart is not the intended evidence behavior.

For version 0.1, each episode contains at most one treatment-review issue. Maintain one item for that issue, including after it becomes resolved. This is a simplifying fixture assumption, not a general rule that a patient can have only one clinical concern.

| Status | Meaning in this task |
| --- | --- |
| open | An explicit concern remains unresolved and needs clinical review |
| needs_clarification | Incompatible current instructions require clinician reconciliation |
| resolved | Documentation establishes that the item's specific concern was addressed |

Reopening an existing resolved item would be permitted if new in-scope evidence warranted it. The initial fixture does not require that transition. Resolved items are retained; deletion is unavailable.
