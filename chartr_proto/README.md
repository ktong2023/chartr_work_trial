# ChartR follow-up induction prototype — v0.1.1

A separate Harbor task (the calibrated `chartr_task` is untouched) that tests two harder kinds of
reasoning than the main task:

1. **Inferring rules instead of reading them.** There is no rule table. The clinic's follow-up
   standards are demonstrated only by 31 past determinations (`clinic history`) on other patients
   (H201–H231), whose charts the agent can read.
2. **Grading the reasoning, not just the outcome.** For each of 6 current patients (P301–P306) the
   agent records one determination with four graded fields: the governing plan, the computed due
   date, the completion record and the status. A right status reached by the wrong route fails.

Version 0.1.1 fixes malformed patient arguments producing service faults; fixture clinical facts and expected answers are unchanged.

The domain is repeat-RPR follow-up only. Current cases combine standards, but the audit found that P302 closely repeats H215. This historical induction experiment is retained for comparison; the new `chartr_probe` has no demonstration bank and uses independently authored, dependent histories.

## Fairness design

`qa/proto_rules.py` is the private rule engine and the single source of truth: it produces the
past determinations and the expected answers. It also encodes 16 plausible misconceptions (e.g.
nurse-entered plans count, a later plan silently supersedes, any lab result completes the plan,
month intervals are 30-day blocks). `qa/build_proto.py` refuses to build unless every
misconception is contradicted by at least two past determinations and would fail at least one
current case. `qa/test_proto.py` writes each misconception's answer for every case it affects and
checks that the grader fails it.

Case facts live in `qa/proto_cases.py`; rendering, the fixture and the private answer files come
from `qa/build_proto.py`. Record IDs are opaque hashes; charts stay under 30,000 characters (the
adapter's tool-output cap is 100,000).

## Run

```sh
./.venv/bin/python qa/build_proto.py
./.venv/bin/python -m unittest qa.test_proto -v
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_proto -a oracle --jobs-dir "$PWD/jobs/chartr"
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_proto -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 5 -n 5 --ak max_turns=150 --ak max_tokens=16000 --ak wall_timeout_sec=3500 --env-file .env --jobs-dir "$PWD/jobs/chartr"
```

The service, CLI and grader follow the main task's architecture (sidecar service, controller-only
collection, separate verifier, no reward on invalid runs). The service code here is a modified copy
of `chartr_task/environment/service`: determinations replace review items, and history is read-only.
