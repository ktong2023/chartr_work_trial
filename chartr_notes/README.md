# ChartR messy-notes probe v0.1.0

Same six patients, facts, golden answers and grader as `chartr_graph` v0.1.0 (which Opus passed 5/5
by writing a parser and solver). Only the documentation changes, to isolate whether interpreting
real-looking clinical text is where the model fails.

What changed from `chartr_graph`:

- **Corrections and retractions are free-text clinical notes**, not numbered machine clauses:
  addenda, lab QA notices and nursing notes in ordinary clinical language, with abbreviations
  (pt, BPG, f/u, QNS), mixed date formats (1/22, 1/22/26, Jan 22, January 22nd, 22 Jan,
  2026-01-22), bulleted or single-sentence bodies, filler, and signatures.
- **Records are named by charted details, never IDs**: an injection by its charted date and series
  start date, a specimen or report by collection date, a hold by start date, a plan by entry date
  and series. Retractions name the note by author and date and the change by content.
- **Some review holds exist only in a clinician's note** ("resume 4/1", "paused ... through 3/12"),
  with a nurse's look-alike travel hold that has no authority.
- **Plan schedules are free text** with varied wording ("4x", "fourfold", "6 weeks" or "42 days").
- **Non-changing text**: "correct as charted" confirmations of untouched injections, and routine
  notes that change nothing.

The public policy (`environment/public/policy.md`) defines how statements map to facts, including the
two hold-ending conventions (resume date is the first unpaused day; "through"/"last held day" is the
last paused day). There are no demonstrations.

## Answers, fairness and grading

`qa/build_notes.py` renders `qa/graph_cases.py` and writes, for the reference only,
`solution/readings.json`: the statement each note makes, as an expert reader would extract it. The
reference computes everything else from those readings and the structured chart. Every rendered note
was reviewed against its reading for a single interpretation before any pilot (September 27, 2026).
`tests/grade.py` is identical to `chartr_graph`'s: exact row fields, allocation judged as constraints,
any maximum assignment accepted.

`qa/test_notes.py`: reference agrees with the authored answers; reference through the real CLI; every
maximum assignment (38) passes; a smaller valid one fails; eleven wrong algorithms fail; malformed input
400; notes contain no record IDs, clause numbers or computed conclusions; ID renaming and reversed record
order leave row facts unchanged.

```sh
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python qa/build_notes.py
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m unittest qa.test_notes -v
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_notes -a oracle --job-name NAME --jobs-dir "$PWD/jobs/chartr"
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_notes --agent-import-path qa.agents:BoundaryProbe --job-name NAME --jobs-dir "$PWD/jobs/chartr"
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_notes -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 5 -n 5 --ak max_turns=150 --ak max_tokens=32000 --ak api_timeout_sec=900 --ak wall_timeout_sec=3500 --env-file .env --job-name NAME --jobs-dir "$PWD/jobs/chartr"
```

## Limits

The prose is generated from a finite set of phrasings, so a determined agent could still write a
parser after reading enough notes; reading carefully by hand is equally valid. Single-reading review
was done by the task author, not an independent clinician.

## Pilot result

`claude-opus-5`, adapter 0.3.1. At a 16K output cap: 4/5, the failure a turn-15 thinking block that
consumed the whole cap before any write (budget, not reasoning). At 32K (API timeout 900 s): **5/5**,
511–711 s. Every run hand-transcribed the notes into effective overrides and then ran its own solver;
all determinations right. Use `--ak max_tokens=32000 --ak api_timeout_sec=900` for this task.
