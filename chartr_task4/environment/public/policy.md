Clinical determinations follow current ACC/AHA guidance, including the 2023 ACC/AHA/ACCP/HRS Guideline for the Diagnosis and Management of Atrial Fibrillation. Clinic instructions in the chart and in clinic documents govern where they apply. Documentation dated after the evaluation time has no effect.

Review items (category: reason):
- `ANTICOAGULATION: UNTREATED_AF`: atrial fibrillation or flutter for which the guideline recommends anticoagulation, with none current.
- `ANTICOAGULATION: ANTICOAGULANT_WITH_CONTRAINDICATION`: a current anticoagulant despite a documented reason it should not continue without review.
- `QT_SAFETY: PROLONGED_QTC_ON_WATCH_LIST_DRUG`: as defined in clinic documents.
- `FOLLOW_UP: ECG_AFTER_WATCH_LIST_START` and `FOLLOW_UP: INR_AFTER_WARFARIN_DOSE_CHANGE`: monitoring that clinic documents require.
- `CONTRADICTION: DUAL_ANTICOAGULATION`: more than one current anticoagulant.
- `CONTRADICTION: RHYTHM_DOCUMENTATION_CONFLICT`: documentation of the rhythm that an ECG from the same day contradicts.

Follow-up status: `completed` (done within the required time), `overdue` (not done, due on or before the evaluation date), `not_due` (not done, due later), `cannot_determine` (a referenced result not in the chart could have completed it).

ECG findings, for each patient's most recent ECG: `AF` (atrial fibrillation) or `QTC_PROLONGED` (QTc prolonged by the clinic's QT-monitoring definition).
