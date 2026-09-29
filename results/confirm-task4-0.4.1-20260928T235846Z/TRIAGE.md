# Task 4 final confirmation batch — v0.4.1 (September 28–29, 2026)

**Headline: 1/10 valid attempts pass** (4VKuoXw). This is under the predeclared protocol in `chartr_task4/README.md`
("Final confirmation protocol"), scored by `python3 qa/confirm_summary.py chartr_task4 <this directory>`.

The result is below the 2–7/10 target and is reported as it stands. Per the protocol, no further batch is run to reach the
target, and this batch is not pooled with the v0.4.0 pilot (3/10), which stays a pilot result.

## Provenance and validity

- **Dispatch** (`DISPATCH.txt`): commit `63a05e4`. Every preflight line was `ok`.
- **Evaluated files:** identical to the frozen commit `19edc3b`, with only READMEs differing. `qa/confirm_summary.py` checked
  every trial's task-file hashes, provider, adapter 0.4.0 hash, model `claude-opus-5` and all six budgets against it, and found
  no provenance problems.
- **Configuration:** job `batch`, `-k 10 -n 10`, `max_turns=300`, `max_tokens=64000`, `api_timeout_sec=1800`,
  `wall_timeout_sec=7000`, `tool_timeout_sec=900`, `prompt_cache=true`, as in `batch/config.json`.
- **Validity:** all 10 attempts ended `end_turn` / valid, with a reward and no exceptions.
  - No invalid attempts, so **no reruns were needed or made**, and no paid calls were made after the batch.
  - No budget failures.
- **Run sizes:** 81–114 turns, 27.5–39.8 min each; 40 min for the batch; 105–161K output tokens per run.
- **Extra files:** `FREEZE.json`, `PROVENANCE_START.json` and `console.log` were written at dispatch. They are retained
  unmodified as dispatch records.

## Per-attempt triage

Each failure was classified from the saved items and interpretations in the trusted snapshot, compared with the key and
with the ECG reader evidence in `qa/task4/ecg_reads.json`. Every failing attempt contains at least one well-supported
genuine error. There are no budget failures and no task or grader defects.

| Attempt | Result | Failing fields | Classification |
|---|---|---|---|
| 4VKuoXw | **pass** | — | — |
| 4jPYbWk | fail | 108912996 (10019172) read SINUS with PR 168 ms, so `NEW_AF` was missed | Model: AF read as sinus. The only failure; see the contested point below |
| 77EhP7W | fail | UNTREATED_AF missed for 10020306 and 10004235. 108912996 read SINUS (PR 162). 104941853 QRS 112 ms and no LBBB. 108211642 QRS 62 ms (floor 65) | Model: hidden AF missed ×2 and an AF misread. Also: QRS on 104941853 under-read against readers of 126–164 ms, with LBBB on the cart and in G's morphology; it fails under the v0.4.0 key too. 108211642's QRS miss is 3 ms, marginal and not decisive |
| ALSct2y | fail | 102280728 (10007058): first-degree AV block not reported | Model: the cart states it, and PR reads are 222 / 216 / 238 ms. The only failure; same pattern as 2 of the v0.4.0 pilot runs |
| CfDqnVD | fail | Rate 82 on 108912996 (accepted 41–74). Rate 74 on the QT-edited 101515306 (52.5–62.5), which also fails the QT item's `heart_rate` | Model: ventricular rate over-counted on two tracings. All three readers read 57.0–57.5 bpm on 101515306 |
| DrFAHv5 | fail | 108195884 changes include `RESOLVED_BUNDLE_BRANCH_BLOCK` (prior 100698634 has no block). 100924231 QRS 112 ms (accepted 51–106) | Model: a block claimed on a prior with QRS 90 / 80 ms (M / G), no block statement and no block morphology. The QRS over-read is secondary |
| FkVc3Wy | fail | 105862861 (10038999) QTc 530 ms (accepted 382–501) | Model: QTc misread on a sinus tachycardia at 108 bpm. The only failure. The other 9 runs read 389–470 ms; this is an outlier, not a tolerance edge |
| ewkP9iU | fail | UNTREATED_AF missed for 10004235 | Model: hidden AF (history line "paroxysmal atrial fibrillation" since v0.3.4, plus an older AF ECG and inpatient charting). The only failure |
| kHM3Xvh | fail | UNTREATED_AF missed for 10020306 and 10004235. 109218019 QTc 363 ms (floor 378.6) | Model: hidden AF missed ×2 is decisive. The QTc miss (15 ms) is secondary |
| kwRjFiH | fail | UNTREATED_AF missed for 10020306 and 10004235. `requirement` on all 5 ECG_AFTER_WATCH_LIST_START items cites `f95e0881` | Model: hidden AF missed ×2. The cited document is a lobby-renovation parking notice, not the ECG-after-start memo (`2a70ec05`); status and due dates were right |

**Failure concepts across the 9 failing runs.** Each run may appear under more than one concept.

| Concept | Runs |
|---|---|
| Hidden AF missed (10004235 and/or 10020306) | 4 |
| ECG measurement or reading errors (rhythm, rate, QTc, conduction, QRS) | 7 |
| Wrong governing document cited | 1 |

In 3 runs the only failure is one ECG reading: 4jPYbWk, ALSct2y and FkVc3Wy.

## Contested points (none changes the headline)

**1. 108912996 rhythm (key `AF`).** Two runs (4jPYbWk, 77EhP7W) read sinus with a PR interval; for 4jPYbWk this is the only failure.

Evidence for AF:
- the cart statement is "Atrial fibrillation";
- two of three readers (M, G) find no P wave, and only neurokit reports a PR;
- 8 of 10 runs read AF;
- an independent check at triage, using all-lead QRS detection that was validated on three control tracings, gives 61 bpm
  with RR intervals varying from 696 to 1,168 ms in no repeating pattern (variation 0.20, median successive difference 217 ms).
  That is irregularly irregular. The controls gave variation of 0.013–0.074.

The label is not blinded-cardiologist adjudicated (a standing limitation in the README). A blinded read of this tracing is
recommended before any later version, but per the protocol it does not change this batch.

**2. The F1 fix (v0.4.1 QRS floor on 104941853).** Rescoring every attempt against the v0.4.0 key gives identical rewards (1/10).
77EhP7W's no-LBBB reading fails the conduction field under either key, so the fix decided no outcome here.

## Comparison (not pooled)

The v0.4.0 pilot, same budgets and model, scored 3/10. Its failures were the same concepts: first-degree AV block missed,
rate over-counting, hidden AF missed, an unsupported conduction or change claim. Only one graded bound differs between the
two keys, and it affects neither batch. The difference between 3/10 and 1/10 is within the run-to-run variation expected at a
roughly 20% pass rate.
