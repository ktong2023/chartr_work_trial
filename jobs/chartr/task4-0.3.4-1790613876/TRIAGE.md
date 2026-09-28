# Task 4 v0.3.4 pilots (Opus 5, 5 valid runs): 1/5 raw and 1/5 rescored against the v0.3.5 key

- **xCZrGaw passes every component.** It is the first full pass since v0.1.
- **Calibration:**
  - 10004235 found in 4/5 runs (it was 2/30 before its note-history change).
  - 10020306 found in 4/5 runs.
- **Genuine failures:**
  - 4QuGdYm missed both AF items; its axis error on 101901982 is ungraded under v0.3.5.
  - SFVnfVD over-counted ventricular rate by 10–23% on four ECGs whose three readers agree. The same error appears in its QT
    item heart rate. It also omitted a magnesium result, marked the unreceived-ECG follow-up overdue instead of
    cannot_determine, and cited a normal-sinus ECG as AF evidence.
  - t64gpFo cited a clinic note that never mentions AF as AF evidence for 10039997 (a second run has now done this). It
    also called first-degree AV block on PR 206 ms, where the cart reads 132.
  - z42axUz raised a QT_SAFETY item for 10019385 from a QTc of 536 ms read on the baseline-wander tracing (true QTc about
    370–430). It also called first-degree AV block on PR 210–225 ms, where the cart reads 142.
- **v0.3.5 key rules** (these change no result in this batch):
  - axis is ungraded when the two axis readers differ by more than 40°;
  - first-degree AV block is forbidden only when the cart's PR is 160 ms or less.
