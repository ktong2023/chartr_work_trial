# ChartR implementation handoff

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
