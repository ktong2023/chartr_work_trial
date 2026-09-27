# ChartR Task 3: cohort audit with calibrated abstention — v0.2.0 (300 patients, chain-weighted)

## Expansion 0.2.0 (September 27, 2026)

The 29-patient core (unchanged cases) plus 271 generated patients: **300 patients, 1,200 candidates, 6,579 records,
107 confirmed, 101 `cannot_determine` (69 conflict, 18 pending, 14 outside), 34 review requests.** Generator:
`qa/task3_families.py` (seeded, deterministic); cohort: `qa/task3_cohort.py`. Weighted heavily toward *chained*
cases, where one fact's status must be carried into a different issue or a different patient's chart; 187 of the
~360 non-control candidates are chains, each family pointing both ways (the chain changes the answer / is present
but does not):

| Family | What must be carried | Patients |
|---|---|---|
| F1 identity conflict | label vs accessioning → follow-up; lab/collector corrections by the record's author; accession naming another cohort patient → *their* follow-up | 36 |
| F2 resolved misfile | result in A's chart is B's → A misfiled + A follow-up; B's follow-up satisfied (or just missed) | 30 |
| F4 pending pregnancy test | pending hCG → doxycycline adequacy and pregnancy issue; irrelevant when BPG suffices either way | 18 |
| F5 hCG identity | positive hCG misfiled to / disputed with another cohort patient → her pregnancy → her doxycycline adequacy | 21 |
| F6 corrections | author's dose-date correction → follow-up anchor or series gap; a non-author's contradiction → unresolved | 21 |
| F7 outside first dose | received ED record sets the anchor (even against a later clinic note); unreceived ED dose → anchor unknown | 23 |
| F9 delivery | received hospital record beats a later local note (both directions); unreceived record with conflicting local notes | 14 |
| F3 stage inference | no staging entry: exam text → stage → adequacy and the 24-month test | 13 |
| Single-step | overdue, gaps, untreated, doxy-PEP, rejected, pending, name change, outside records incl. contradicted | 26 |
| Background | clean histories, pregnancies with received deliveries, rejected-then-recollected specimens | 69 |

Every generated instance declares its intended dispositions; the build refuses unless `qa/task3_rules.py` recomputes
all 1,200 exactly, and refuses any record dated after the evaluation time. Surface details vary per instance; no two
instances of a variant share a chart skeleton.

**Independent review:** a second model given only 58 rendered charts (one per variant plus cross-chart partners) and
the public docs matched 231/232 decisions; the miss was a generator bug (a specimen dated after the evaluation time),
fixed. Its concerns led to three more fixes: identity conflicts on pregnancy tests name only female patients; a
partial outside record now states the series was incomplete; the outside-facility rule now says other records do not
change what the facility's record establishes.

**Infrastructure at scale:** the audit log stored the full item list before and after every request (quadratic;
it filled the service's 32 MB tmpfs in the first oracle attempt, correctly classified invalid). It now stores item-state
digests, the one item a write changed, and read digests; the grader replays the chain. Sources are cached in the
service; tmpfs raised to 128 MB. Task timeout raised to 7,200 s.

**Checks:** offline `qa/test_task3.py` 14/14 (all 13 wrong algorithms fail on both core and generated cases; audit
tampering detected; audit linear); Docker oracle 1, no-op 0, boundary exit 0 (cloud CA-copy runs).

Suggested pilot budgets for 300 patients: 250 turns, 32K output, 900 s API timeout, 7,000 s wall.

---

## History: the 29-patient core (0.1.x)

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

## Pilot 0.1.0 (September 27, 2026) and fixes in 0.1.1

Five `claude-opus-5` trials (adapter 0.3.2; 150 turns, 32K output, 900 s API timeout, 3,500 s wall), all valid
`end_turn`, 16–21 turns, 518–676 s, 0.86–1.36M input tokens; peak single-turn output 26.4K (a 16K cap would have
truncated two runs). Artifacts: branch `task3-pilot-results`, `jobs/chartr/task3-0.1.0-pilot-opus/`.

**Raw 0/5.** Every trial failed on two defects, fixed in 0.1.1:
- *Grader defect (all 5):* the correct `MISFILED_RESULT` item for the misfiled RPR cited the owning patient's chart
  (her "RPR drawn" nursing note or specimen record), which the evidence check wrongly rejected. 0.1.1 accepts the
  chart of any patient that shares a specimen accession.
- *Policy wording defect (all 5):* the 24-month follow-up whose only specimen has an unresolved identity was marked
  not overdue. The convention said a test counts when "its specimen was collected", without requiring that the
  specimen be the patient's, and the identity rule spoke only of results; "not an issue" was defensible. 0.1.1 says
  "a specimen from the patient" and makes the identity rule cover specimens. The expected answer is unchanged.

**Defect-adjusted regrade: 4/5.** The one fair miss (trial `EYPqUZh`): coded the delivery date for the pregnancy
requirement as an unresolved conflict between the hospital discharge summary (32 days after treatment) and a later
clinic note (29 days), without applying the published rule that care at another facility is established only by that
facility's record; the other four runs cited that rule. Every other candidate was right in every run: all
undeterminable codes, all determinable-despite-gap cases, all complex-looking non-issues, all review requests,
including unstaged latent = unknown duration, doxy-PEP is not treatment, azithromycin, the 14-day gap in pregnancy,
pending results that do and do not matter, and cross-chart identity. Opus scripted the cohort, then read every chart.

Reading: calibrated abstention on a small, fully readable cohort is not where Opus fails (about 1 fair miss per 125
hard decisions). The misses that did occur were an authority rule applied inconsistently and a second-order
consequence of an unresolved fact (identity conflict → follow-up) that no run connected, though its wording was
defective. 0.1.1: offline tests pass; Docker oracle 1, no-op 0.

## Pilot 0.1.1 (September 27, 2026) and fix in 0.1.2

Five `claude-opus-5` trials, same settings, task-file hashes identical to 0.1.1: all valid `end_turn`, 18–28 turns,
540–647 s, peak single-turn output 21.4K. **Raw 2/5.** Three trials failed evidence validity on a *grader defect*:
they cited the review request being answered, or patient records (MRN/DOB) on identity questions; `tools.md` allows
any record, and 0.1.2 accepts the item's own patient, episode and review requests plus the partner patient on a
shared accession. **Defect-adjusted 4/5.** The one fair miss (`ooZZVWg`) is the same as in 0.1.0: patient 22's
delivery date coded as an unresolved conflict ("no other convention settles the conflict"), not applying the
outside-facility rule. The identity-conflict → follow-up chain, fixed in 0.1.1, was right in all five runs.

Both batches together, defect-adjusted: **8/10**; the only fair miss (2/10) is the outside-facility authority rule
against a tempting later local note. Single-hop chains stated through explicit conventions are solved.

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
