# Reviewer report: the 0.3.0 release build (one patient per variant, plus linked partners and core p11)

This packet was rendered from the exact fixture that is piloted (`chartr-cohort-audit-0.3.0`). The same second-model
reviewer checked it, deciding every candidate independently from these charts. Agreement with `answer_key.json`:
**240/240** (60 patients × 4 candidates).

Fairness notes, condensed:
- **Window edges.** No answer depends on whether an edge is inclusive. The closest deciding specimens are 5–7 days from
  an edge, and all others are at least 10. The one reading that could still matter is P1c2fe99 under "12 months = 360
  days": 30-day months put the window start on the specimen date. Calendar months are the standard reading, and a
  365.25/12-day month stays within the 4-day check. A month-end first dose (Pdcc0bf0, Dec 31) doesn't matter.
- **Designed judgment calls, answered as authored:**
  - A pending, unrejected specimen counts as collected.
  - Pregnancy status doesn't matter when penicillin was given at the stage's dose.
  - A non-author clinician's note against the MAR is unresolved.
  - An unverified outside shot that couldn't move the anchor far enough (Paa51224) leaves the answer determinable.
  - Unreceived outside care takes precedence over conflicting local notes (the 0.2.2 wording).
  - Stage is inferred from exam and history.
- **Minor inconsistency, no effect on any answer:** an unreceived-delivery chart's gestational age and a preterm
  delivery, noted but answer-neutral.
- **Earlier concerns confirmed resolved:**
  - Contradicted outside series, pending-test ages, disputed hCG pairs, rejection reasons, outside-record arrival
    dates.
