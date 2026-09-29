# ChartR dependent-history probe v0.1.0

Separate experiment following `chartr_proto`'s 5/5 pilot result. Twelve new synthetic patients,
two episodes per patient, 289 limited FHIR R4 resources, and one determination per target
episode. The full protocol is public; there are no historical answers or demonstrations.
Difficulty comes from combining scoped amendments, partial retractions, retractions of
retractions, course reassignment, dose-sequence reconstruction, replacement relationships,
and result timing. No terminal note supplies a computed completion date or disposition.

## Architecture and grading

The existing `chartr_environment:ChartREnvironment` runs an agent container and a private
clinic service. Sources are immutable; determinations persist in SQLite during a trial.
After agent actions stop, the host controller freezes and collects service state and runs
the separate private verifier. The agent cannot replace the trusted snapshot or access
the grader, reference solution, fixture generator, host mounts, or credentials.

The generator `qa/build_probe.py` renders the separately authored cases in
`qa/probe_cases.py`. Expected fields are manually specified in that case sheet. The private
reference solution independently reconstructs fields from public clinic responses and does
not import the case sheet, expected answers, or generator. Grading compares the governing
plan/course, counted administration IDs, completion/due dates, qualifying result, and status.
Any qualifying result and any dose-list ordering are accepted. Explanation text is checked
only for nonempty text; free-form reasoning quality is not judged.

The clinic checks types, record ownership, schemas, and write rules only. It accepts
operationally valid wrong answers and supplies no correctness feedback. Public policy
defines a synthetic retrospective protocol, not a treatment recommendation or full FHIR API.

## Reproduce

Use the existing project `.venv`; do not upgrade dependencies. From the project root:

```sh
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python qa/build_probe.py
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m unittest qa.test_probe -v
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_probe -a oracle
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_probe -a nop
```

A paid pilot, only when authorized, uses the existing adapter and environment-loaded key:

```sh
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_probe -a anthropic_agent:AnthropicAgent -m claude-opus-5 --ak max_turns=150 --ak max_tokens=16000 --ak wall_timeout_sec=3500 --env-file .env
```

Installed Harbor 0.23.0 requires the explicit `module:Class` custom-agent form above;
the bare `-a anthropic_agent` form is rejected before starting a trial. The import module
is unchanged. The five-run probe adds `-k 5 -n 5` and a unique `--job-name`/`--jobs-dir`. Adapter v0.3.1
keeps the organization's original API request shape: model, max_tokens, tools, messages.
There is no prompt-cache or explicit thinking parameter. Limits are deliberately generous
to distinguish reasoning errors from clipping. See `DEPENDENCY_PROBE_HANDOFF.md` and
`PROGRESS.md` at the repository root for frozen run evidence and interpretation.

## Limits

Ten wrong-algorithm controls test known shortcuts; they do not prove that no shortcut exists.
Opaque IDs and a renamed/shuffled fixture check reduce incidental ID/order dependence.
The amendment language is intentionally regular, so an agent may implement a solver.
Correct tool-assisted reasoning counts as success. This is a dependency probe, not yet a
broad or naturalistic clinical benchmark. Five pilots cannot establish a stable failure rate.
