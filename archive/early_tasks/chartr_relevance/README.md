# ChartR relevance probe v0.1.0

`chartr_notes` (free-text documentation, 9/9 complete Opus runs correct) plus six authored gaps. It
tests the one reasoning type not yet tried on Task 1: deciding whether a gap in the record changes
the determination. Adapted from the calibrated-abstention idea in `TASK3_BUILD_PROMPT.md`, narrowed
to one patient's fixed protocol. The overlap with Task 3 is an open decision.

| Patient | Gap | Changes the answer? |
|---|---|---|
| harbor | Outside dose dated only "between Jan 26 and Feb 1" | No: every date keeps the gap ≤14 days; completion unchanged |
| orchard | Outside dose dated "between Feb 22 and Feb 26" | Yes: gap 13–17 days; the course is complete or not, so `unclear` (freed specimens let another episode complete both checkpoints) |
| meadow | Two final reports on the comparison specimen, 1:8 and 1:16 (baseline 1:4) | Yes: schedule branch differs, both episodes on that report `unclear` |
| ridge | Two reports, 1:8 and 1:4 | No: routine either way |
| ridge | Outside RPR drawn 8/20, requested, not received | Yes: inside an unassigned checkpoint's window, `cannot_determine` |
| summit | Outside RPR drawn 7/10, not received | No: in no unassigned checkpoint's window |

Public policy additions (`environment/public/policy.md`, "Ranges, conflicting reports and unreceived
results", and one status rule): a range is one unknown date; conflicting titers are one unknown value
among those reported; completion and branch are established only when identical for every allowed
value; an unreceived result cannot complete a checkpoint, and an unassigned checkpoint it would have
been eligible for is `cannot_determine`. New status `cannot_determine`.

## Answers and checks

Golden changes are hand-authored in `qa/build_relevance.py` (`RELEVANCE`); the reference solver
(`solution/reference.py`, extended to enumerate range dates and reported titers) agrees on every row and
optimum. Grader: `chartr_notes`' grader plus the `cannot_determine` rule, judged on the saved assignment.
`qa/test_relevance.py`: all prior checks, every maximum assignment passes, and 13 wrong algorithms fail,
including `best_guess` (range start, designated titer, ignore unreceived results; 3 patients wrong) and
`abstain_any_gap` (any range, conflict or unreceived result means abstain; 3 patients wrong). Offline suite
89/89; Docker oracle 1, no-op 0, boundary exit 0.

```sh
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python qa/build_relevance.py
PYTHONDONTWRITEBYTECODE=1 ./.venv/bin/python -m unittest qa.test_relevance -v
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_relevance -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 5 -n 5 --ak max_turns=150 --ak max_tokens=32000 --ak api_timeout_sec=900 --ak wall_timeout_sec=3500 --env-file .env --job-name NAME --jobs-dir "$PWD/jobs/chartr"
```

## Limits

The relevance rule is stated as a definition ("established only when identical for every allowed value")
because leaving it implicit would let careful readers disagree. Stating it makes the check mechanical for
an agent that enumerates. Six gaps is a small sample.

## Pilot result

`claude-opus-5`, adapter 0.3.1, 32K output cap: **5/5**, all valid, 21–25 turns, 608–697 s. Every
determination right, including all three relevant gaps (`unclear` ×2 patients, `cannot_determine`) and
all three irrelevant ones (definite answers). Evidence: `jobs/chartr/relevance-0.1.0-*/pilot-summary.json`.

## Revision 0.2.0 (minimal relevance wording)

The policy no longer defines when a gap matters. Removed: "established only when they are the same for
every date or value these facts allow", "one unknown value among those reported", and the spelled-out
eligibility test for `cannot_determine`. Kept only output rules: a date range means some date in the
range; conflicting reports mean neither governs; if branch or completion cannot be established from the
record, `unclear`; an unassigned checkpoint an unreceived result could have completed is
`cannot_determine`. Answers, grader and fixture facts unchanged. 0.1.0 is archived at
`archive/chartr_relevance-0.1.0/`. Offline 90/90; Docker oracle 1, no-op 0. Not yet piloted.
Adapter 0.3.2 (all tasks): an API "prompt is too long" rejection now ends the run as a valid
`context_exhausted` failure instead of an invalid API error; context management is left to the model.
