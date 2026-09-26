# ChartR implementation handoff

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
