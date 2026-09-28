# Task 4 v0.3.5 pilots: 10 concurrent trials with adapter 0.4.0 caching

**Result: raw 1/10; 4/10 rescored against the v0.3.6 key.** All 10 runs are valid (`end_turn`).

The host lid was closed twice (13:56–14:03 and 14:09–14:29 EDT), which cost about 27 minutes of wall time. Each run
had 1–4 API connection drops, all recovered by identical-request retries.

## Key defects fixed in v0.3.6

These are repeated patterns, each checked against the tracings or records:

- **AF evidence.** Four runs cited 10004235's ICD-9 427.89 ("other specified cardiac dysrhythmias") next to real AF
  evidence. Two of those runs (Murt73D, xZFJm4f) failed on nothing else. Coded dysrhythmias are now accepted as
  corroboration, and at least one AF-establishing record is still required.
- **First-degree AV block on 103036945.** Across ten careful runs, PR read from 140 to 222 ms on a broad P wave; the cart
  reads 142 ms and neurokit 174 ms. The block is now forbidden only when both the cart and neurokit PR are 160 ms or less.
  DiZKdkA failed on nothing else.
- **100924231.** One run read ectopic atrial tachycardia. Across batches this tracing has drawn sinus, 2:1 flutter and
  ectopic atrial readings, and all three are now accepted.

## Passing runs (v0.3.6 key)

AjuVnrX (also passes raw), DiZKdkA, Murt73D, xZFJm4f.

## Genuine failures (6)

- **CWvWGfY:** missed both hidden-AF cases.
- **DE4VRou:** read a slow AF as sinus with premature beats (14/15 runs read it correctly) and missed a
  transient RBBB resolution (8/10 runs got it).
- **bW86LAh:** QTc 500+ ms and RBBB read on the baseline-wander tracing (true QTc about 370–430, QRS about 80–96).
  That produced an extra QT_SAFETY item; a second run has now done this.
- **e8mpFxN:** missed 10004235 and the RBBB resolution.
- **rfo6TJY:** missed 10013049's QT item.
- **uKBCStc:** missed 10004235 and claimed premature beats on regular sinus tracings, which inflated the rates.

## Efficiency

- **Input cost:** caching took uncached input from 18.9M to about 0 tokens per run (17.4M cache reads).
- **Output:** throughput is unchanged at 72–73 tokens/s. Output generation dominates run time.
- **Tool calls:** 2.5–4× slower at 10-way concurrency on battery power (median 0.44 → 1.25 s, p99 67 → 248 s).
- **Clocks:** the adapter's monotonic clock excluded 769 s of deep sleep.
