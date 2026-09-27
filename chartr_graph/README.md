# ChartR interacting-requirements probe v0.1.0

Separate experiment following `chartr_probe` v0.1.0 (5/5). Six synthetic patients, three
treatment courses per patient (one target episode each), two follow-up checkpoints per episode:
36 determinations over 335 limited FHIR R4 resources. The full protocol is public
(`environment/public/policy.md`); there are no demonstrations.

What is new relative to `chartr_probe`:

- **Joint decisions inside one chart.** Each lab specimen can complete at most one checkpoint
  across all of the patient's episodes; a `second` checkpoint needs its `first` completed and a
  minimum specimen separation. The agent must choose an assignment that maximizes completed
  checkpoints, so a locally reasonable choice can block a better overall answer.
- **Paused clocks.** Overlapping review pauses (union, half-open intervals) stretch both the
  inter-dose gap that decides sequence membership and the follow-up clock that sets due dates.
- **Conditional schedules.** Each plan picks a routine or accelerated month pair from a designated
  titer comparison whose reports can be amended or invalidated by laboratory notes.
- **Scoped amendments with authority.** Clinicians amend administrations, plans and pauses;
  laboratory authors amend specimens and reports; withdrawals can target withdrawals. Nurse and
  wrong-role notes are controls that change nothing.

## Answers and grading

Canonical cases: `qa/graph_cases.py` (authored ledgers and golden intermediate facts, written
before running any solver). Renderer and private answer files: `qa/build_graph.py`.
`solution/reference.py` reconstructs everything from public clinic responses and searches for a
maximum assignment; it imports no case sheet, expected answers or generator, and agrees with the
authored answers on every row and every patient's optimum.

`tests/grade.py` compares each row's plan, course, branch, counted doses (as a set), completion
date, due date and paused-day count exactly. The evidence allocation is graded as a constraint
problem: every saved result must be eligible for its checkpoint, specimens must be unique per
patient, `second` needs `first` plus the separation, the total must equal the patient's optimum,
and each unassigned row's status (`blocked`, `overdue`, `not_due`) is checked against the
assignment the agent actually saved. Any maximum assignment passes (38 exist across the six
patients; all are tested). Explanations are checked for nonempty text only.

## Checks

`qa/test_graph.py`: solver/author agreement; reference through the real CLI; every maximum
assignment passes; a valid but smaller one fails; eleven wrong algorithms fail (patients wrong out
of 6): original fields only 6, ignore withdrawals 6, whole-note withdrawal 3, any author may amend
3, ignore pauses 6, double-count overlapping pauses 6, one-pass pause extension 2, always routine 6,
reuse specimens 4, ignore the first-checkpoint prerequisite 3, greedy allocation 2. Also malformed
input returns 400 with no service fault, identity fields are immutable, reads/freeze/forgery
behave, the generator reproduces the fixture, and ID renaming plus reversed record order leave
every row fact unchanged.

```sh
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python qa/build_graph.py
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m unittest qa.test_graph -v
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_graph -a oracle --job-name NAME --jobs-dir "$PWD/jobs/chartr"
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_graph -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 5 -n 5 --ak max_turns=150 --ak max_tokens=16000 --ak wall_timeout_sec=3500 --env-file .env --job-name NAME --jobs-dir "$PWD/jobs/chartr"
```

## Limits

The amendment language is regular, so an agent may write a solver; correct tool-assisted
reasoning counts as success. Wrong-algorithm controls test known shortcuts only. Six patients
is small, and all six share the same record vocabulary. Clinical realism is limited: pauses,
checkpoint windows and the allocation rule are a synthetic retrospective protocol, not care
guidance.
