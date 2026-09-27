# ChartR Task 3: cohort audit with calibrated abstention — v0.2.1 (300 patients, chain-weighted)

## 0.2.1: fixes from the independent 0.2.0 audit (September 27, 2026)

`TASK3_V020_AUDIT_2026_09_27.md` audited 0.2.0 and found two fairness defects and one overstated difficulty claim. All
three were reproduced, then fixed across the whole 300-patient cohort, not just the cases the audit named.

- **Accession-number collisions (high).** Accession numbers came from a hash reduced mod 9,000 with no uniqueness
  check. Four numbers were shared by two unrelated specimens each, so joining a result to its accessioning entry by the
  documented accession number could return a second patient's identity (one pair had the same test, date and staff).
  The rules engine reads generator facts, so it could not see this. Now every specimen gets its own number, and
  `qa/build_task3.py` rebuilds every result's identity from the rendered records alone (accession number to
  collection record and accessioning entry, MRN plus DOB). The build then refuses unless that matches what the engine
  reads: which charts hold misfiled results, which RPR specimens count toward each patient's follow-up, that every
  identity conflict is a modeled uncertainty, and that every positive hCG unambiguously a patient's makes her pregnant.
  Run against the 0.2.0 fixture, this check stops at the first collision.
- **Cross-chart evidence rejected (high).** The private evidence rule linked patients only through the charts holding
  a result or its specimen, missing a second patient named only by the accessioning entry's MRN and DOB. That is
  exactly how the 5 F1 identity-conflict pairs and 5 F5 pregnancy-test conflict pairs are built. A correct run that
  cited the disputed result for the second patient scored 0; the audit reproduced this, and so did I. Public
  `tools.md` also said "any chart", broader than the grader accepted. The rule is now public and precise in
  `tools.md`. `tests/grade.py` computes it from the attested sources rather than from private build data: a result
  links the patients whose charts hold it or its specimen, and the patients its collection record and accessioning
  entry identify. The audit's exact case now scores 1. A new test checks that the grader's links equal the identity
  relationships the cases were written with, with none missing and none spurious. It also submits every linked
  patient (60) citing the linking result, specimen and accessioning entry plus the other patient's records, and
  requires reward 1.
- **F3 stage inference named the stage (medium).** Every F3 intake note said "Secondary syphilis", "Latent syphilis,
  duration unknown" or "Treating as late latent"; `recorded=False` only dropped the diagnosis-list entry. F3 is
  rewritten in the style of core p01/p12. Notes now give only examination, testing history and the plan, never a stage,
  and nothing else in those charts names one. There are 18 patients (was 13):
  - secondary by exam (1 dose, 6/12-month tests: nothing due);
  - unknown duration, meaning no prior test and no early-latent criterion, with 3 doses but no 24-month test
    (overdue) or 1 dose (inadequate);
  - a matched pair where only the date of a prior nonreactive RPR differs. When it is 3–9 months before diagnosis,
    that is documented seroconversion, so the infection is early latent and one dose is adequate. When it is 15–22
    months before, the infection is of unknown duration and one dose is inadequate.

  A test asserts that no stage word appears in any stage-inference chart (F3 and core p01/p02/p12) and checks the
  pair's 12-month logic.
- **Follow-up missed after seroreversion (from the independent review of the new F3 charts).** Two F3 patients were
  overdue only for a 24-month test after their follow-up RPR had already turned nonreactive. CDC 2021 has no exception
  for this, but some clinicians stop testing then, so the answer should not depend on it. I checked the whole cohort
  and found five more such patients, present since 0.2.0: one F1-e, three F2 (a, c, d) and one F6 anchor-late. Fixed
  for all 300: generated follow-up RPRs turn nonreactive only at the last scheduled test, and the F6 pre-window specimen
  stays reactive. The rules engine now reports missed windows per possible world, and the build refuses any answer that
  depends on a window missed after a nonreactive follow-up. Only result values changed, with no answers moved.

Also: a grammar slip in two generated note templates ("Pt reports they was seen") fixed. The README's 0.2.0 count of
chained candidates was wrong: it is 208 of 359 non-control candidates (0.2.0) and 208 of 363 (0.2.1).
`qa/task3_preflight.py VERSION` checks the checkout before paid runs: versions, fixture digest and a clean
`chartr_task3/`. That is the check that would have stopped the mislabeled 0.1.1 batch. Earlier independent-review
packets and decisions are now kept in `qa/reviews/`, and `qa/task3_review_packet.py` renders new ones.

**Not changed (audit item 4, a direction rather than a defect).** Most generated patients carry one modeled unknown,
and intake-note templates repeat, so 300 patients add more workload than they add reasoning structure. The next
difficulty step, once a 0.2.x pilot shows where Opus stands, is composed complications, where resolving one fact
changes whether another matters, plus more matched counterfactuals. F3's early/lapsed pair is the first of these.

**Counts:** 300 patients, 1,200 candidates, 6,634 records, 109 confirmed, 101 `cannot_determine` (69 conflict, 18
pending, 14 outside), 34 review requests, 208 of 363 non-control candidates chained.

**Independent review:** a second model given only the 18 rewritten F3 charts and the public docs matched all 72
authored decisions. It reported no stage leakage and no boundary-close intervals. Its seroreversion concern is fixed
above. Packet, answer key, its decisions and full report: `qa/reviews/2026-09-27_v0.2.1-pre_f3/`. The final build
differs from the reviewed packet only in ten follow-up values, and the answer key is identical.

**Checks (final build):** offline `qa/test_task3.py` 15/15. This includes the new link-equality and every-link
evidence test, accession uniqueness, and stage-free charts with the matched pair; the build itself runs the rendered
identity and seroreversion checks. Task 1 offline 19/19 and adapter 14/14 are unchanged. The audit's exact failing case
scores reward 1. Docker (cloud CA copies, final build): oracle 1, no-op valid 0
(missing 34, missed 103, overclaim 93), boundary probe exit 0 with the trusted snapshot complete (6,634 records),
frozen, 0 faults.

## Expansion 0.2.0 (September 27, 2026)

The 29-patient core (unchanged cases) plus 271 generated patients: **300 patients, 1,200 candidates, 6,579 records,
107 confirmed, 101 `cannot_determine` (69 conflict, 18 pending, 14 outside), 34 review requests.** Generator:
`qa/task3_families.py` (seeded, deterministic); cohort: `qa/task3_cohort.py`. Weighted heavily toward *chained*
cases, where one fact's status must be carried into a different issue or a different patient's chart; 208 of the
359 non-control candidates are chains, each family pointing both ways (the chain changes the answer / is present
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
| F3 stage inference | no staging entry: exam text → stage → adequacy and the 24-month test (0.2.0 notes still named the stage; rewritten in 0.2.1) | 13 |
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

**Third 0.1.1 batch (mislabeled).** The results-branch folder `task3-0.2.0-pilot-opus` holds five trials whose task
files match commit `f2b8a1b` (0.1.1) exactly; the local checkout had not been updated, so they are *not* 0.2.0 runs.
All valid `end_turn`, 14–25 turns, 565–670 s, peak turn 28.4K. Raw 1/5; with the 0.1.2 evidence rule 2/5. All three
fair misses are patient 22 (hospital discharge summary vs later clinic note coded as an unresolved conflict). Across
the three 0.1.x batches, defect-adjusted: **10/15**, and every fair miss (5/15 runs) is that one authority case.

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
for review requests, checks evidence against the public rule in `tools.md` (records of the patient or of a patient
linked through a laboratory result, or clinic-level records), computed from the attested sources, and reports diagnostics by case kind × issue, error type
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
# Paid pilots (authorize first; the preflight must print all ok):
python3 qa/task3_preflight.py 0.2.1
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
