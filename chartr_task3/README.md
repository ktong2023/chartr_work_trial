# ChartR Task 3: cohort audit with calibrated abstention — v0.3.1 (200 patients, chain-weighted)

## Final confirmation protocol (fixed September 28, 2026, before any confirmation trial)

This batch confirms the pre-final release. It is a new batch: the v0.3.1 pilot below (4/10) stays a pilot result and is not
pooled with it. Nothing in this section changes once the batch has started. Running it makes paid model calls and needs the
user's authorization.

**Frozen configuration**

| | |
|---|---|
| Frozen commit | `19edc3b` on `main`. The checkout may be a later `main` commit only if no evaluated file differs from `19edc3b` (step 2); only READMEs, `PROGRESS.md` and reports may change. Task 3's evaluated files are identical to the v0.3.1 pilot's |
| Task | `chartr/cohort-audit` **0.3.1** (`task.toml`, fixture and baseline `chartr-cohort-audit-0.3.1`) |
| Answer key | `tests/expected.json` sha256 `ffdd6f592cefe259e5886a829e3b9d3918a578f382a041c5a852369610f97517` |
| Fixture | initial digest `4bda15848c03019ce75bf4c239d8724aaf3041e81fd67aeaf5eee177f5df3ab8`, attested by the provider at every trial start |
| Harness | adapter 0.4.0 (`anthropic_agent.py` sha256 `95ce935a…3ead`), provider `chartr_environment.py`, Harbor 0.23.0, anthropic 1.8.0; host environment from `requirements.lock.txt` |
| Model and budgets | `claude-opus-5`; `-k 10 -n 10`; `max_turns=250`, `max_tokens=64000`, `api_timeout_sec=1800`, `wall_timeout_sec=7000`, `prompt_cache=true`, and the default `tool_timeout_sec=60`. These are exactly the v0.3.1 pilot's |
| Host | Docker; no other ChartR trial running (Task 3 and Task 4 batches never overlap); `caffeinate` so the host cannot sleep |

**Exact commands** (bash, from the repository root)

1. Update the checkout: `git fetch origin && git checkout main && git pull --ff-only`
2. Frozen files unchanged (must print `frozen-files-ok`):
   ```bash
   git diff --quiet 19edc3b HEAD -- chartr_task3 ':(exclude)chartr_task3/README.md' anthropic_agent.py chartr_environment.py chartr_job.yaml requirements.lock.txt && echo frozen-files-ok
   ```
3. Preflight (every line must be `ok`): `python3 qa/task3_preflight.py 0.3.1`
4. No other ChartR trial running (must print `idle`): `docker ps --format '{{.Names}}' | grep -q '^chartr_' || echo idle`
5. Create the batch's unique output directory. It is never reused; the command refuses an existing path and records the
   dispatch state:
   ```bash
   D="$PWD/jobs/chartr/confirm-task3-0.3.1-$(date -u +%Y%m%dT%H%M%SZ)"; test ! -e "$D" && mkdir -p "$D" && { git rev-parse HEAD; python3 qa/task3_preflight.py 0.3.1; } > "$D/DISPATCH.txt" && echo "$D"
   ```
6. Run the batch (job name `batch`):
   ```bash
   caffeinate -dims env PYTHONPATH="$PWD" .venv/bin/harbor run -c chartr_job.yaml -p chartr_task3 -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 10 -n 10 --ak max_turns=250 --ak max_tokens=64000 --ak api_timeout_sec=1800 --ak wall_timeout_sec=7000 --ak prompt_cache=true --env-file .env --job-name batch --jobs-dir "$D"
   ```
7. Score: `python3 qa/confirm_summary.py chartr_task3 "$D"`. If it reports `INCOMPLETE`, rerun the same command with
   `-k N -n N`, where N is the number of missing valid attempts. Use the next unused job name (`rerun-1`, `rerun-2`, …) in the
   same `$D`, then score again.
8. Write `$D/TRIAGE.md`, then commit `$D` to the `task3-pilot-results` branch.

**Counting rules** (applied by `qa/confirm_summary.py`; the same rules as the v0.3.1 pilot, made mechanical)

- **Headline:** passes among the first 10 valid attempts, in start order. The 2–7 of 10 target is judged on this number alone.
  It is reported whatever it is, and no further batch is run to reach the target.
- **Invalid attempts** get no reward and are not attempts: API or adapter errors, cancellation, service faults, and evidence or
  integrity failures. Report them and rerun under the same command (step 7) until there are 10 valid attempts.
  - If one job has 3 or more invalid attempts, stop and fix the infrastructure without touching frozen files.
  - If a frozen file must change, the batch is void.
- **Budget failures:** valid attempts that end on output truncation, turn, wall or tool timeout, or context exhaustion count as
  failures in the headline. They are also listed as a separate category. The 64K output cap is part of the frozen
  configuration; the single-command submission pattern seen in 2 of 20 earlier runs is counted, not excused.
- **Provenance:** every trial's manifest must match the frozen task files (README excepted), provider, adapter, model and
  budgets. One mismatch voids the batch; the script exits 1.
- **Triage:** classify each failure from its saved items and trace as a model failure, a task/grader defect, or a budget
  failure.
  - A defect is fixed in a new version and reported separately.
  - This batch is never re-scored.

## Pilot 0.3.1: final frozen batch under the predeclared protocol (September 28, 2026)

**Headline: 4 passes / 10 valid attempts** (2GsKnAe, DGcRpcc, KVWAAfk, djAjB3r), inside the 2–7 of 10 target.

**Setup.** Ten `claude-opus-5` trials, run with exactly the frozen configuration:
- adapter 0.4.0;
- `max_turns=250`, `max_tokens=64000`, `api_timeout_sec=1800`, `wall_timeout_sec=7000`;
- caching on, `-k 10 -n 10`.

The artifacts are on `task3-pilot-results`, in `jobs/chartr/task3-0.3.1-pilot-opus/`.

**Provenance.** Every environment, verifier, solution and instruction file matches v0.3.1. The one differing file is
this README, which matches `52dc127`: the checkout had not yet merged the documentation-only audit response. Nothing
the environment or grader uses differs.

**Run health.**
- All 10 attempts were valid, with no evaluation errors, so none were rerun.
- No API retries.
- 40–67 turns and 1,364–1,856 s per run; 31 minutes for the batch.
- About 0 uncached input tokens and 104–147K output tokens per run.

**Categories (triaged from saved items, charts and traces; no task or grader defect found):**

| Attempt | Category | What it did not account for |
|---|---|---|
| Gn7VPQQ | Budget failure (counted) | Finished its analysis ("I've analyzed all 200 patients"), then tried to write every decision into one command and exceeded the 64K output cap; nothing was saved. Same pattern as 0.3.0's PQ8ap5i. Two other runs peaked at 45K and 42K output tokens, which the 64K cap allowed, and one of them passed |
| B24Thje | Model | A received ED record over a later clinic note that misstates the dose date (F7 received-conflict-late, 1 candidate) |
| PCds9a2 | Model | Label-vs-accessioning identity conflict in its own chart (F1 f: `MISFILED_RESULT` and follow-up); a received hospital delivery date over a later note (F9 hospital-late); unreceived outside injections (single outside_unreceived, answered not-an-issue) |
| Pmzp2Ay | Model | Identity named only on another chart's accessioning entry (F1 partner ×3, one requested) |
| V84v8J2 | Model | A non-author clinician's note disputing the MAR date (F6 dispute ×3); an untreated episode with only a "not-done" injection record; unreceived outside care (single outside_unreceived ×2, core p13) |
| z8iMPfP | Model | Signed dose-date corrections by the MAR's author (F6 anchor-late ×3, gap-worse ×3, gap-better, requested) and the non-author dispute (×3); unreceived outside care (outside_unreceived, core p13) |

The recurring model failures across both 10-run batches are the same small set of concepts. Each is a documented
public convention applied to records the run had access to:
- unreceived outside care that should force abstention (5 of 20 runs);
- signed corrections, or non-author disputes, of administration dates (3);
- identity that only the accessioning entry reveals, or a label/accession conflict not carried into follow-up (4);
- a received outside record over a later local note (2).

The whole 29-patient core was right in every run except p06, p08 and p13 (unreceived outside care and an unresolved
dose discrepancy) and p16 (identity carried into follow-up).

**Observation for any later version (not applied to this batch):** in 2 of 20 runs the model wrote its entire
submission into one tool call and ran past the output cap. A budget should not be what fails a run. Raising the cap
further would need the adapter to stream responses (128K output); the alternative is to leave it as the model's own
strategy failure. The decision is the user's.


## Pilot 0.3.0 (September 28, 2026) and fixes in 0.3.1

Ten `claude-opus-5` trials on the actual 0.3.0 (every task-file hash matches `e9dbe75`), run with adapter 0.4.0,
caching on, `caffeinate`, and `-n 10`. Results branch `task3-pilot-results`, `jobs/chartr/task3-0.3.0-pilot-opus/`.
- **Budgets:** 35–70 turns, 1,496–1,846 s each, 31 min for the whole batch. There were no API retries or stalls.
- **Caching:** input was about 0 uncached tokens per run, with 4.5–17.7M read from cache and 0.34–0.64M written.
- **Run time:** 98% of it is generating 112–149K output tokens per run, so caching cut input cost but barely changed
  wall time.

**Three separate statements (per the 0.3.1 audit, [`TASK3_V031_AUDIT_2026_09_28.md`](../docs/audits/TASK3_V031_AUDIT_2026_09_28.md)):**
1. **Benchmark outcome, v0.3.0: 4 passes / 10 attempts.** Passes were 2qiXgav, RgLAepP, Xqtgqdm and tKW2k6E. All 10
   attempts were valid, and all 10 count in this number.
2. **Retrospective analysis of the 6 failures:** 4 defensible model failures, 1 wording-affected failure and 1
   output-budget failure (below). A reasoning-only view is 4 passes out of the 8 attempts not affected by wording or
   budget (4/9 if CJ4ZKQH is counted). This is an analysis, not a benchmark result, and not a v0.3.1 result.
3. **v0.3.1:** the free verification passed, but no model batch has been run on it yet. The old runs are not
   re-scored against it.

Categorized failures:
- **PQ8ap5i, output budget.** A valid `output_truncated` attempt, not an infrastructure error: one response used the
  whole 32K output cap building a single large submission command, and the adapter correctly did not run the
  incomplete call. It stays in the raw result. The frozen 0.3.1 protocol below raises the cap.
- **CJ4ZKQH, wording.** It treated guideline-based follow-up as requiring a recommendation written in the chart, so
  it missed 41 of the 43 follow-up candidates whose answer was not "not an issue". Its explicit follow-up items were 13
  not-an-issue, 1 confirmed and 1 cannot-determine; it did catch a case with a written 12-month reminder. The v0.3.0
  wording ("recommended at a stated number of months") allowed that reading. 0.3.1 names the CDC as the source.

The four defensible failures below were verified against the charts and each run's saved items. Saying why a run
failed is an inference: several runs filtered records in their own scripts, so some decisive note text never
appeared in what they displayed. A miss may be a failure to retrieve or keep the evidence, not a conscious rejection
of it. Repeated misses across the instances of one family count as one recurring failure, not several.

| Run | Missed (did not account for) |
|---|---|
| 5XayigW | Patient-reported care at another facility whose record was not received: injections elsewhere (×2), core p08, and a PCP RPR (core p13). Also core p06's unresolved MAR-vs-pharmacy dose discrepancy |
| ALwrnZf | Core p16: flagged the specimen identity conflict for `MISFILED_RESULT` but did not carry it into follow-up |
| T9WouCF | A non-author clinician's note disputing the MAR date, which changes follow-up coverage (F6 dispute ×3); also core p13 |
| snDgxNq | Identity named only on another chart's accessioning entry (F1 partner ×3). Its three `RESULT_PENDING` answers on pending, unrejected follow-up specimens (pending_fu ×2, core p11) are listed separately: the v0.3.0 wording was less explicit, and 0.3.1 clarifies it |

**0.3.1 (policy wording only; no case or answer changes):**
- `FOLLOW_UP_OVERDUE` now names the source of the recommendation: "a nontreponemal test that the CDC 2021 guidelines
  recommend at a given number of months after treatment".
- The follow-up convention now says a specimen counts as collected when "the laboratory had not rejected it by the
  evaluation time, whether or not its result is final". The independent reviewer had flagged this reading twice.

**0.3.1 checks:** offline 15/15; Docker (cloud CA copies) oracle 1, no-op valid 0, boundary probe exit 0 (snapshot complete,
frozen, 0 faults). The authored answers and answer key are unchanged from 0.3.0.


## Predeclared protocol for the v0.3.1 batch (fixed before the run)

- **Frozen configuration:**
  - task 0.3.1 at a commit whose preflight passes (`python3 qa/task3_preflight.py 0.3.1` prints only `ok`);
  - adapter 0.4.0;
  - model `claude-opus-5`;
  - `-k 10 -n 10`;
  - budgets `max_turns=250`, `max_tokens=64000`, `api_timeout_sec=1800`, `wall_timeout_sec=7000`,
    `prompt_cache=true`;
  - job name `task3-0.3.1-pilot-opus`.
- **Headline:** raw passes out of 10 valid attempts. The 2–7 of 10 target is judged on this number.
- **Invalid attempts:** evaluation errors (no reward, e.g. an API outage or a service fault) are not attempts. They
  are reported and rerun under the same configuration until there are 10 valid attempts.
- **Budget failures:** valid attempts that end by output truncation, turn exhaustion, wall timeout or context
  exhaustion count as failures in the headline, and are reported as a separate category.
- **Triage:** each failure is classified from its saved items and trace as a model failure, a task/grader defect or a
  budget failure. A defect found in triage is fixed in a new version and reported separately. It does not change this
  batch's headline, and the batch is not re-scored retroactively.

## What a pass measures, and its limits

- **Measured:** correct structured decisions across interacting records. That is every disposition and
  missing-evidence code for all 800 candidates, including calibrated abstention and carrying one fact into another
  issue or patient's chart.
- **Not measured:**
  - The grader checks that citations are admissible and explanations are nonempty, not that they justify the
    decision. Records with no patient subject, such as accessioning entries, are admissible for any patient even when
    irrelevant.
  - The rules engine is independently written but consumes authored case facts. Agreement with the authored answers
    doesn't by itself prove that the rendered records convey every needed fact.
  - The independent reviews cover samples (59, 21 and 60 patients, with linked charts supplied), not all 800
    candidates and not full-cohort retrieval.
  - Case families repeat templates. Instances of one variant are correlated, not independent reasoning tests, and
    the score is an aggregate-reliability test.

## 0.3.0: calibration and run time (user decisions, September 28, 2026)

After pilot 0.2.0 (below): defect-adjusted 0/5, an estimated ~10% pass rate, and 27–51 minutes per run.
- **Run time came from context, not the task.** 98% of each run was waiting on the model. Context reached 350–620K
  tokens per turn, and total input was 13–16M tokens per run, all uncached. Three runs also lost about 15 minutes each
  when a connection stalled; all three failed within 2 s of each other, a host-side network drop.
- **Adapter 0.4.0: opt-in prompt caching.** Enabled with `--ak prompt_cache=true`: one top-level
  `cache_control: {type: ephemeral, ttl: 1h}`, and nothing else in the request changes. Caching affects latency and
  cost, not what the model sees, and on the Claude API cache reads do not count toward input-token rate limits. It is
  **off by default**, so Task 1 and any default run keep exactly the original request shape. That shape was the
  user's 0.3.1 decision, because ChartR's HIPAA-constrained access rejects extra features. Adapter 0.3.0 had used
  caching successfully on this key. The history is append-only, so the automatic breakpoint advances every turn.
- **200 patients.** Each variant keeps two or three instances; five copies added workload but not difficulty, since a
  run applies one rule to every instance of a variant. The background drops from 64 to 26 patients.
- **Option (b):** F7 `unreceived` is removed. That was a patient-reported ED dose that moves the follow-up anchor; the
  answer depended on the 12-month test falling about a week either side of a window, and 3 of 5 runs missed it. The
  same story remains in F7 `unreceived-both` (3 patients), where the answer does not depend on the dose, and its
  review request moved there. `OUTSIDE_RECORD_NOT_RECEIVED` is still exercised by 8 candidates (F9 unreceived
  deliveries, outside injections, and core p08/p13/p19), all right in every 0.2.0 run once the code wording was fixed.
- **Expected pass rate:** roughly 25% at the 0.2.0 per-concept rates (identity only on another chart's accessioning
  entry 2/5, corrections 4/5, early latent 24-month schedule 4/5). Five runs make each rate uncertain.

| Family | Patients (0.3.0) |
|---|---|
| F1 identity conflict | 21 |
| F2 resolved misfile | 20 |
| F4 pending pregnancy test | 12 |
| F5 hCG identity | 16 |
| F6 corrections | 15 |
| F7 outside first dose (received, late, unreceived-both, received-conflict) | 14 |
| F9 delivery | 9 |
| F3 stage inference | 14 |
| Single-step (incl. contradicted outside records) | 24 |
| Background | 26 |
| Core | 29 |

**Counts:** 200 patients, 800 candidates, 4,482 records, 83 confirmed, 61 `cannot_determine` (41 conflict, 12
pending, 8 outside), 34 review requests, 139 of 259 non-control candidates chained.

**Tightening from the independent review, applied cohort-wide:**
- **Contradicted outside series:** a patient's "series completed" report now plainly concerns the doses the received
  record covers, not possible later care.
- **Pending tests:** these are weeks old, not months. A pending follow-up RPR is collected 5–30 days before the
  evaluation time, with its window just closed; pending hCGs are 32–44 days old.
- **Disputed pregnancy tests:** the "hCG drawn" note appears only where ownership is resolved, so the result-pending
  code can't be argued. The positive test falls during the doxycycline course it bears on.
- **External patients** named on pregnancy tests are of reproductive age.
- **Outside records** arrive after any date a later note misstates.
- **Rejection reasons** are ones that fit a serum specimen.
- **Window edges:** every specimen that decides whether a follow-up window was met is at least 5 days inside or outside
  it. Windows closing within days of the evaluation time are filled. The build refuses any cohort where moving every
  window edge 4 days would change a window's status, which rules out inclusive/exclusive and month-end arithmetic
  readings. This moved decisive specimens in 15 patients, including core p11's pending specimen, from 3 to 9 days
  inside its window.
- **Latent F6 generator bug:** the build caught a disputed dose date pushing the 12-month window past the evaluation
  time, so the charted anchor now leaves room for it.

**Independent review.** Three passes by the same second-model reviewer, each given only rendered charts and the public docs:
- **236/236** on one patient per variant.
- **84/84** on the variants the resulting fixes touched.
- **240/240** on the release build itself (60 patients).

All packets, keys, decisions and reports are in `qa/reviews/`.

**Checks:** offline `qa/test_task3.py` 15/15; adapter 15/15, including the new opt-in caching test, with the default
request shape unchanged; Task 1 offline passes. Docker (cloud CA copies, release build): oracle 1, no-op valid 0 (missing 34,
missed 78, overclaim 54), boundary probe exit 0 with the snapshot complete (4,482 records), frozen, 0 faults.


## Pilot 0.2.0 (September 27, 2026) and 0.2.2

Five `claude-opus-5` trials on the actual 300-patient 0.2.0: every task-file hash matches `40162ad`. Results branch:
`task3-pilot-results`, `jobs/chartr/task3-0.2.0-pilot-opus/`, the five trials not in the earlier 0.1.1 set (74VimNs,
EGtYvWL, Kc4VEtB, Qg3K5ne, xrHn2mx). All ended valid `end_turn`, with 52–82 turns, 1,630–3,050 s, 13–17M input and
119–157K output tokens, and a peak turn of 9.6–21.4K. No budget pressure (250 / 32K / 7,000 s). Every run scripted the
cohort.

**Raw 0/5. Defects, all fixed (0.2.1 and 0.2.2), none counted:**
- *Evidence (all 5 runs):* every rejected citation was an accessioning-entry-only link (F1 partner, F5 conflict
  pair), which is the audit's defect. Regraded with the 0.2.1 rule on the same records, every item's evidence passes.
- *Accession collisions (2 runs):* EGtYvWL and Kc4VEtB coded `MISFILED_RESULT` (and twice `FOLLOW_UP_OVERDUE`) as
  unresolved conflicts on 6 of the 8 collision patients. Opus correctly caught the rendering defect.
- *Two codes applied (1 run):* xrHn2mx coded the four unreceived-delivery cases (F9) `UNRESOLVED_SOURCE_CONFLICT`
  instead of `OUTSIDE_RECORD_NOT_RECEIVED`: two local notes disagree on a delivery whose hospital record never arrived,
  and both code definitions literally apply. **0.2.2** adds a precedence sentence to `policy.md`. When the fact is
  unreceived outside care, the code is `OUTSIDE_RECORD_NOT_RECEIVED` even if other records disagree. No authored answer
  changes; no conflict-coded case involves outside care.

**Defect-adjusted: 0/5.** Each run still has at least one fair miss, and every candidate listed below was checked
against its chart and the run's explanation or transcript:

| Fair miss | Runs | What happened |
|---|---|---|
| Unreceived outside first dose (F7 `unreceived`, all 5 instances incl. the requested one) | EGtYvWL, Kc4VEtB, xrHn2mx | Timed follow-up from the clinic's dose, never considering the patient-reported ED dose 12–24 days earlier. If that dose was real, the 12-month test was on time, so the answer is `cannot_determine` / `OUTSIDE_RECORD_NOT_RECEIVED`. The independent reviewer and the other two runs coded it that way. |
| Identity only on the accessioning entry (F1 partner follow-up; F5 pregnancy-test conflict partner) | EGtYvWL, Qg3K5ne (F1 ×4, F5); Kc4VEtB (F5) | Did not find the accessioning entry naming this patient on a specimen filed in another chart, so reported the window missed, or treatment adequate, instead of an unresolved identity. |
| Author corrections (F6: 4 later, 2 earlier, 4 disputed) | Kc4VEtB | Used the charted administration dates, ignoring the administering nurse's signed correction and another clinician's contradiction. |
| Early latent follow-up schedule | 74VimNs | Its script scheduled early latent at 6 and 12 months. CDC 2021 gives 6, 12 and 24 for all latent syphilis, as the other four runs applied. Two 24-month windows missed. |

Everything else was right in all five runs: the whole 29-patient core, including patient 22 under the 0.2.0 wording;
resolved misfiles, pending tests, pregnancy-test misfiles, received and contradicted outside records, and deliveries
with received hospital records. Requested candidates scored 31–34 of 34; the misses sit in unrequested chains.

**Calibration.** Zero tolerance compounds independent concepts. Each run fair-failed 1–3 of 4 concepts, and the two
discovery chains (unreceived first dose, accessioning-only identity) were each right in only 2 of 5 runs. The
estimated pass rate is about 10%, below the 2–7 of 10 target. The 0.2.1 and 0.2.2 fixes would not turn any of these
runs into a pass. Next step: the user's decision on which concept to soften or remove (see [`PROGRESS.md`](../docs/history/PROGRESS.md)), then a 0.2.x
pilot after `python3 qa/task3_preflight.py VERSION`.

**0.2.2 checks:** offline 15/15; Docker (cloud CA copies) oracle 1, no-op valid 0, boundary probe exit 0 (trusted
snapshot complete, frozen, 0 faults).


## 0.2.1: fixes from the independent 0.2.0 audit (September 27, 2026)

[`TASK3_V020_AUDIT_2026_09_27.md`](../docs/audits/TASK3_V020_AUDIT_2026_09_27.md) audited 0.2.0 and found two fairness defects and one overstated difficulty claim. All
three were reproduced, then fixed across the whole 300-patient cohort, not just the cases the audit named.

- **Accession-number collisions (high).** Accession numbers came from a hash reduced mod 9,000 with no uniqueness
  check. Four numbers were shared by two unrelated specimens each, so joining a result to its accessioning entry by the
  documented accession number could return a second patient's identity (one pair had the same test, date and staff).
  The rules engine reads generator facts, so it could not see this. Now every specimen gets its own number, and
  `qa/build_task3.py` rebuilds every result's identity from the rendered records alone (accession number to
  collection record and accessioning entry, MRN plus DOB). The build then refuses unless that matches what the engine
  reads: which charts hold misfiled results, which RPR specimens count toward each patient's follow-up, that every
  identity conflict is a modeled uncertainty, and that every positive hCG unambiguously a patient's makes her pregnant.
  Run against the 0.2.0 fixture, this check stops at the first collision.
- **Cross-chart evidence rejected (high).** The private evidence rule linked patients only through the charts holding
  a result or its specimen, missing a second patient named only by the accessioning entry's MRN and DOB. That is
  exactly how the 5 F1 identity-conflict pairs and 5 F5 pregnancy-test conflict pairs are built. A correct run that
  cited the disputed result for the second patient scored 0; the audit reproduced this, and so did I. Public
  `tools.md` also said "any chart", broader than the grader accepted. The rule is now public and precise in
  `tools.md`. `tests/grade.py` computes it from the attested sources rather than from private build data: a result
  links the patients whose charts hold it or its specimen, and the patients its collection record and accessioning
  entry identify. The audit's exact case now scores 1. A new test checks that the grader's links equal the identity
  relationships the cases were written with, with none missing and none spurious. It also submits every linked
  patient (60) citing the linking result, specimen and accessioning entry plus the other patient's records, and
  requires reward 1.
- **F3 stage inference named the stage (medium).** Every F3 intake note said "Secondary syphilis", "Latent syphilis,
  duration unknown" or "Treating as late latent"; `recorded=False` only dropped the diagnosis-list entry. F3 is
  rewritten in the style of core p01/p12. Notes now give only examination, testing history and the plan, never a stage,
  and nothing else in those charts names one. There are 18 patients (was 13):
  - secondary by exam (1 dose, 6/12-month tests: nothing due);
  - unknown duration, meaning no prior test and no early-latent criterion, with 3 doses but no 24-month test
    (overdue) or 1 dose (inadequate);
  - a matched pair where only the date of a prior nonreactive RPR differs. When it is 3–9 months before diagnosis,
    that is documented seroconversion, so the infection is early latent and one dose is adequate. When it is 15–22
    months before, the infection is of unknown duration and one dose is inadequate.

  A test asserts that no stage word appears in any stage-inference chart (F3 and core p01/p02/p12) and checks the
  pair's 12-month logic.
- **Follow-up missed after seroreversion (from the independent review of the new F3 charts).** Two F3 patients were
  overdue only for a 24-month test after their follow-up RPR had already turned nonreactive. CDC 2021 has no exception
  for this, but some clinicians stop testing then, so the answer should not depend on it. I checked the whole cohort
  and found five more such patients, present since 0.2.0: one F1-e, three F2 (a, c, d) and one F6 anchor-late. Fixed
  for all 300: generated follow-up RPRs turn nonreactive only at the last scheduled test, and the F6 pre-window specimen
  stays reactive. The rules engine now reports missed windows per possible world, and the build refuses any answer that
  depends on a window missed after a nonreactive follow-up. Only result values changed, with no answers moved.

Also: a grammar slip in two generated note templates ("Pt reports they was seen") fixed. The README's 0.2.0 count of
chained candidates was wrong: it is 208 of 359 non-control candidates (0.2.0) and 208 of 363 (0.2.1).
`qa/task3_preflight.py VERSION` checks the checkout before paid runs: versions, fixture digest and a clean
`chartr_task3/`. That is the check that would have stopped the mislabeled 0.1.1 batch. Earlier independent-review
packets and decisions are now kept in `qa/reviews/`, and `qa/task3_review_packet.py` renders new ones.

**Not changed (audit item 4, a direction rather than a defect).** Most generated patients carry one modeled unknown,
and intake-note templates repeat, so 300 patients add more workload than they add reasoning structure. The next
difficulty step, once a 0.2.x pilot shows where Opus stands, is composed complications, where resolving one fact
changes whether another matters, plus more matched counterfactuals. F3's early/lapsed pair is the first of these.

**Counts:** 300 patients, 1,200 candidates, 6,634 records, 109 confirmed, 101 `cannot_determine` (69 conflict, 18
pending, 14 outside), 34 review requests, 208 of 363 non-control candidates chained.

**Independent review:** a second model given only the 18 rewritten F3 charts and the public docs matched all 72
authored decisions. It reported no stage leakage and no boundary-close intervals. Its seroreversion concern is fixed
above. Packet, answer key, its decisions and full report: `qa/reviews/2026-09-27_v0.2.1-pre_f3/`. The final build
differs from the reviewed packet only in ten follow-up values, and the answer key is identical.

**Checks (final build):** offline `qa/test_task3.py` 15/15. This includes the new link-equality and every-link
evidence test, accession uniqueness, and stage-free charts with the matched pair; the build itself runs the rendered
identity and seroreversion checks. Task 1 offline 19/19 and adapter 14/14 are unchanged. The audit's exact failing case
scores reward 1. Docker (cloud CA copies, final build): oracle 1, no-op valid 0
(missing 34, missed 103, overclaim 93), boundary probe exit 0 with the trusted snapshot complete (6,634 records),
frozen, 0 faults.

## Expansion 0.2.0 (September 27, 2026)

The 29-patient core (unchanged cases) plus 271 generated patients: **300 patients, 1,200 candidates, 6,579 records,
107 confirmed, 101 `cannot_determine` (69 conflict, 18 pending, 14 outside), 34 review requests.** Generator:
`qa/task3_families.py` (seeded, deterministic); cohort: `qa/task3_cohort.py`. Weighted heavily toward *chained*
cases, where one fact's status must be carried into a different issue or a different patient's chart; 208 of the
359 non-control candidates are chains, each family pointing both ways (the chain changes the answer / is present
but does not):

| Family | What must be carried | Patients |
|---|---|---|
| F1 identity conflict | label vs accessioning → follow-up; lab/collector corrections by the record's author; accession naming another cohort patient → *their* follow-up | 36 |
| F2 resolved misfile | result in A's chart is B's → A misfiled + A follow-up; B's follow-up satisfied (or just missed) | 30 |
| F4 pending pregnancy test | pending hCG → doxycycline adequacy and pregnancy issue; irrelevant when BPG suffices either way | 18 |
| F5 hCG identity | positive hCG misfiled to / disputed with another cohort patient → her pregnancy → her doxycycline adequacy | 21 |
| F6 corrections | author's dose-date correction → follow-up anchor or series gap; a non-author's contradiction → unresolved | 21 |
| F7 outside first dose | received ED record sets the anchor (even against a later clinic note); unreceived ED dose → anchor unknown | 23 |
| F9 delivery | received hospital record beats a later local note (both directions); unreceived record with conflicting local notes | 14 |
| F3 stage inference | no staging entry: exam text → stage → adequacy and the 24-month test (0.2.0 notes still named the stage; rewritten in 0.2.1) | 13 |
| Single-step | overdue, gaps, untreated, doxy-PEP, rejected, pending, name change, outside records incl. contradicted | 26 |
| Background | clean histories, pregnancies with received deliveries, rejected-then-recollected specimens | 69 |

Every generated instance declares its intended dispositions; the build refuses unless `qa/task3_rules.py` recomputes
all 1,200 exactly, and refuses any record dated after the evaluation time. Surface details vary per instance; no two
instances of a variant share a chart skeleton.

**Independent review:** a second model given only 58 rendered charts (one per variant plus cross-chart partners) and
the public docs matched 231/232 decisions; the miss was a generator bug (a specimen dated after the evaluation time),
fixed. Its concerns led to three more fixes: identity conflicts on pregnancy tests name only female patients; a
partial outside record now states the series was incomplete; the outside-facility rule now says other records do not
change what the facility's record establishes.

**Infrastructure at scale:** the audit log stored the full item list before and after every request (quadratic;
it filled the service's 32 MB tmpfs in the first oracle attempt, correctly classified invalid). It now stores item-state
digests, the one item a write changed, and read digests; the grader replays the chain. Sources are cached in the
service; tmpfs raised to 128 MB. Task timeout raised to 7,200 s.

**Checks:** offline `qa/test_task3.py` 14/14 (all 13 wrong algorithms fail on both core and generated cases; audit
tampering detected; audit linear); Docker oracle 1, no-op 0, boundary exit 0 (cloud CA-copy runs).

Suggested pilot budgets for 300 patients: 250 turns, 32K output, 900 s API timeout, 7,000 s wall.

---

## History: the 29-patient core (0.1.x)

**Third 0.1.1 batch (mislabeled).** The results-branch folder `task3-0.2.0-pilot-opus` holds five trials whose task
files match commit `f2b8a1b` (0.1.1) exactly; the local checkout had not been updated, so they are *not* 0.2.0 runs.
All valid `end_turn`, 14–25 turns, 565–670 s, peak turn 28.4K. Raw 1/5; with the 0.1.2 evidence rule 2/5. All three
fair misses are patient 22 (hospital discharge summary vs later clinic note coded as an unresolved conflict). Across
the three 0.1.x batches, defect-adjusted: **10/15**, and every fair miss (5/15 runs) is that one authority case.

The agent audits 29 synthetic syphilis-care patients (one episode each) for four publicly defined issue
types: `INADEQUATE_TREATMENT`, `FOLLOW_UP_OVERDUE`, `MISFILED_RESULT`, `PREGNANCY_TREATMENT_INADEQUATE`.
It does not know how many issues exist or where. For each candidate (episode × issue) the disposition is
`confirmed`, `not_an_issue` or `cannot_determine` with one of three missing-evidence codes
(`RESULT_PENDING`, `OUTSIDE_RECORD_NOT_RECEIVED`, `UNRESOLVED_SOURCE_CONFLICT`). Absence of an item
means `not_an_issue`, except for the eight candidates named in review requests, which need an explicit item.

Design follows [`TASK3_BUILD_PROMPT.md`](../docs/design/TASK3_BUILD_PROMPT.md) and [`TASK_DESIGN_PRINCIPLES.md`](../docs/design/TASK_DESIGN_PRINCIPLES.md): clinical truth is the CDC 2021 STI
Treatment Guidelines, not a published protocol. The public docs (`instruction.md`,
`environment/public/policy.md`, `tools.md`) contain only the goal, the interface, the output vocabulary and
local conventions (evaluation time, follow-up windows, identity evidence, correction/outside-record
authority, unresolved conflicts). There are no adequacy tables, schedules, staging rules or hints.

## Cohort (private; `qa/task3_cases.py`)

116 candidates: 12 confirmed, 9 `cannot_determine` (3 per code), the rest `not_an_issue`.

| Kind | Candidates | Examples |
|---|---|---|
| Real issues | 7 | unknown-duration latent with one dose; 18-day gap in a late latent series; untreated primary; cross-chart misfile |
| Judgment from standard of care | 4 | unstaged latent with no evidence of recent infection = unknown duration; secondary treated only with azithromycin; doxy-PEP is not treatment |
| Relevance: gap present, answer still definite | 8 | stage conflict where both stages are early; pending 12-month specimen collected in window; delivery elsewhere but bounded by a later prenatal visit; pregnancy unknown but one of three doses fails either way |
| Undeterminable | 9 | MAR 2.4 MU vs pharmacy 1.2 MU; injections reportedly given elsewhere; RPR reportedly drawn by a PCP; label vs accessioning identity conflict (2 candidates); delivery date needed; pending pregnancy test with doxycycline (2) or an incomplete series |
| Complex-looking non-issues | 7 | nurse's own dose correction; outside injections received; hemolyzed then recollected; misfiled result that belongs to this patient; former-name label; hospital delivery date beats a later local note; restaged early latent after two doses |
| Controls | the rest | clean histories, including a pregnant patient |

## Truth, grading and checks

`qa/task3_rules.py` recomputes every disposition from each patient's clinical facts by evaluating every
possible world of the patient's single unknown; the build refuses to write if it disagrees with the
authored truth. `tests/grade.py` grades every candidate exactly (zero tolerance), requires explicit items
for review requests, checks evidence against the public rule in `tools.md` (records of the patient or of a patient
linked through a laboratory result, or clinic-level records), computed from the attested sources, and reports diagnostics by case kind × issue, error type
(overclaim, underclaim, wrong code, false flag, missed, missing) and requested vs unrequested.
Citation sufficiency and explanation prose are not graded. Invalid runs produce no reward.

The rules engine reads authored facts, so the build also checks the rendered records that decide authority: every F6 date the engine
takes from a correction must be signed by the nurse who charted that administration, and every disputed date by someone else
(release validation, September 28, 2026; build-time check only, no task file or answer changed).

`qa/test_task3.py` (12 tests): rules agree with authored truth and the build is reproducible; reference
passes through the real CLI (including export); no-op fails; 13 wrong algorithms each fail on exactly their
target candidates (never abstain, abstain on any gap, flag everything, per-patient processing, ignore received
outside records, ignore unreceived ones, pending as negative, pending as not collected, latest source wins,
default unstaged to late, doxy-PEP as treatment, non-pregnant interval tolerance in pregnancy, structured
fields only); zero-tolerance and absence semantics; evidence validity; recoverable 400s with no service
faults; export completeness and freeze; public-surface leak checks; identity evidence on every result;
ID renaming and record reordering leave every answer unchanged.

```sh
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python qa/build_task3.py
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m unittest qa.test_task3 -v
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task3 -a oracle --job-name NAME --jobs-dir "$PWD/jobs/chartr"
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task3 -a nop --job-name NAME --jobs-dir "$PWD/jobs/chartr"
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task3 --agent-import-path qa.agents:BoundaryProbe --job-name NAME --jobs-dir "$PWD/jobs/chartr"
# Paid pilots (authorize first; the preflight must print all ok):
python3 qa/task3_preflight.py 0.3.1
caffeinate -dims env PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task3 -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 10 -n 10 --ak max_turns=250 --ak max_tokens=64000 --ak api_timeout_sec=1800 --ak wall_timeout_sec=7000 --ak prompt_cache=true --env-file .env --job-name NAME --jobs-dir "$PWD/jobs/chartr"
```

## Independent review (September 27, 2026)

A second model, given only the rendered charts and the public docs, decided all 116 candidates. It matched
the authored answers on 114; both misses were one wording ambiguity (whether pregnancy bears on
`INADEQUATE_TREATMENT`), fixed in the issue definitions, after which it matched all 116. The pregnant
patient's dose gap was widened from 11 to 14 days because CDC does not define a "missed" dose in pregnancy by
days. Residual concerns it raised: a later local note versus the hospital's delivery date (settled by the
published outside-record rule, 32 vs 29 days); a pregnancy test pending for three months (realistic as a lost
send-out, still `RESULT_PENDING`); an ongoing pregnancy with incomplete treatment counts as an issue now.

## Verification (September 27, 2026)

Offline suite 101/101 (all tasks, including adapter tests, Harbor 0.23.0 / anthropic 1.8.0 / jsonschema 4.26.0 in a
fresh venv). Docker (cloud container): Task 3 oracle 1, no-op 0 (valid; errors missing 8, missed 10, overclaim 7),
boundary probe exit 0; Task 1 0.5.2 regression oracle 1, no-op 0. These Docker runs used temporary copies of the
tasks whose service Dockerfile adds two lines trusting the cloud proxy's CA so `pip install` could build; every other
file was identical. Evidence: `jobs/chartr/task3-0.1.0-*-cacopy/`, `jobs/chartr/task1-0.5.2-*-regression-cacopy/`.

## Pilot 0.1.0 (September 27, 2026) and fixes in 0.1.1

Five `claude-opus-5` trials (adapter 0.3.2; 150 turns, 32K output, 900 s API timeout, 3,500 s wall), all valid
`end_turn`, 16–21 turns, 518–676 s, 0.86–1.36M input tokens; peak single-turn output 26.4K (a 16K cap would have
truncated two runs). Artifacts: branch `task3-pilot-results`, `jobs/chartr/task3-0.1.0-pilot-opus/`.

**Raw 0/5.** Every trial failed on two defects, fixed in 0.1.1:
- *Grader defect (all 5):* the correct `MISFILED_RESULT` item for the misfiled RPR cited the owning patient's chart
  (her "RPR drawn" nursing note or specimen record), which the evidence check wrongly rejected. 0.1.1 accepts the
  chart of any patient that shares a specimen accession.
- *Policy wording defect (all 5):* the 24-month follow-up whose only specimen has an unresolved identity was marked
  not overdue. The convention said a test counts when "its specimen was collected", without requiring that the
  specimen be the patient's, and the identity rule spoke only of results; "not an issue" was defensible. 0.1.1 says
  "a specimen from the patient" and makes the identity rule cover specimens. The expected answer is unchanged.

**Defect-adjusted regrade: 4/5.** The one fair miss (trial `EYPqUZh`): coded the delivery date for the pregnancy
requirement as an unresolved conflict between the hospital discharge summary (32 days after treatment) and a later
clinic note (29 days), without applying the published rule that care at another facility is established only by that
facility's record; the other four runs cited that rule. Every other candidate was right in every run: all
undeterminable codes, all determinable-despite-gap cases, all complex-looking non-issues, all review requests,
including unstaged latent = unknown duration, doxy-PEP is not treatment, azithromycin, the 14-day gap in pregnancy,
pending results that do and do not matter, and cross-chart identity. Opus scripted the cohort, then read every chart.

Reading: calibrated abstention on a small, fully readable cohort is not where Opus fails (about 1 fair miss per 125
hard decisions). The misses that did occur were an authority rule applied inconsistently and a second-order
consequence of an unresolved fact (identity conflict → follow-up) that no run connected, though its wording was
defective. 0.1.1: offline tests pass; Docker oracle 1, no-op 0.

## Pilot 0.1.1 (September 27, 2026) and fix in 0.1.2

Five `claude-opus-5` trials, same settings, task-file hashes identical to 0.1.1: all valid `end_turn`, 18–28 turns,
540–647 s, peak single-turn output 21.4K. **Raw 2/5.** Three trials failed evidence validity on a *grader defect*:
they cited the review request being answered, or patient records (MRN/DOB) on identity questions; `tools.md` allows
any record, and 0.1.2 accepts the item's own patient, episode and review requests plus the partner patient on a
shared accession. **Defect-adjusted 4/5.** The one fair miss (`ooZZVWg`) is the same as in 0.1.0: patient 22's
delivery date coded as an unresolved conflict ("no other convention settles the conflict"), not applying the
outside-facility rule. The identity-conflict → follow-up chain, fixed in 0.1.1, was right in all five runs.

Both batches together, defect-adjusted: **8/10**; the only fair miss (2/10) is the outside-facility authority rule
against a tempting later local note. Single-hop chains stated through explicit conventions are solved.

## Reuse

Service, CLI pattern, controller attestation/collection, separate verifier and Harbor provider are reused
from `chartr_notes`. New: bulk export (`GET /export`, CLI writes NDJSON + manifest), review requests,
audit items (one per episode and issue), laboratory accessioning records, evidence from any chart or
clinic-level record. No shared harness file changed.

## Limits

Truth is authored and recomputed by a private engine written by the same author; the independent review
(a second reviewer given only the charts and public docs) is recorded separately. 29 patients is the core
for a first pilot; the plan is to scale the cohort with generated background patients after pilots show
where Opus fails. Clinical realism is synthetic; judgments rely on the 2021 CDC guidance, and cases where
the guidance hedges (for example 10–14-day gaps outside pregnancy) were excluded.
