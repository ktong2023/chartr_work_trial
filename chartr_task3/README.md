# ChartR Task 3: cohort audit with calibrated abstention — v0.1.0 (29-patient core)

The agent audits 29 synthetic syphilis-care patients (one episode each) for four publicly defined issue
types: `INADEQUATE_TREATMENT`, `FOLLOW_UP_OVERDUE`, `MISFILED_RESULT`, `PREGNANCY_TREATMENT_INADEQUATE`.
It does not know how many issues exist or where. For each candidate (episode × issue) the disposition is
`confirmed`, `not_an_issue` or `cannot_determine` with one of three missing-evidence codes
(`RESULT_PENDING`, `OUTSIDE_RECORD_NOT_RECEIVED`, `UNRESOLVED_SOURCE_CONFLICT`). Absence of an item
means `not_an_issue`, except for the eight candidates named in review requests, which need an explicit item.

Design follows `TASK3_BUILD_PROMPT.md` and `TASK_DESIGN_PRINCIPLES.md`: clinical truth is the CDC 2021 STI
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
for review requests, checks that evidence IDs exist and belong to the patient (or are linked identity
records or clinic-level records), and reports diagnostics by case kind × issue, error type
(overclaim, underclaim, wrong code, false flag, missed, missing) and requested vs unrequested.
Citation sufficiency and explanation prose are not graded. Invalid runs produce no reward.

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
# Paid pilots (authorize first):
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task3 -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 5 -n 5 --ak max_turns=150 --ak max_tokens=32000 --ak api_timeout_sec=900 --ak wall_timeout_sec=3500 --env-file .env --job-name NAME --jobs-dir "$PWD/jobs/chartr"
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
