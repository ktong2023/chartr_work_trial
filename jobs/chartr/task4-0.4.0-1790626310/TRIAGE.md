# Task 4 v0.4.0 final pilots: 10 trials, frozen key, commit d1156b5

**Result: 3/10 on the frozen v0.4.0 key** (3kzLb4o, dsn6HkF, iXuDhuL). No rescoring.

## Run conditions

- All 10 runs valid (`end_turn`); 68–131 turns; 33–49 min on the adapter clock; batch 50 min.
- Adapter 0.4.0 with prompt caching; 10 concurrent trials.
- The host was on AC power for most of the run (it started on battery), and it never slept.
- Each run had 0–3 dropped API connections, all recovered.

## Failures

Every failing run has at least one clearly genuine error:

- **6sqZzHF:** missed first-degree AV block on 102280728, reading PR as 116 ms. Readers put it at 216–238 ms, and 8/10
  runs read 212–225 ms. This was its only failure.
- **v2zAPnA:** the same first-degree AV block missed, reading PR as 185 ms. This was its only failure.
- **ytGv8se:** counted T waves as extra beats ("12 complexes in 10 s") on four regular tracings, so its rates were wrong
  in four interpretations and in two QT items.
- **AF4oAxQ:**
  - the same T-wave double counting, which also led it to call a regular sinus tracing AF;
  - wrong QT-item fields;
  - denied NEW_AF on 10022017, a contested label (see below).
- **Ck2zzzu:**
  - cited a heart-failure code (428.0) as AF evidence for 10004235;
  - denied NEW_AF on 10022017 (contested label).
- **DAozU5p:**
  - cited a normal ECG as AF evidence for 10039997;
  - put the AF diagnosis code among the rhythm-conflict records (contested strictness);
  - one QTc value out of range.
- **qu3V3qP:**
  - missed both hidden-AF cases (10004235, 10020306);
  - missed the transient RBBB resolution;
  - one QRS value out of range.

## Checked and found not to be task defects

**T-wave double counting.** neurokit2 flags extra "beats" on T waves in a few leads of 106885519 and 101515306 (QT-edited)
and of 107689861 and 109419304 (unedited). Plots confirm they are broad T waves, not QRS complexes: R waves are 5–10×
taller. The original 106885519 had no double detections, so the lengthened T wave makes a naive detector more likely to
trip. The passing runs read these rates correctly (e.g. 62 bpm).

## Contested (these change no outcome in this batch; candidates for a later version)

- **107374881 (10022017's prior).** The label is sinus: the cart says "sinus arrhythmia" and the median-based RR
  irregularity is 0.01. But the first seconds are visibly irregular with low-voltage P waves, so an AF reading is
  defensible. Two runs read AF and so denied NEW_AF. Accepting AF/SINUS for this tracing would make NEW_AF allowed, not
  required.
- **Rhythm-conflict records.** An AF diagnosis code alongside the note and the same-day ECG is arguably corroborating,
  the same principle as the v0.3.6 dysrhythmia rule.
