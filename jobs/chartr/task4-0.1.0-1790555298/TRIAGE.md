# Task 4 v0.1.0 pilot triage (Opus 5, 5 valid runs)

The raw grader score was 0/5. After fixing four answer-key defects (listed in chartr_task4/README.md, "Pilot history")
and withdrawing the motion-artifact ECG 109419304, the rescored result is 1/5 (see rescored_answer_key_v2.json).

| Run | Rescored | Reasoning failures |
|---|---|---|
| 2LN2xqH | 1 | none |
| AxyTh6a | 0 | missed UNTREATED_AF for 10004235 (AF only on an older ECG and in inpatient charting) |
| cZyYeak | 0 | missed 10004235; 10018423 trigger cites a later refill order, not the start |
| cejPD9W | 0 | missed 10004235; HR 64 on a 58 bpm tracing (claimed interpolated PVCs; none present) |
| tYz8cPU | 0 | missed 10004235; QTc 521 ms read on a normal ECG with baseline wander (true QTc about 370–430 ms) |

Not counted against the model: tYz8cPU's AF finding and UNTREATED_AF item on the withdrawn motion-artifact tracing.
