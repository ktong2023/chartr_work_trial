# Task 3: cohort audit with calibrated abstention (`chartr/cohort-audit` v0.3.1)

**Final result: 5/10** Claude Opus 5 attempts pass, inside the 2–7/10 target. This is the one confirmation batch, run under
the predeclared protocol below. The full triage is in
[`results/confirm-task3-0.3.1-20260928T232731Z/TRIAGE.md`](../results/confirm-task3-0.3.1-20260928T232731Z/TRIAGE.md).

## Overview

The agent audits the syphilis care of a 200-patient synthetic clinic cohort as of September 24, 2026, 12:00 UTC. Clinical
questions are judged by the CDC Sexually Transmitted Infections Treatment Guidelines, 2021.

**The candidates.**
- Every episode × issue pair is a *candidate*, for 800 candidates in all.
- There are four issue types:
  - `INADEQUATE_TREATMENT`
  - `FOLLOW_UP_OVERDUE`
  - `MISFILED_RESULT`
  - `PREGNANCY_TREATMENT_INADEQUATE`
- Each candidate gets one disposition: `confirmed`, `not_an_issue`, or `cannot_determine`.
- A `cannot_determine` must name what is missing: `RESULT_PENDING`, `OUTSIDE_RECORD_NOT_RECEIVED`, or
  `UNRESOLVED_SOURCE_CONFLICT`.
- The agent also answers 34 explicit review requests.

**What makes it hard.**
- **Calibrated abstention.** The agent must say "can't determine" exactly when a decisive fact is genuinely unestablished,
  and must still answer definitely when a gap doesn't change the answer.
- **Chained reasoning.** 139 of the 259 non-control candidates are *chains*: a fact settled in one place must be carried into
  a different issue or into a different patient's chart. Examples:
  - a specimen whose identity conflicts between its collection label and the laboratory's accessioning entry leaves
    *follow-up* unresolved, not just the misfiling question;
  - a pregnancy test misfiled to another patient makes *her* doxycycline treatment inadequate;
  - a nurse's signed dose-date correction moves the follow-up window.
- **No hints.** The public documents give only the goal, the interface, the output vocabulary and local conventions. There
  are no treatment tables, schedules or staging rules; those come from the CDC guidelines.

**Scoring** is zero-tolerance.
- A run passes only if all 800 dispositions and missing-evidence codes are right, every review request has an explicit item,
  and every cited record is admissible.
- Explanation prose is not graded.

## Environment

**Containers.** Each trial runs two containers on an internal Docker network with no internet access:
- **`main`:** the agent's container. All Linux capabilities are dropped. It holds the `clinic` command-line tool and the
  public docs at `/app/` (`policy.md`, `tools.md`).
- **`clinic`:** a read-only FHIR-like record service that answers HTTP requests from the CLI. Records are immutable; the
  agent can only add and update its own review items.

**The cohort.**
- 200 synthetic patients and 4,482 limited FHIR R4 records (pinned R4 4.0.1 structural schema).
- Record types include patients, episodes, diagnoses, lab results with collection records, the laboratory's accessioning
  entries, medication administrations and dispenses, notes and scanned outside records, and review requests.
- The cohort is a 29-patient hand-authored core plus generated case families: identity conflicts, resolved misfiles,
  pending pregnancy tests, pregnancy-test identity, dose-date corrections, outside first doses, deliveries, and stage
  inference.

**Grading.** After the run, a separate verifier container collects a controller-attested snapshot of the saved items. A
private, deterministic grader (`tests/grade.py`) compares it with the answer key. The key is checked against an
independently written rules engine (`qa/task3_rules.py`), which evaluates every possible value of each patient's one
unknown fact.

## Tools given to the model

**Interfaces.** The agent gets a shell in the `main` container (the adapter's single `bash` tool), so it may write
scripts. Everything else goes through the `clinic` CLI:

| Command | What it does |
|---|---|
| `clinic patients` | Every cohort patient with their episodes |
| `clinic records PATIENT_ID` | Every record whose subject is that patient, in event-time order |
| `clinic export [--dir DIR]` | Every record in the clinic, including records with no patient subject (such as accessioning entries), as NDJSON per resource type plus a manifest |
| `clinic requests` | Open review requests |
| `clinic items [--patient ID]` | Saved items |
| `clinic item --json {...}` | Save one item: `patient`, `episode`, `issue`, `disposition`, `missing_evidence`, `evidence` (1–30 record IDs), `explanation` |
| `clinic update-item ITEM_ID --json {...}` | Update a saved item |

**Prompt and documents.** The instruction is 80 words ([`instruction.md`](instruction.md)): audit every patient for the policy's issue
types, answer every review request, and save the decisions as items.
- [`environment/public/policy.md`](environment/public/policy.md) defines the dispositions, the issue types and five local
  conventions:
  - follow-up windows;
  - specimen identity;
  - signed corrections;
  - outside-facility records;
  - unresolved conflicts.
- [`environment/public/tools.md`](environment/public/tools.md) defines the interface and the record types.

## Final confirmation batch: 10 trials

**Batch.** It ran on September 28, 2026, with frozen commit `19edc3b`, model `claude-opus-5` and adapter 0.4.0. The budgets
were 250 turns and 64K output tokens per response, with prompt caching on.
- All 10 attempts were valid, with no reruns, no budget failures and no API retries.
- Each run took 20–30 min and 40–63 turns.

| Trial | Result | What it got wrong |
|---|---|---|
| Xw6Xdrd | fail | Marked three follow-ups (g017, g019, g021) `confirmed` overdue. In each, a specimen in *another* chart has conflicting identities, one naming this patient, inside the window, so follow-up is `cannot_determine` / `UNRESOLVED_SOURCE_CONFLICT` |
| 2LCiX4L | fail | Correctly flagged misfiled 24-month RPRs for g024 and g040, but did not carry that into the dependent `FOLLOW_UP_OVERDUE`: with the misfiled result removed, both patients' 24-month tests are missing |
| reSK6L9 | **pass** | — |
| uBiC29g | **pass** | — |
| bdK7sjH | fail | The same two missed dependent follow-ups as 2LCiX4L (g024, g040) |
| xMreuhf | fail | The same three cross-chart follow-up overclaims as Xw6Xdrd (g017, g019, g021) |
| 6XqsLvn | **pass** | — |
| TSGnJbn | **pass** | — |
| SXq9ZER | fail | Five wrong candidates:<br>• missed a definite misfiled result (g030);<br>• missed three abstentions on g062, where a pregnancy test with conflicting identities bears on treatment adequacy;<br>• missed g103's pregnancy-treatment issue, preferring a later clinic note over the received hospital delivery record.<br>Also cited one inadmissible record |
| Ng8WpkK | **pass** | — |

**Pattern.**
- All failures are model errors under the unchanged public rules; there are no task or grader defects.
- Every failure is a broken chain: an identity or authority fact that the run itself recognized, or could have, but did
  not carry into the dependent decision.
- Across all 10 runs, 15 of 8,000 candidate decisions were wrong (99.8% candidate accuracy). The zero-tolerance task score
  is 5/10.

## Version history

| Version | Date | Change | Opus 5 result |
|---|---|---|---|
| 0.1.0 | Sep 27 | 29-patient hand-authored core, 116 candidates | Pilot 0/5 raw. Two defects: the evidence rule rejected a valid citation, and follow-up wording was ambiguous. Defect-adjusted 4/5 |
| 0.1.1, 0.1.2 | Sep 27 | Fixed the wording and the evidence rule | Pilot 2/5 raw, defect-adjusted 4/5. The only fair miss was the outside-facility authority rule. Too easy |
| 0.2.0 | Sep 27 | Scaled to 300 patients with generated chain-weighted case families | Pilot 0/5. Exposed accession-number collisions and an over-strict cross-chart evidence rule |
| 0.2.1, 0.2.2 | Sep 27 | Fixes from an independent audit: unique accessions, rebuilding identity from the rendered records, cross-chart evidence, a precedence rule between missing-evidence codes | Defect-adjusted 0/5 (about 10%). Too hard |
| 0.3.0 | Sep 28 | Calibration: 200 patients (fewer duplicate instances), removed the hardest window-edge case, tightened realism from three independent reviews, adapter 0.4.0 with opt-in prompt caching | Pilot 4/10 |
| **0.3.1** | Sep 28 | Policy wording only: `FOLLOW_UP_OVERDUE` names the CDC as the source, and an unrejected pending specimen counts as collected. No answer changes | Pilot 4/10, then **confirmation 5/10** |

The full build log is in
[`docs/history/chartr_task3_build_log.md`](../docs/history/chartr_task3_build_log.md). It covers:
- every pilot's per-run triage;
- the case-family tables;
- the independent model reviews ([`qa/reviews/`](../qa/reviews/README.md));
- the audit responses ([`docs/audits/`](../docs/audits/)).

## Limits

- **Grading.** The grader checks decisions and citation admissibility, not whether the explanation justifies the decision.
- **Answer key.** The answers are authored. The rules engine that cross-checks them is independent code, but it reads
  authored case facts, not the rendered records.
- **Independent review.** It covered samples (59, 21 and 60 patients), not all 800 candidates. Instances within one case
  family are correlated.
- **Clinical realism.** The patients are synthetic. Judgments rely on the CDC 2021 guidance, and cases where the guidance
  hedges were excluded.

## Licensing and citations

- **Data.** Every patient and record is synthetic, generated by `qa/build_task3.py`, and contains no real patient data.
- **Clinical standard.** Workowski KA, Bachmann LH, Chan PA, et al. *Sexually Transmitted Infections Treatment
  Guidelines, 2021.* MMWR Recomm Rep 2021;70(No. RR-4):1–187. doi:10.15585/mmwr.rr7004a1. This is a US government
  publication in the public domain.
- **Record format.** HL7 FHIR R4 (4.0.1); the FHIR specification is published under CC0. The structural JSON schema is
  pinned in `environment/service/schema/`.
- **Harness.** Harbor 0.23.0 runs the task; the agent uses the Anthropic API (`anthropic` 1.8.0) through
  `anthropic_agent.py`.

## Final confirmation protocol (fixed September 28, 2026, before any confirmation trial)

*Kept word for word as fixed before the batch. Paths and file names in it are as they stood then; `PROGRESS.md` is now in [`docs/history/`](../docs/history/PROGRESS.md).*

This batch confirms the pre-final release. It is a new batch: the v0.3.1 pilot below (4/10) stays a pilot result and is not
pooled with it. Nothing in this section changes once the batch has started. Running it makes paid model calls and needs the
user's authorization.

**Frozen configuration**

| | |
|---|---|
| Frozen commit | `19edc3b` on `main`. The checkout may be a later `main` commit only if no evaluated file differs from `19edc3b` (step 2); only READMEs, `PROGRESS.md` and reports may change. Task 3's evaluated files are identical to the v0.3.1 pilot's |
| Task | `chartr/cohort-audit` **0.3.1** (`task.toml`, fixture and baseline `chartr-cohort-audit-0.3.1`) |
| Answer key | `tests/expected.json` sha256 `ffdd6f592cefe259e5886a829e3b9d3918a578f382a041c5a852369610f97517` |
| Fixture | initial digest `4bda15848c03019ce75bf4c239d8724aaf3041e81fd67aeaf5eee177f5df3ab8`, attested by the provider at every trial start |
| Harness | adapter 0.4.0 (`anthropic_agent.py` sha256 `95ce935a…3ead`), provider `chartr_environment.py`, Harbor 0.23.0, anthropic 1.8.0; host environment from `requirements.lock.txt` |
| Model and budgets | `claude-opus-5`; `-k 10 -n 10`; `max_turns=250`, `max_tokens=64000`, `api_timeout_sec=1800`, `wall_timeout_sec=7000`, `prompt_cache=true`, and the default `tool_timeout_sec=60`. These are exactly the v0.3.1 pilot's |
| Host | Docker; no other ChartR trial running (Task 3 and Task 4 batches never overlap); `caffeinate` so the host cannot sleep |

**Exact commands** (bash, from the repository root)

1. Update the checkout: `git fetch origin && git checkout main && git pull --ff-only`
2. Frozen files unchanged (must print `frozen-files-ok`):
   ```bash
   git diff --quiet 19edc3b HEAD -- chartr_task3 ':(exclude)chartr_task3/README.md' anthropic_agent.py chartr_environment.py chartr_job.yaml requirements.lock.txt && echo frozen-files-ok
   ```
3. Preflight (every line must be `ok`): `python3 qa/task3_preflight.py 0.3.1`
4. No other ChartR trial running (must print `idle`): `docker ps --format '{{.Names}}' | grep -q '^chartr_' || echo idle`
5. Create the batch's unique output directory. It is never reused; the command refuses an existing path and records the
   dispatch state:
   ```bash
   D="$PWD/jobs/chartr/confirm-task3-0.3.1-$(date -u +%Y%m%dT%H%M%SZ)"; test ! -e "$D" && mkdir -p "$D" && { git rev-parse HEAD; python3 qa/task3_preflight.py 0.3.1; } > "$D/DISPATCH.txt" && echo "$D"
   ```
6. Run the batch (job name `batch`):
   ```bash
   caffeinate -dims env PYTHONPATH="$PWD" .venv/bin/harbor run -c chartr_job.yaml -p chartr_task3 -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 10 -n 10 --ak max_turns=250 --ak max_tokens=64000 --ak api_timeout_sec=1800 --ak wall_timeout_sec=7000 --ak prompt_cache=true --env-file .env --job-name batch --jobs-dir "$D"
   ```
7. Score: `python3 qa/confirm_summary.py chartr_task3 "$D"`. If it reports `INCOMPLETE`, rerun the same command with
   `-k N -n N`, where N is the number of missing valid attempts. Use the next unused job name (`rerun-1`, `rerun-2`, …) in the
   same `$D`, then score again.
8. Write `$D/TRIAGE.md`, then commit `$D` to the `task3-pilot-results` branch.

**Counting rules** (applied by `qa/confirm_summary.py`; the same rules as the v0.3.1 pilot, made mechanical)

- **Headline:** passes among the first 10 valid attempts, in start order. The 2–7 of 10 target is judged on this number alone.
  It is reported whatever it is, and no further batch is run to reach the target.
- **Invalid attempts** get no reward and are not attempts: API or adapter errors, cancellation, service faults, and evidence or
  integrity failures. Report them and rerun under the same command (step 7) until there are 10 valid attempts.
  - If one job has 3 or more invalid attempts, stop and fix the infrastructure without touching frozen files.
  - If a frozen file must change, the batch is void.
- **Budget failures:** valid attempts that end on output truncation, turn, wall or tool timeout, or context exhaustion count as
  failures in the headline. They are also listed as a separate category. The 64K output cap is part of the frozen
  configuration; the single-command submission pattern seen in 2 of 20 earlier runs is counted, not excused.
- **Provenance:** every trial's manifest must match the frozen task files (README excepted), provider, adapter, model and
  budgets. One mismatch voids the batch; the script exits 1.
- **Triage:** classify each failure from its saved items and trace as a model failure, a task/grader defect, or a budget
  failure.
  - A defect is fixed in a new version and reported separately.
  - This batch is never re-scored.

