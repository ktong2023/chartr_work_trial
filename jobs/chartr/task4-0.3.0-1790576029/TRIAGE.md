# Task 4 v0.3.0 pilots (Opus 5, 5 valid runs): 0/5; rescored against the v0.3.1 key, still 0/5

## Key defects fixed in v0.3.1

- **Numeric tolerances were tighter than method-to-method variability.** All five runs measured QTc 30–50 ms below the cart
  and neurokit on the same ECGs, matching the tangent and global readers. PR conventions differ in the same way.
  - QTc is now accepted within every plausible reader ±40 ms.
  - QRS is ±25 ms.
  - PR is graded only through first-degree AV block, and as null in AF.
- **The rhythm-conflict definition was open to ICU charting.** Two runs flagged a nursing "Normal Sinus Rhythm" entry made
  8 minutes after an AF ECG. The policy now says the conflict must be a note documenting a rhythm.

## Genuine failures (v0.3.1 key)

- **Hidden-evidence AF, 5/5 runs.** Every run missed 10020306 (charted rhythm only) and 10004235 (AF only on an older ECG).
- **Prior-ECG misreads:**
  - 4/5 read 10004422's slow AF prior as sinus bradycardia, so they missed RESOLVED_AF.
  - 2/5 called 10023117's sinus tachycardia with LBBB "already paced", so they missed NEW_PACED_RHYTHM.
- **Current-ECG misreads:**
  - the paced rhythm called sinus with LBBB;
  - a 141 bpm sinus tachycardia called atrial flutter;
  - AF rates of 81 and 97 on tracings the readers put at about 55 and 70;
  - QTc 580 ms on a normal ECG;
  - RBBB, or no block at all, on an AF tracing with LBBB;
  - NEW_AF reported when the prior was already AF.

Only one run (qRMKFJU) had flawless interpretations, and even it made one comparison error.
