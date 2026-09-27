# ChartR implementation handoff

## Task 3 cohort audit `chartr_task3/` v0.1.0 — 29-patient core (September 27, 2026)

Built per `TASK3_BUILD_PROMPT.md` and `TASK_DESIGN_PRINCIPLES.md` (user decisions: `claude-opus-5`, 32K output
cap / 900 s API timeout / 150 turns / 3,500 s, zero tolerance, archive Task 2). Task 2 was never built; its brief
moved to `archive/task2/`. Clinical truth is the CDC 2021 STI guidelines; public docs carry only goal, interface,
output vocabulary and local conventions. 29 patients, 116 candidates (12 confirmed, 9 `cannot_determine`, 8 review
requests). Private engine `qa/task3_rules.py` recomputes every disposition by possible-world evaluation and agrees
with the authored truth; 13 wrong algorithms each fail on exactly their target candidates. See `chartr_task3/README.md`.
Independent second-model review matched all 116 candidates after a wording fix. Verification: offline 101/101; Docker
Task 3 oracle 1, no-op 0, boundary exit 0; Task 1 regression oracle 1, no-op 0 (cloud runs used task copies trusting
the proxy CA for the image build only). Paid pilots not yet run.

## Relevance probe `chartr_relevance/` v0.1.0 (September 27, 2026)

`chartr_notes` plus six authored gaps (idea from `TASK3_BUILD_PROMPT.md`): dose dates known only as a
range, two conflicting reports on one specimen, and outside RPRs referenced but not received; three change
the determination (orchard, meadow, ridge) and three do not (harbor, ridge, summit). Policy states that
completion and branch are established only when identical for every allowed value; new status
`cannot_determine`. Hand-authored golden changes agree with the extended reference; `best_guess` and
`abstain_any_gap` each fail 3 patients. Offline 89/89; Docker oracle 1, no-op 0, boundary exit 0.
Pilots (32K cap, 900 s API timeout): **5/5**, 21–25 turns, 608–697 s, all valid; every gap decided
correctly in every run. Open design question: the "every allowed value" sentence makes relevance
explicit; a v0.2 would keep only output rules ("neither report governs"; "if not established, unclear").

## Messy-notes probe `chartr_notes/` v0.1.0 (September 27, 2026)

Same cases, golden answers and grader as `chartr_graph`; only documentation changes. Corrections,
retractions, some review holds and plan schedules are free-text clinical notes (abbreviations, seven
date styles, records named by charted details never IDs, retractions naming author/date/change,
"correct as charted" confirmations, a nurse's unauthorized travel hold). Public policy maps statement
types to facts, including both hold-ending conventions. Every note reviewed against its private
reading (`solution/readings.json`) for a single interpretation. Offline 77/77; Docker oracle 1, no-op 0,
boundary exit 0. Evidence: `jobs/chartr/notes-0.1.0-*/` (`pilot-summary.json`).

Pilots, `claude-opus-5`, adapter 0.3.1:
- 16K output cap: **4/5**. The failure (`NmrvjSL`) stopped at turn 15 on a single 16,000-token thinking
  block before saving anything: a budget failure, not a reasoning miss. Two passing runs peaked at
  13.3K and 14.0K output tokens in one turn; messy notes make Opus think far longer per turn.
- 32K output cap, API timeout 900 s: **5/5**, 23–31 turns, 511–711 s, peak turn 16.6K tokens.
Every run read all notes and hand-wrote a per-patient table of effective overrides (no regex), then
ran its own solver. All 216 determinations from the nine complete runs were right. Conclusion: free-text
interpretation of this kind is not where Opus fails; use a 32K cap for any text-heavy task.

## Interacting-requirements probe `chartr_graph/` v0.1.0 (September 27, 2026)

Follow-up to `chartr_probe` (5/5). Six patients, three courses and two checkpoints each (36
determinations, 335 R4 resources): scoped amendments with role authority and withdrawal chains,
overlapping review pauses that stretch both the dose-gap and follow-up clocks, titer-conditioned
routine/accelerated schedules, and a per-patient joint allocation of specimens to checkpoints that
must reach the maximum (one specimen per checkpoint, `second` needs `first` plus a separation).
Authored golden answers (`qa/graph_cases.py`) agree with the independent public-record solver on all
36 rows and every optimum. The grader checks row fields exactly and judges the allocation as
constraints, accepting any maximum assignment (38 exist; all tested). Eleven wrong algorithms fail
(greedy allocation 2/6 patients wrong, one-pass pause clock 2/6, the rest 3–6/6). Offline 65/65;
Docker oracle 1, no-op 0; boundary probe exit 0. Note: `-a qa.agents:BoundaryProbe` silently did
not run the probe; `--agent-import-path qa.agents:BoundaryProbe` did.

Pilots (`jobs/chartr/graph-0.1.0-1790530987/opus-pilot/`, adapter 0.3.1, `claude-opus-5`, 150 turns,
16K tokens, 3,500 s): **5/5**, all valid `end_turn`, 21–23 turns, 360–398 s, no API retries; all 180
determinations right. 5.06M input / 0.14M output tokens. Every run wrote a 540–650-line solver:
clause parser with withdrawal resolution and authority, pause union, iterative due dates, then an
exhaustive search for the maximum allocation, and verified its saved rows round-trip. Conclusion:
a fully specified protocol over machine-regular records reduces to programming, which Opus does
without error; adding more rules of this kind is unlikely to change that.

## Dependent-history probe and audit fixes (September 27, 2026)

New `chartr_probe/` v0.1.0: 12 fresh patients, two episodes each, 289 R4 resources,
explicit protocol, no demonstration bank. Scoped amendments and retractions require
reconstructing course membership, counted dose sequence, completion anchor, due date,
and qualifying results. Independently authored expected fields agree with a separate
public-record reconstruction solver. All ten wrong-algorithm controls fail; ID renaming
and record reordering preserve answers. Private implementation and public-surface details
are in `chartr_probe/README.md`; results and resume notes are in `DEPENDENCY_PROBE_HANDOFF.md`.

Legacy fixes: `chartr_proto` 0.1.1 rejects malformed patient types with 400/faults=0;
`chartr_task` 0.5.2 removes P132's computed completion/extra-dose summary while preserving
the actual date and restart retraction. Existing clinical expectations are unchanged.
The old induction fixture is retained as a historical comparison, including its known
near-copy; the new experiment entirely removes demonstration-answer exposure.

Offline suite 52/52 passed, plus the new executable-entrypoint regression check. New probe
Docker oracle 1, no-op 0, isolation probe clean; corrected legacy oracles both 1 and no-ops both 0.
The first new-probe oracle did not execute because solve.sh lacked executable permission;
fixed before paid runs, with the failed setup run retained. Harbor 0.23.0 rejects the bare
custom-agent name; the verified form is `-a anthropic_agent:AnthropicAgent`.
User authorized five paid pilots after free checks; batch completed with adapter 0.3.1,
150 turns / 16K output tokens / 3500 seconds. Evidence root:
`jobs/chartr/dependency-probe-20260927-1790527316201/`.

Result: **5/5 pass**, all valid `end_turn`, 14–25 turns, 315–378 seconds. All 60 patient
determinations, including intermediate fields, passed. Every run read all 12 charts;
no service faults, API retries, tool errors, or truncated outputs. Task hashes matched
the frozen files in all five manifests. Total usage: 3,128,459 input / 118,763 output
tokens, no cache usage. `pilot-summary.json` records per-trial checks and usage.
The model organized charts into compact tables, resolved amendments and episode bindings,
and submitted explicit answers; no private-path accesses appeared in recorded commands.
The probe removes known shortcuts but **does not meet the target failure rate**. Do not
mistake longer responses for a measured reasoning failure, tighten budgets, or hide rules
to force a score. Further paid runs require authorization; proposed next design directions
and limits are in `DEPENDENCY_PROBE_HANDOFF.md`.

## Prototype: follow-up induction `chartr_proto/` v0.1.0 (September 27, 2026)

User-approved prototype of the two strongest difficulty ideas: (1) infer unwritten standards from
31 past determinations instead of reading a rule table, and (2) grade four reasoning fields per
patient (governing plan, due date, completion record, status) for 6 current patients. Separate task
directory; the main task is untouched. Private rule engine `qa/proto_rules.py` with 16 misconceptions,
each contradicted by at least two precedents and failing at least one current case (checked at
build time and by tests). Offline 42/42 (10 prototype tests); Docker oracle 1 (x2), no-op 0,
boundary probe clean.

Prototype pilots (`jobs/chartr/proto-0.1.0-pilot-opus/`): **5/5**, all valid `end_turn`, 17–24 turns,
163–217 s, no API errors, no truncated tool output, no credentials in artifacts. Every run downloaded
all 37 charts, tabulated the 31 past determinations with a script, stated each hidden standard
correctly with the precedents that show it, and got all 24 graded fields right. Diagnosis: the
precedents are clean one-factor contrasts, and nearly every standard matches clinical common sense,
so induction was easy. Harder induction would need standards that go against common sense,
precedents where several factors vary at once, and some standards shown only once.

## Current revision: 0.5.1 — harness robustness (September 27, 2026)

0.5.0 pilots (`jobs/chartr/v0.5.0-pilot-opus/`): **all 5 invalid** (`api_error`,
`APIConnectionError`), every trial failing within the same ~25 s window about 4 minutes in:
a host-side network or API interruption, not the task. Correctly recorded as invalid with no
reward; no credentials in artifacts. Per the framework they are retained and rerun, not
counted.

0.5.1 harness and service changes (no case changes):
- Adapter 0.3.0 (used for the 0.5.1 pilots): transient API failures retried after 10/30/90 s
  with an `api_retry` event per retry; explicit adaptive thinking with summarized display;
  automatic prompt caching; tool-output cap 100,000 characters; missing-key detection fixed.
- Adapter 0.3.1 (current, user decision): ChartR's access is HIPAA-constrained and rejects
  extra API features, so requests are back to exactly the original shape (no caching, no
  thinking parameter, no beta/fallback/gateway features). Kept: identical-request retries,
  the 100K tool-output cap and the missing-key fix. Thinking text is omitted again.
  Behavioral equivalence and an exact cost multiplier were not established by a controlled
  comparison. The 0.5.1 pilots remain historical evidence under adapter 0.3.0; report
  their configuration separately from current 0.3.1 runs.
- Service: evidence accepts typed references (`DocumentReference/R123456`) as review items
  display them, removing the most common wasted 400 in pilots; mismatched types still 400.
Offline 33/33 (new tests: API retry, missing credentials, thinking toggle, typed evidence);
Docker oracle 1 (x2), no-op 0, mocked API error invalid after 3 logged retries, mocked
budget valid.

0.5.1 pilots (`jobs/chartr/v0.5.1-pilot-opus/`): **5/5**, all valid `end_turn`, 17–32 turns,
482–558 s. Two runs survived host connection drops via retries (3 and 4 `api_retry` events),
which previously would have invalidated them. Prompt caching works (nearly all input is cache
reads). Thinking summaries (11–16K chars per run) show every event-history case solved
directly; the only wobble was P117, where one run first inferred from "deliberate contrast"
between twin cases that no flag was needed, then re-read the explicit rule and corrected
itself. Finding: Opus reasons about the benchmark's construction when cases come in
recognizable twins (P117/P123, P118/P124, P103/P121); these should be de-twinned.

## Previous revision: 0.5.0 — event histories (September 27, 2026)

Direction chosen by the user after 0.4.0 (5/5): event-history reconstruction. Eight cases
every pilot solved are switched off; P125–P132 added (see README "Revision 0.5.0" and the
case sheet). Offline 29/29 (11 new wrong-answer variants, each failing on its intended
check); leak audit clean after adding routine counterparts for features left only on
citable records when the easy cases were switched off; Docker oracle 1 (x2), no-op 0.

## Previous revision: 0.4.0 — supersession-boundary cases (September 27, 2026)

0.3.2 pilots (`jobs/chartr/v0.3.2-pilot-opus/`): **4/5**, all valid `end_turn`, no API errors,
max 2.4K output tokens per turn. The failure again missed P117's treatment conflict ("superseded
by the later note reclassifying to early latent on new outside records"). Comparable 0.3.x runs
(same cases, excluding the budget truncation): 12/14, with every miss the same error: inferring
that a later, well-reasoned plan silently supersedes an earlier active order. 0.4.0 targets that
boundary: P121 (history-based reassessment) and P122 (normal CSF) need a treatment-conflict item;
P123 is P117's twin with an explicit cancellation (no item); P124 is P118's twin without the
explicit "replaces" sentence (follow-up timing unclear). TR2's loose phrase "authorized
clarification" now reads "an authorized clarification that explicitly addresses the
disagreement". Cohort 24, 19 expected items. Offline 29/29; Docker oracle 1 (x2), no-op 0.

0.4.0 pilots (`jobs/chartr/v0.4.0-pilot-opus/`): **5/5**, all valid `end_turn`, no API errors,
5.1M input tokens. Every run handled P117, P121–P124 correctly and cited the tightened
"explicit" wording in its reasoning. Conclusion so far: with clearly disclosed rules, Opus 5
makes essentially no errors on this case style; every discriminating miss in 0.3.x came from
loose or ambiguous rule wording. Next direction needs a decision (event-history state
tracking vs. scale).

## Previous revision: 0.3.2 — budget fix (September 27, 2026)

0.3.1 batch B (`jobs/chartr/v0.3.1-pilot-opus-b/`): 4/5. The failure stopped on
`output_truncated` at turn 12 before any writes: its response was a single thinking block
that used the whole 4,096-token cap. `claude-opus-5` runs adaptive thinking by default
(effort `high`, thinking text omitted) even though the adapter sends no thinking options,
and thinking counts toward `max_tokens`. That is a harness budget failure, not a reasoning
signal. 0.3.1 over ten pilots: 8/10; one reasoning slip (P117 supersession inference), one
budget truncation. 0.3.2 raises adapter defaults to `max_tokens` 16,000, API timeout 600 s,
wall 1,770 s, Harbor agent timeout 1,800 s (SDK non-streaming guard does not apply with an
explicit client timeout). Cases unchanged; offline 29/29.

## Previous revision: 0.3.1 — P117 defect fix (September 27, 2026)

0.3.0 pilots (`jobs/chartr/v0.3.0-pilot-opus/`): 1/5 raw, all valid `end_turn`, 19–26 turns,
193–245 s, 4.5M input tokens total, no credentials in artifacts. All four failures were the
same single miss, P117/follow_up, which triage attributes to a **task defect**, not the model:
the plan was timed from "completing treatment", the conflicting orders left completion
undocumented under either reading, and the new "not yet due" clause makes "no item" a
defensible (arguably better) answer. Regrading the saved snapshots with either answer
accepted gives 5/5; no other case produced an error or visible hesitation in any run.
0.3.1 gives P117's plan an explicit date (due 2026-09-02), so P117 cleanly needs two items
(treatment conflict + overdue follow-up). Offline 29/29; Docker oracle 1 (×2), no-op 0.

0.3.1 pilots, batch A (`jobs/chartr/v0.3.1-pilot-opus/`): **4/5**, all valid `end_turn`, 22–36
turns, 216–253 s, 5.3M input tokens, no credentials. The failure missed P117's treatment
conflict, reasoning that the second clinician's plan was "clarified by new outside records".
The policy requires an explicit correction, replacement, cancellation or reconciliation,
and the note never mentions the first order (same structure as Morgan, whom the same run
flagged), so this counts as a valid model failure. Borderline: the policy's phrase
"authorized clarification" is loosely worded. Batch B running to reach ten pilots.

## Previous revision: 0.3.0 — prose over structure, twenty patients (September 27, 2026)

See `chartr_task/README.md` "Revision 0.3.0" and `chartr_task1_cases_v0_3.md`.

## Current revision: 0.2.0 — follow-up category and ten patients (September 26, 2026)

See `chartr_task/README.md` "Revision 0.2.0" and the private case sheet
`chartr_task1_cases_v0_2.md`. First difficulty revision: 10 patients, treatment +
follow-up categories, 4 seeded items, 9 expected final items, opaque record IDs, raised
budgets. Offline: 29 tests pass (18 clinic + 11 adapter). Docker: oracle 1 (×2, and ×5 run
concurrently), no-op 0, boundary probe clean (`jobs/chartr/v0.2.0-*`). Opus pilots
(`jobs/chartr/v0.2.0-pilot-opus/`): **5/5 pass**, all valid `end_turn`, 11–25 turns,
115–154 s, 3.3M input tokens total, no credentials in artifacts. Still too easy.

## Previous revision: 0.1.4 — extraneous records (September 26, 2026)

See `chartr_task/README.md` "Revision 0.1.4". Nine routine same-episode records added
(32 resources); citing one fails evidence. Records returned in event-time order.
0.1.3 Opus pilot (`jobs/chartr/2026-09-26__18-25-27/`) passed; it predates this change.
0.1.4 Opus pilot `jobs/chartr/2026-09-26__18-33-58/` scored 1 (10 turns, 70 s). A later
0.1.4 service fix returns 400 (not a trial-voiding 500) for unsupported whitespace.

## Previous revision: 0.1.3 — reduced public docs (September 26, 2026)

See `chartr_task/README.md` "Revision 0.1.3". Agent-visible docs cut to non-inferable
rules/conventions. Offline checks pass;
Docker oracle/no-op and an Opus pilot need rerunning as 0.1.3.

## Previous revision: 0.1.2 — content leak cleanup (September 26, 2026)

See `chartr_task/README.md` "Revision 0.1.2". Fixture text/labels and public docs
no longer pre-state answers; facts, links, grader and expected state unchanged.
Offline: 14 clinic tests pass; oracle 1 (both variants), no-op 0. Docker oracle/no-op
and a fresh Opus pilot still need to be rerun locally and labeled 0.1.2.

## Previous revision: 0.1.1 — hint cleanup (September 26, 2026)

Public examples now use labeled placeholders; authority is a general `author-role`
rule. Both signed Morgan assessments keep distinct authors and share the
`treating-clinician` role. Removed named-case documentation, fixture-transition
commentary, and editorial sentences about absent replacement links/order history.
All clinical facts, dates, statuses, genuine links, Q102, intended dispositions and
accepted evidence alternatives remain unchanged. Canonical generator and derived
fixture/private integrity baseline updated; task/runtime versions are 0.1.1.
Grader, reference, CLI behavior, adapter, dependencies and isolation are unchanged.
README pilot command now uses `-a anthropic_agent`.

Verification: 25 existing offline checks passed; fresh Docker oracle scored **1**
and no-op scored **0**, both valid with no exceptions. Schema/fact/attachment and
public-surface reviews passed. New evidence is in
`jobs/chartr/hint-cleanup-0.1.1-20260926T212013Z/`. All 275 pre-existing artifact
files were hash-checked and preserved, including the successful 0.1.0 Opus pilot
at `jobs/chartr/2026-09-26__15-11-22/`. No paid calls, new tests, dependency changes,
or subagents in this revision. No local verification blockers remain.
The entries below are historical initial-implementation notes; their statements
about no pilot predate that saved pilot. A future model run must be labeled 0.1.1.

## Initial implementation history

Updated after resuming the interrupted implementation, September 25–26, 2026.

**Status:** first working version implemented and locally verified. No paid model
calls, no dependency upgrades, no subagents. `task_1` unchanged relative to commit
`c80925b`; the initial implementation was already committed as `fa90033`. Completion
changes are working-tree changes; no new commit was made.

## Start here

Read `chartr_task/README.md` for architecture, commands, artifact locations and
limitations. Always use `-c chartr_job.yaml` for ChartR and an absolute `--jobs-dir`.
The old `PYTHONPATH="$PWD" ./.venv/bin/harbor run -p task_1 -a anthropic_agent` import
path is preserved; `--print-config` checked it without making model calls.

## Implemented

* One three-patient task, pinned HL7 FHIR R4 4.0.1 JSON schema, 23 initial resources.
* SQLite clinic service, read-only sources, five public CLI operations, audit, frozen
  controller snapshot and private separate verifier. Reset is a new trial/container.
* Q102 identity and original creation preserved; independent deterministic grading
  accepts sufficient alternative evidence sets and nonempty paraphrased explanations.
* Reference uses the same CLI; no private files in agent or clinic image layers.
* Direct async Anthropic loop with configurable model/limits, host-only observable
  trajectory/results/usage/termination logs, explicit truncation/budget/error/cancel
  handling and credential redaction. Standard Messages API only.

## Integration findings already resolved

Harbor **0.23.0**, Anthropic **1.8.0**, jsonschema **4.26.0** were inspected in `.venv`.
Harbor supports service collection hooks and separate verification. Its default host
log mounts violate this task boundary; `ChartREnvironment` removes them and verifies
actual mounts. It also enforces stop-before-collection on recovery paths.
Docker Desktop **29.8.0** could not `docker cp` the service tmpfs snapshot: the small
provider reads the exact file via trusted service exec instead. Solution/test scripts
now have executable modes. Verifier attestation parent directory is created first.
Database connections are explicitly closed; no lingering-resource warnings remain.

## Saved verification (jobs/ is deliberately ignored)

* `jobs/chartr/transfer-smoke-1790365248157768000/`: minimal service counter 7 passes;
  agent-created replacement 999 ignored.
* `jobs/chartr/oracle-resume/`: repaired clinical oracle reward 1.
* `jobs/chartr/oracle-final/`: **two fresh oracle trials, both reward 1**, no exceptions.
  Final source/queue JSON identical; nonces and trial IDs distinct.
* `jobs/chartr/noop-verified/`: valid reward 0.
* `jobs/chartr/boundary-verified/`: privacy probe passes; planted evidence forgery
  ignored; unchanged starting queue correctly scores 0.
* `jobs/chartr/mock-api-error/`: deliberately mocked API fault -> evaluation_error,
  no reward. Harbor reports RewardFileNotFoundError because invalid trials deliberately
  emit no reward; private diagnostics give the actual reason.
* `jobs/chartr/mock-budget/`: mocked real-CLI call -> turn_exhaustion, valid reward 0;
  trajectory, tool result, usage, termination and trusted snapshot retained.
* `jobs/chartr/offline-tests.log`: 24 tests passed (13 clinic + 11 adapter).
* `jobs/chartr/additional-check.log`: one added paraphrase/corrected-state test passed.
  **25 total checks**. The entire current suite is discoverable with unittest.
* `jobs/chartr/verification-summary.json`: all saved development/QA attempts,
  including pre-fix infrastructure failures. Rebuild with `qa/summarize.py`.
* `git diff --check` passed. Original tutorial content unchanged.

## Remaining work / limits

Nothing blocks local oracle/no-op use. A paid Opus pilot was **not run**, as requested.
Use the exact pilot command in the README once authorized. The preserved model ID is
`claude-opus-5`; current account access is unverified without that pilot. No benchmark
pass rate is claimed. This is structural R4 schema validation, not full FHIR API/profile
conformance. Deterministic grading does not validate arbitrary explanation prose.
The provider intentionally pins Harbor 0.23.0 and uses a few inspected Docker-provider
interfaces; retest after any Harbor/Docker upgrade. Requirements pin current packages;
no blind upgrades should be made to the working `.venv`.

Before a ten-run model batch, review one authorized pilot, calibrate if necessary,
then freeze a version. Retain all attempts and distinguish invalid infrastructure
runs from valid score-zero/budget-exhausted runs. Do not regenerate the fixture or
baseline unless intentionally changing and reviewing the task.
