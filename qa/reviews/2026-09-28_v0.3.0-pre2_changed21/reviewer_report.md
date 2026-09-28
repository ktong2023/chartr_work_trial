# Reviewer report: variants changed after the first 0.3.0 review (second pre-release build)

The same reviewer checked 21 regenerated charts covering every variant the realism and wording fixes touched: F4, F5,
F6 anchors, F7 received-conflict, the contradicted outside series, pending and rejected follow-up, and recollected
background. Agreement with `answer_key.json`: **84/84**.

It confirmed that each earlier concern no longer applies:
- The patient's report now concerns the same doses the received record covers.
- Pending tests are 18–42 days old.
- There is no "hCG drawn" note for the disputed second patient.
- Conception falls during the doxycycline course.
- The external patient is of reproductive age.
- Outside records arrive after the misstated date.
- Rejections now read "hemolyzed".

What remained are the designed judgment calls: a registered, unrejected specimen counts as collected; pregnancy
doesn't matter when treatment is adequate either way; and a clinician's note contradicting a MAR written by someone
else is an unresolved conflict.

It raised one new point: two decisive 12-month specimens fell exactly on the first day of their ±30-day window, so the
answer depended on reading the window as inclusive. That led to the final change. Every specimen that decides a
window now sits at least 5 days inside or outside it, and windows closing within a few days of the evaluation time are
always filled. `qa/build_task3.py` now refuses any build where moving every window edge by 4 days would change a
window's status. Checking the whole cohort found 15 such patients, including core p11, whose pending specimen moved
from 3 to 9 days inside its window. The final build was reviewed again: `2026-09-28_v0.3.0_final60/`.
