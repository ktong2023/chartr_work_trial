# Task 4 v0.3.2 pilots (Opus 5, 5 valid runs): 0/5 raw and 0/5 rescored against the v0.3.3 key

## Calibration effect

- **10020306:** found in 3/5 runs now that AF appears in her note history (it was 0/10 before).
- **10004235:** AF appears only on an older ECG and in inpatient charting. Missed in 5/5 runs; across all batches it has been
  found in 2 of 30 runs.

## Key defects fixed in v0.3.3

Pilot readings were reviewed at high resolution. These rhythms could not be settled, so either reading is now accepted:

- **103992480:** the cart itself says "sinus or ectopic atrial". 2/5 runs described inverted inferior P waves and answered
  OTHER. Now SINUS or OTHER.
- **100924231:** fixed regular 141/min two days after AF. 3/10 runs across two batches called 2:1 flutter. Now SINUS or
  ATRIAL_FLUTTER.
- **108780865 (10004422's prior):** slow irregular rhythm. The cart says AF, but low-amplitude waves may precede each QRS,
  and 8/10 runs read sinus. Now AF or SINUS, so RESOLVED_AF is allowed rather than required.

## Rescored against the v0.3.3 key

- **ECG interpretation and comparison pass in 3/5 runs:** 3g3VNYb, cCSHmmu and ogiRGGM.
- **Remaining ECG errors (genuine):**
  - JjbYE5K misread rates (82 on a ~55 AF tracing) and swapped two tracings' descriptions;
  - MD7QYib gave an axis of -177 on a +86/+139 tracing.
- **Items:** every run misses 10004235, and 3g3VNYb and ogiRGGM also miss 10020306. cCSHmmu fails only on 10004235.
