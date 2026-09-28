# Task 4 v0.2.0 pilots (Opus 5, 5 valid runs): 0/5

All five runs fail only identification and item_fields. Each misses the same two UNTREATED_AF items:

- **10020306:** AF documented only in inpatient rhythm charting.
- **10004235:** AF on an older ECG plus inpatient charting.

Every other v0.2.0 addition was handled correctly in all five runs:
- 10013049's QTc above 500 ms, despite a note calling the QT "acceptable";
- 10019385's ECG follow-up under the memo in force at the start;
- the no-requirement look-alike.

None of the runs mentions either missed patient in its reasoning. Every run queried code 220048 (Heart Rhythm) at least once. One (NCwjdED) tallied 2,405 "AF (Atrial Fibrillation)" entries population-wide, yet all identified AF from coded diagnoses alone. These are reasoning failures, not key defects.

Calibration: this is below the 2–7/10 target, and failures concentrate on one skill: using non-diagnosis evidence of AF.
