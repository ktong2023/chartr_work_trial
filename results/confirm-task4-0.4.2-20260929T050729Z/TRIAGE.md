# Task 4 final confirmation batch — v0.4.2 (September 29, 2026)

**Headline: 3/10 valid attempts pass** (FfbFpxA, HckdLbS, Uaz9uQt). **This is inside the 2–7/10 target.** It is under the predeclared protocol in
`chartr_task4/README.md` ("Final confirmation protocol, v0.4.2"), scored by
`python3 qa/confirm_summary.py chartr_task4 <this directory>` against frozen commit `98a881a`.

It is not pooled with the v0.4.0 pilot (3/10) or the v0.4.1 confirmation batch (1/10), which stand as those versions' results.

## Provenance and validity

- **Dispatch** (`DISPATCH.txt`): commit `bcfdac4` (protocol documentation only on top of `98a881a`). Every preflight line was
  `ok`. The frozen-files check printed `frozen-files-ok`.
- **Provenance:** `qa/confirm_summary.py` checked every trial's task-file hashes, provider, adapter 0.4.0 hash, model
  `claude-opus-5` and all six budgets against `98a881a`, and found no problems.
- **Configuration:** job `batch`, `-k 10 -n 10`, `max_turns=300`, `max_tokens=64000`, `api_timeout_sec=1800`,
  `wall_timeout_sec=7000`, `tool_timeout_sec=900`, `prompt_cache=true`.
- **Validity:** all 10 attempts ended `end_turn` / valid, with a reward and no exceptions.
  - No invalid attempts, so **no reruns were needed or made**.
  - No budget failures.
- **Run sizes:** 71–136 turns and 37.6–50.7 min each; 55 min for the batch, including the first build of the 0.4.2 service
  image. Output was 113–170K tokens per run.

## Per-attempt triage

Each failure was classified from the saved items and interpretations in the trusted snapshot, compared with the key and with
the ECG reader evidence in `qa/task4/ecg_reads.json`. There are no budget failures and no task or grader defects. Two
failures are strict readings of the stated field rule, and one is a tolerance edge; both points are listed as contested below.

| Attempt | Result | Failing fields | Classification |
|---|---|---|---|
| FfbFpxA | **pass** | — | — |
| HckdLbS | **pass** | — | — |
| Uaz9uQt | **pass** | — | — |
| 46BXFi9 | fail | 109218019 (10007795) QTc 378 ms (accepted 378.6–481.6) | Model: QTc under-read. This is the only failure, and it misses by 0.6 ms (contested point 2) |
| bwXA5S6 | fail | `af_evidence` for 10039997 cites the AF condition plus a progress note (`c2361cad`) that does not mention AF | Model: a non-AF record was cited as AF evidence. This is the only failure; AF, score and factors were right (contested point 1) |
| jNaD9x7 | fail | `af_evidence` for 10020306 cites two AF-naming clinic notes plus an inpatient apixaban order (`a104f805`) | Model: a drug order was cited as AF evidence. This is the only failure; the hidden AF was found (contested point 1) |
| o5seZqt | fail | UNTREATED_AF missed for 10020306 | Model: hidden AF missed. This is the only failure |
| KeH4CQX | fail | UNTREATED_AF missed for 10004235. 109952008 QTc 526 ms (accepted 370.2–499.3) | Model: AF missed despite the restored AF codes, plus a QTc over-read of 27 ms beyond the range |
| MS3GSSY | fail | UNTREATED_AF missed for 10020306. Rate 76 on 106885519 (57–67) and 71 on 101515306 (52.5–62.5), which also fail both QT items' `heart_rate` | Model: hidden AF missed, plus ventricular rate over-counted on two QT-edited tracings (the same pattern as v0.4.0 and v0.4.1) |
| uRTwKAB | fail | UNTREATED_AF missed for 10020306. The 10021312 follow-up cites the telephone note reporting an unreceived outside ECG as `completion_record`. 109218019 QTc 354 ms (378.6–481.6) | Model: hidden AF missed, the unreceived ECG treated as a completion record, and a QTc under-read |

**Failure concepts across the 7 failing runs.** Each run may appear under more than one concept.

| Concept | Runs |
|---|---|
| Hidden AF missed (10020306: 3 runs; 10004235: 1 run) | 4 |
| ECG measurement errors (QTc, rate) | 4 |
| Non-AF record cited as AF evidence | 2 |
| Unreceived outside ECG used as a completion record | 1 |

In 4 runs a single error decides the outcome: 46BXFi9, bwXA5S6, jNaD9x7 and o5seZqt.

## Contested points (none changes the headline)

**1. Over-citation in `af_evidence` (bwXA5S6, jNaD9x7).** `tools.md` defines the field as "records establishing AF". The grader
accepts any subset of AF-establishing records (plus coded dysrhythmias as corroboration) that covers at least one. Both runs
found the correct AF, score and factors, but added one record that does not establish AF:
- bwXA5S6 added a progress note, evidently cited for the medication list;
- jNaD9x7 added an apixaban order, which has other indications.

The rule is stated in the tool contract and applied uniformly, so these count as model errors. A more lenient rule (accept
extras once AF is covered) would have made the headline 5/10. Per the protocol, this batch is not re-scored.

**2. Tolerance edge on 109218019 QTc (46BXFi9).** The floor is 378.6 ms, the lowest agreeing Bazett read minus 40 ms. 46BXFi9
read 378 ms. The miss is 0.6 ms, but it is outside a range that already includes a 40 ms inter-observer margin. uRTwKAB's
354 ms on the same tracing is a clear under-read.

## Comparison (not pooled)

| Version | Batch | Headline |
|---|---|---|
| v0.4.0 | pilot | 3/10 |
| v0.4.1 | confirmation | 1/10 |
| v0.4.2 | **this confirmation** | **3/10** |

The v0.4.2 calibration changes (see the README) are:
- one rhythm-ambiguous tracing;
- 10004235's AF codes restored;
- QRS graded only where a block is required;
- one first-degree AV block made optional.

None of the failures in this batch is on a field those changes touched, except KeH4CQX's miss of 10004235, which now has coded
AF. The failures are the task's intended concepts: hidden AF, ECG measurement, and document-driven follow-up.
