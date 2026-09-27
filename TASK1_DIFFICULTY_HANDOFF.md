# ChartR Task 1: difficulty handoff

September 27, 2026. **Private:** contains case details and expected outcomes. Never copy it into
any `environment/` directory.

**Goal.** A Harbor task that the target Claude model passes 2–7 times in 10 trials, where the
failures are reasoning errors, not ambiguity, hidden rules, budget limits or tool friction.

**Status.** Not reached. Every fair version so far has been too easy for `claude-opus-5`. This
document covers what was tried, how the model did, what the rule-induction prototype showed, and
the options for going forward.

## 1. Summary

- **50 Opus runs** across 12 versions of the main task and one prototype. 45 were valid; 5 were
  voided by a host-side API outage.
- **38 of 45 valid runs passed.** Of the 7 failures, 4 came from an ambiguous case (a task defect),
  1 from the old 4,096-token output cap, and **2 were reasoning errors**: the same mistake on the
  same case (P117), under policy wording that was then tightened.
- **Since the wording fix (0.4.0): 15 of 15** across the main task and the prototype. If the true
  pass rate were 70%, 15 straight passes would happen about 0.5% of the time.
- Over about **1,470 graded decisions** in valid runs, Opus made 2 reasoning errors: **about 1 in
  700**.
- **It is not stretched.** The longest run used under 10 of its 30 minutes and 36 of 100 turns.
- **Implication.** More decisions of the same kind won't get there. At 1 error in 700, a run needs
  about 500 decisions to fail half the time. We need decision types Opus gets wrong 5–20% of the
  time; 3–14 of those per run put the pass rate mid-band.
- **Recommendation.** Stop adding one lever per version. Build one probe of about 40 candidate cases
  across six untested mechanisms, measure how often Opus misses each, and assemble the final task
  from the cases it actually misses (Option A).

## 2. What was tried

All pilots used `claude-opus-5` through `anthropic_agent.py`; runs are under `jobs/chartr/`. Full
notes are in `PROGRESS.md`; the case sheet is `chartr_task1_cases_v0_3.md`.

| Version | Difficulty change | Patients | Opus | What it showed |
|---|---|---|---|---|
| 0.1.0–0.1.4 | Removed hints (placeholder CLI examples, prose restating answers, case-shaped policy bullets); added routine records so evidence had to be precise | 3 | 5/5 (one run each) | Hygiene, not difficulty |
| 0.2.0 | Follow-up category (overdue, timing unclear); seeded queue items; opaque hashed record IDs | 10 | 5/5 | More decisions, each easy |
| 0.3.0 | Facts moved into prose (no due-date fields, no order–plan links, stale statuses); "not yet due" clause; 10 multi-step cases, each with a tempting shortcut | 20 | 1/5 raw, 5/5 after triage | All 4 failures were one ambiguous case (P117 follow-up): a task defect |
| 0.3.1 | P117's plan given an explicit due date | 20 | 8/10 (two batches) | 1 real miss (see §4); 1 run hit the 4,096-token cap mid-thinking |
| 0.3.2 | Output cap 16,000 tokens; timeouts raised | 20 | 4/5 | The same P117 miss |
| 0.4.0 | Supersession-boundary cases (P121–P124); the conflict rule now needs a clarification that "explicitly addresses the disagreement" | 24 | 5/5 | Precise wording, no misses |
| 0.5.0 / 0.5.1 | Event histories: holds and resumes, retracted revisions, duplicate and not-given doses, rejected specimens, corrected results, a retracted clearance note, nurse vs clinician revisions, an erroneous restart; 8 solved cases switched off | 24 | 0.5.0 invalid (API outage); 0.5.1 5/5 | Chains of 3–5 events solved every time |
| proto 0.1.0 | No rule table: standards inferred from 31 past determinations; 4 graded fields per patient | 6 + 31 past | 5/5 | See §3 |

Anti-shortcut checks have run since 0.2.0 (`qa/test_clinic.py`): record IDs don't separate citable
from routine records, and every type, role, label and author on a citable record also appears on a
routine one. Harness fixes along the way had no effect on difficulty: identical-request retries
after transient API errors, typed evidence references accepted, Unicode whitespace returns a 400
instead of a trial-voiding 500, a higher output cap and timeouts, and a 100,000-character tool-output
cap.

## 3. The induction prototype (`chartr_proto/` 0.1.0)

**Design.** A separate task; the main task is untouched. There is no rule table: the clinic's
follow-up standards are shown only by 31 past determinations (`clinic history`, patients H201–H231)
whose charts the agent can read. For each of six current patients (P301–P306) the agent records a
determination with four graded fields: status, governing plan, due date and completion record. A
right status reached by the wrong route fails.

**Fairness.** `qa/proto_rules.py` is the single source of truth for both the past determinations
and the expected answers. It encodes 16 plausible misconceptions: nurse-entered plans count, a
later plan silently replaces an earlier one, any lab result completes the plan, months are 30-day
blocks, and so on. `qa/build_proto.py` refuses to build unless each is contradicted by at least two
past determinations and changes at least one current answer. `qa/test_proto.py` confirms the
grader fails each wrong answer. Offline 42/42 (10 prototype tests); Docker oracle 1 (×2), no-op 0,
boundary probe clean.

**Result: 5/5**, all valid, 17–24 turns, 163–217 s. Every run downloaded all 37 charts, tabulated
the past determinations with a script, wrote out each standard with the precedents that show it,
and got all 24 fields right.

**Why it was easy.**
- **Clean contrasts.** Most standards were shown by pairs of cases that differ in one factor, and
  several were heavily over-determined: 27 precedents contradict "the baseline test counts", 17
  contradict 30-day months.
- **Common-sense standards.** Nearly every standard matched clinical intuition, so Opus confirmed
  what it already expected instead of inferring anything.

Harder induction is Option B.

## 4. How Opus 5 has held up

**Method, every run.** Reads the docs, downloads every chart, and tabulates structured fields with
a Python script. Then it reads the notes that matter, decides each patient while quoting the policy
clause, writes, re-reads the queue and stops. It recovers from its own 400s. No run probed outside
its boundary or leaked credentials.

**Solved every time (don't reuse these as difficulty):**
- Authority: nurse-entered plans and "per protocol" nurse revisions vs clinician plans.
- Explicit vs implicit replacement of plans and orders (after the 0.4.0 wording).
- Retractions of wrong-patient notes and revisions; holds and resumes.
- Dose counting: duplicates, doses charted but not given, real and erroneous restarts, first vs
  final dose anchors, calendar-month arithmetic.
- Completion evidence: bookings, unrelated visits and tests, self-reports, outside scanned reports,
  rejected specimens and recollections, corrected results, and a result later documented as another
  patient's (in the same chart).
- Seeded queue items: keep open, resolve, reopen a wrongly resolved item; one item per issue.
- Conflicting clinician plans with no reconciliation; a concern addressed vs a different concern
  addressed.

**The one failure mode.** Letting a later, clinically sensible plan silently replace an earlier
active order when the wording left room for it (2 of 14 exposures in 0.3.x). Once the rule said
"explicitly", it never happened again. Opus follows precise rules even against clinical intuition.

**It reads the test design.** Opus spotted twin cases (P117/P123, P118/P124, P103/P121) and called
them a "deliberate contrast". Cases must not come in recognizable pairs.

**Headroom and usage.** At most 558 s of a 1,770 s limit, 36 of 100 turns, and 88K tokens of
context per request. About 40M input and 0.7M output tokens over all 50 runs.

## 5. Why it keeps passing

1. Every case reduces to "extract the facts, then apply a stated or cleanly shown rule". Opus
   extracts by script and careful reading, then applies rules literally.
2. The reasoning per case is short (3–5 steps) and stays inside one chart.
3. The design leaked structure: twins, one-factor contrasts, standards that match clinical priors.
4. All-or-nothing grading can't make up the gap. At 1 error in 700, the current 48 decisions per
   run give about a 93% pass rate.

## 6. Options

### The arithmetic

With n graded decisions that each have miss rate e, the pass rate is about (1 − e)^n. Aim for a true
pass rate of 35–55%, where a 10-trial batch lands in 2–7 about 90% of the time. At 70%, a batch lands
at 8 or more about 38% of the time.

| Miss rate per decision | Decisions per run for a ~50% pass rate |
|---|---|
| 1 in 700 (today) | ~500 |
| 5% | ~14 |
| 10% | ~7 |
| 20% | ~3 |

### Option A (recommended): probe, measure, assemble

Build about 40 candidate cases across the six mechanisms below and pilot them. Measure each case's
miss rate, then build the final task from the cases Opus actually misses.

**Build.**
- Reuse the prototype's machinery: a private rule engine as the single source of truth, a case
  generator, varied phrasing, misconception coverage, per-field grading. Publish a **written
  protocol** instead of hiding the standards, which avoids the withheld-conventions concern (§7).
- Grade the intermediate reasoning for every patient (governing plan, due date, completion record,
  status; for treatment, the conflicting orders), not only the final flag.
- Mix 2–3 mechanisms per chart in random combinations. Make about 20% of charts controls that look
  just as complicated but have simple answers, so "complicated chart means flag" fails. No twins,
  no ID or layout tells.
- Split into two probe tasks of about 20 patients each. Context peaked at 88K tokens with 24
  patients, and the adapter has no context management.

**Mechanisms (none tested yet):**
1. **Long correction chains, referenced only in prose.** 10–20 events per chart: corrections of
   corrections, a retraction of a retraction, "my note from Tuesday" instead of record IDs. Include
   a date correction that changes which rule applies: the corrected dose date pushes the gap past
   the protocol limit, forcing a restart that a later addendum undoes. Chains of 3–5 events were
   solved; errors should grow with length and nesting.
2. **Cross-chart effects.** A result misfiled to patient A, with the correction only in patient B's
   chart. A lab notice (a new, documented feed) that voids one analyzer's results over a date range,
   identifiable only from each result's text. A duplicate chart whose doses must be combined. Every
   case so far was self-contained, and Opus works one patient at a time.
3. **A dense protocol.** Replace the four-rule table with a protocol of about 25 provisions, with
   defined terms and exceptions, where each answer needs 4–8 of them. Examples: dose-interval limits
   that differ in pregnancy; a late dose restarts the series unless a clinician documents a reason
   within 3 days; follow-up intervals by stage and HIV status; completion only by the same test
   method as baseline; a test more than 30 days early doesn't count. Policy-heavy agent benchmarks
   (τ-bench, DABstep) get their difficulty this way.
4. **Interacting determinations.** One answer feeds another. An unresolved regimen conflict makes
   the completion date, and so the follow-up due date, undeterminable (the protocol says so); a later
   explicit cancellation makes it computable and overdue. Opus currently decides each category
   independently.
5. **Precise rules that cut against intuition.** For example, the interval counts from the date the
   plan was written, or the shorter of two conflicting clinician intervals governs. The only real
   misses came from intuition overriding a rule, but with precise wording Opus complied in 0.4.0.
   Expect a low yield; these are cheap to add.
6. **Quantitative criteria.** A fourfold (two-dilution) titer decline by the 6-month test, measured
   against a baseline from the same method; RPR and VDRL are not comparable; an inadequate response
   creates a new requirement and a review item.

My guess at yield, highest first: 1, 2, 3, 4, 6, 5. If the build must be trimmed, keep 1–3.

**Run and assemble.**
1. Offline tests (every misconception fails, reference passes, leak audit, chart size), then Docker
   oracle and no-op.
2. 5 Opus trials per probe task.
3. Triage every miss. If the public docs and records don't force the expected answer, it's a
   defect: fix it, regrade the saved runs, and don't count it. Otherwise it's a model error; name
   the misconception it matches.
4. Choose cases with real miss rates so the predicted pass rate is about 45%, plus some zero-miss
   cases.
5. Freeze, run 10 fresh trials, and report every run.

**Stop rule.** If no mechanism exceeds about a 5% miss rate, go to Option C or D.

### Option B: harder induction (prototype 0.2)

Keep the no-rule-table design, but make the induction real:
- Standards that are consistent but counter-intuitive: intervals counted from the plan date; a nurse
  plan counts once a clinician co-signs it within 14 days; early tests don't count.
- Precedents where 3–5 factors change at once, so no pair isolates a rule.
- Some standards shown by only one or two precedents.
- A stated guarantee that every past determination is correct under one consistent standard.
- A stronger checker: 3–5 candidate versions of each standard, and a build-time proof that every
  combination consistent with the precedents gives the same current answers.

This measures real hypothesis search, but the yield is uncertain: Opus may write a
hypothesis-testing script, which is still valid reasoning. It also conflicts with a principle in
`TASK2_DESIGN_HANDOFF.md`: "Do not increase difficulty by withholding local conventions." It can run
as a second probe task alongside Option A.

### Option C: scale, only as the last knob

Once miss rates are known, add cases to reach the target; for example, 30 cases at 2.5% gives about
47%. Scale alone is not reasoning difficulty (the Task 2 handoff says the same), and context becomes
a limit. The adapter keeps the full history, and the HIPAA-constrained request shape rules out
server-side context features. Trimming old tool outputs on the client keeps the request shape but
changes agent behavior, so it needs your approval.

### Option D: stop and report the ceiling

If the probe finds nothing Opus misses at a meaningful rate, write that up with the full run and
triage record. The framework says the 2–7 target "is not a reason to change rules during a final
batch or discard valid outcomes".

### Avoid: levers that move the score without measuring reasoning

| Lever | Seen here |
|---|---|
| Loose or ambiguous wording | 0.3.0's four failures were a defect; the P117 misses vanished once the wording was precise |
| Budget pressure | 0.3.1-b stopped at the 4,096-token cap mid-thinking |
| Tool or format friction | Evidence-format 400s (now accepted); the Unicode whitespace 500 (now a 400) |
| Rules not recoverable from docs or records | Never used; keep it that way |
| ID, layout or twin tells (these make it easier) | 0.1.4's routine records were always X06–X08; twins were read as "deliberate contrast" |
| Grading explanation prose | Explanations are only checked for non-empty text |

## 7. Decisions needed

1. **Target model.** Every run used `claude-opus-5`. If ChartR's model is different (for example
   Opus 5.5, `claude-opus-5-5`), confirm before building; nothing here was measured on it.
2. **Withheld conventions.** Is Option B acceptable, given the Task 2 principle?
3. **Shipping format.** Queue reconciliation (`chartr_task`) or graded determinations (the
   prototype's format)? I lean toward determinations: intermediate fields expose reasoning errors
   that a correct final flag can hide.
4. **Scale.** Is it acceptable as the final knob (Option C)?
5. **Commit.** The working tree has uncommitted work, including the HIPAA-compliant adapter 0.3.1.
   `HEAD` (b5d474f) still has adapter 0.3.0, which sends `cache_control` and `thinking`. Commit
   before the next build.

## 8. State, constraints and commands

**Current versions.** `chartr_task` 0.5.1 (24 patients, 19 expected items); `chartr_proto` 0.1.0;
adapter 0.3.1 (uncommitted). The offline suite passed 42/42 on September 27.

**Uncommitted.** Modified: `HANDOFF.md`, `PROGRESS.md`, `anthropic_agent.py`,
`chartr_task/README.md`, `qa/test_adapter.py`. New: `TASK2_DESIGN_HANDOFF.md`, this file,
`chartr_proto/`, `qa/build_proto.py`, `qa/proto_cases.py`, `qa/proto_rules.py`, `qa/test_proto.py`.

**Constraints.**
- Adapter requests carry exactly `model`, `max_tokens`, `tools` and `messages`, because ChartR's
  access is HIPAA-constrained. Re-sending an identical request after a transient error is the only
  addition. No caching, thinking or effort parameters, beta headers or fallbacks.
- Opus 5 thinks by default, and thinking counts toward `max_tokens`; keep it at 16,000.
- Don't upgrade `.venv` or pinned dependencies (Harbor 0.23.0, anthropic 1.8.0, jsonschema 4.26.0).
- Never read or print `.env`; paid runs pass it with `--env-file .env`. API spend is pre-approved.
- Don't use Harbor's `--max-retries`: it deletes failed trial directories.
- Harbor's "Mean" counts invalid runs as 0. Use `qa/summarize.py` (it rewrites
  `jobs/chartr/verification-summary.json`), or each trial's `termination.json` and
  `verifier/diagnostics.json`.
- Edit the generators (`qa/build_fixture.py`, `qa/build_proto.py`), never the generated JSON.
  `COHORT` in `qa/build_fixture.py` switches patients on or off.
- Change cases, not rules, between pilot batches; freeze before the final 10 trials. Commit only
  when the user asks.

**Budgets.** Main task: 100 turns, 16,000 `max_tokens`, 1,770 s wall, 1,800 s Harbor timeout.
Prototype: 150 turns, 3,500 s wall, 3,600 s timeout.

**Commands.**

```sh
./.venv/bin/python -m unittest discover -s qa -p 'test_*.py'
./.venv/bin/python qa/build_fixture.py   # main task fixture and baseline
./.venv/bin/python qa/build_proto.py     # prototype fixture, baseline and answers
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task -a oracle --job-name NAME --jobs-dir "$PWD/jobs/chartr"
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task -a nop --job-name NAME --jobs-dir "$PWD/jobs/chartr"
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 5 -n 5 --ak max_turns=100 --ak max_tokens=16000 --ak wall_timeout_sec=1770 --env-file .env --job-name NAME --jobs-dir "$PWD/jobs/chartr"
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_proto -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 5 -n 5 --ak max_turns=150 --ak max_tokens=16000 --ak wall_timeout_sec=3500 --env-file .env --job-name NAME --jobs-dir "$PWD/jobs/chartr"
./.venv/bin/python qa/summarize.py jobs/chartr
```

**Per trial** (`jobs/chartr/<job>/<trial>/`): `controller/anthropic/events.jsonl` (trajectory),
`controller/anthropic/termination.json` (reason, validity, usage), `verifier/diagnostics.json`
(per-patient checks) and `artifacts/evidence/snapshot.json` (final state and audit log). To name the
error behind a prototype miss, compare the saved determination with `answer(case, {misconception})`
from `qa/proto_rules.py` for each misconception.
