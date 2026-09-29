# Handoff: ChartR Task 1 — state as of v0.2.0 (September 26, 2026)

This file explains where the ChartR treatment-review Harbor task stands, why it looks
the way it does, and what I want from you next: **a read-only audit**. Please read it
fully before running anything.

**Update (v0.2.0):** the 0.1.4 audit in section 5 is complete. Version 0.2.0 is the first
difficulty revision: ten patients, a new follow-up category, four seeded items and
opaque record IDs. Cases and expected answers are in the private
`chartr_task1_cases_v0_2.md`; the list of three cases below describes 0.1.x.

## 1. Background

This is a work trial for ChartR, a healthcare startup. The assignment is a Harbor
evaluation task that a Claude model can pass **2–7 times out of 10**. Task 1 is a
treatment-review queue reconciliation. The agent reads synthetic syphilis-care charts
for three patients through a clinic CLI. It then creates, updates or resolves review
items according to a published policy. A private grader checks the saved queue.

- **Design source of truth:** `chartr_task1_conceptual_framework_v0_1.md` (project root).
  It holds the intended task, the three cases, the architecture, the grading rules,
  the QA cases and the failure-attribution rules. Its expected answers are private and
  must never reach the agent's environment.
- **Cases:**
  - Samantha Lee (P101/E101): expected to **create** an `open` UNRESOLVED_TREATMENT_CONCERN item.
  - Darrow Jones (P102/E102): expected to **resolve** the existing item Q102.
  - Morgan Patel (P103/E103): expected to **create** a `needs_clarification` CONFLICTING_ACTIVE_PLANS item.
- **Pilot command** (bills the Anthropic API):
  ```sh
  PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task \
    -a anthropic_agent:AnthropicAgent -m claude-opus-5 \
    --ak max_turns=100 --ak max_tokens=16000 --ak wall_timeout_sec=1770 \
    --jobs-dir "$PWD/jobs/chartr"
  ```

## 2. What changed recently, and why

The infrastructure was already in place: an isolated agent container, a clinic
sidecar, a separate verifier, controller-collected snapshots, and a custom Docker
provider with no bind mounts. It was verified in `jobs/chartr/` (see `PROGRESS.md`).
Every Opus pilot so far has scored **1**, so recent work removed places where the task
gave answers away. None of these revisions changed the expected answers or the grader
logic.

| Version | Change | Reason |
|---|---|---|
| 0.1.1 | Placeholder CLI examples; authority stated as a general `author-role` rule; removed named-case commentary | Public docs contained case-specific hints |
| 0.1.2 | Record text now carries only clinical content. Removed record-ID citations and restated status/link/cancellation history from prose (D01, D03, D04, S02, M02, M04). Removed sentences that existed only to rule out wrong answers (S05, M05, D05). Note `type` is no longer "Signed clinician note"; notes use realistic types (Progress note, Nursing note, …). `author.display` is now a fictional name instead of the role string. | Prose and labels handed over the answer, so the model never had to read the structured fields |
| 0.1.3 | Cut public docs to rules the model can't infer. `instruction.md` keeps the cohort/time, the permission to resolve existing items, "grading uses the persisted queue", and doc/tool pointers. `policy.md` keeps the TR1/TR2 table, the TR1+TR2 single-item convention, the evidence line, one-item-per-issue, and the status table. `tools.md` lost the duplicate-item warnings, the signed-note explanation, and the draft/`priorPrescription` meanings; custom cancellation extensions are listed by name only. | In the 0.1.2 pilot, Opus's reasoning matched the policy bullets one-for-one, which amounted to a per-case checklist |
| 0.1.4 | Added three routine same-episode records per patient (S06–S08, D06–D08, M06–M08: registration, vital signs, portal/admin message). They are outside the grader's allowed evidence sets, so citing one fails. `clinic records` now returns a chart in event-time order. Evidence policy line reduced to its first sentence plus "Cite only records relevant to the issue." Three QA tests added. | Before this, the allowed set was the entire chart, so "don't attach the whole chart" could not be enforced |
| 0.2.0 | Follow-up category (FU1 overdue, FU2 timing unclear) and seven new patients; four seeded items (Q102 renamed Q2146); opaque hashed record IDs; routine records now include orders, results, visits and signed notes; category/destination/reason combinations validated; budgets raised (100 turns, 4,096 tokens, 1,170 s, 50,000 tool chars). See `chartr_task1_cases_v0_2.md`. | Every 0.1.x pilot passed. More independent decisions, each with a plausible wrong answer. The 0.1.4 routine records were always X06–X08, an ID-based tell. |

**Deliberate divergences from the framework doc.** These are not defects, so do not
"fix" them back. The framework's Section 2 instruction, Section 3 policy bullets
(including "In Morgan's case, both authors have equal authority") and Section 4 record
wording are older and more hint-heavy than what now ships. The current wording lives in
`chartr_task/instruction.md`, `chartr_task/environment/public/policy.md`,
`chartr_task/environment/public/tools.md` and `qa/build_fixture.py`. The facts are
unchanged: dates, statuses, intents, regimens, links, cancellation metadata, Q102,
dispositions, and required evidence groups. Additions not in the framework: the 0.1.4
extraneous records and chronological record order.

## 3. Pilot results so far

All runs used `claude-opus-5`. Artifacts are under `jobs/chartr/<timestamp>/chartr_task__*/`.

| Run dir | Task version | Reward | Turns / time | Notes |
|---|---|---|---|---|
| `2026-09-26__15-11-22` | 0.1.0 | 1 | — | First pilot |
| `2026-09-26__17-27-01` | 0.1.1 | 1 | 9 / 57 s | Only read the docs and used `clinic`; relied on prose hints in records |
| `2026-09-26__17-50-45` | 0.1.2 | 1 | 8 / 68 s | Read the structured fields; reasoning mirrored the policy bullets |
| `2026-09-26__18-25-27` | 0.1.3 | 1 | 10 / 61 s | Reasoned from the records; all citations inside the allowed sets |
| `2026-09-26__18-33-58` | 0.1.4 | 1 | 10 / 70 s | Cited S01–S04, D01–D04, M01–M04 |
| `v0.2.0-pilot-opus` (5 trials) | 0.2.0 | 5/5 | 11–25 / 115–154 s | Every decision right in every run, with no visible hesitation; tabulated charts with a script; two runs self-corrected an evidence-format 400 |
| `v0.3.0-pilot-opus` (5 trials) | 0.3.0 | 1/5 raw; 5/5 after defect regrade | 19–26 / 193–245 s | Every failure was P117/follow_up, a case-design defect (see PROGRESS.md); nothing else missed |
| `v0.3.1-pilot-opus` (5 trials) | 0.3.1 | 4/5 | 22–36 / 216–253 s | One run treated P117's later single-dose plan as silently superseding the active weekly order |
| `v0.3.1-pilot-opus-b` (5 trials) | 0.3.1 | 4/5 | 12–29 / 95–234 s | Failure was a 4,096-token cap hit inside a thinking block (budget, not reasoning); fixed in 0.3.2 |
| `v0.3.2-pilot-opus` (5 trials) | 0.3.2 | 4/5 | 23–27 / 230–251 s | Same P117 miss: later plan read as superseding |
| `v0.4.0-pilot-opus` (5 trials) | 0.4.0 | 5/5 | 19–29 / 215–250 s | All supersession-boundary cases right; runs cite the tightened "explicit" rule |
| `v0.5.0-pilot-opus` (5 trials) | 0.5.0 | invalid (5) | 17–24 / 260–287 s | All `APIConnectionError` in the same ~25 s window; host network/API blip; rerun as 0.5.1 |
| `v0.5.1-pilot-opus` (5 trials) | 0.5.1 | 5/5 | 17–32 / 482–558 s | Event histories solved; two runs survived connection drops via retries; Opus noticed twin cases as "deliberate contrast" |
| `proto-0.1.0-pilot-opus` (5 trials) | proto 0.1.0 (`chartr_proto/`) | 5/5 | 17–24 / 163–217 s | Inferred all 16 hidden standards from 31 past determinations; all 24 fields right |

No run has shown the agent probing outside its boundary. The runs only ran `ls /app`
and `clinic --help`, both public.

Useful files in each run: `controller/anthropic/events.jsonl` (full trajectory),
`controller/anthropic/termination.json`, `controller/attestation.json` and
`controller/run-manifest.json` (version and file hashes), `verifier/diagnostics.json`
(per-check results), and `artifacts/evidence/snapshot.json`.

## 4. Where things are

| Path | What it is | Agent-visible? |
|---|---|---|
| `chartr_task1_conceptual_framework_v0_1.md` | Design spec, including private expected answers | No |
| `PROGRESS.md` | Implementation log, revision notes, verification history | No |
| `chartr_task/README.md` | Architecture, commands, artifact locations, revision notes 0.1.1–0.1.4 | No |
| `chartr_task/task.toml` | Harbor task config (version, timeouts, separate verifier, collect hook, artifacts) | No |
| `chartr_task/instruction.md` | Agent prompt | Yes |
| `chartr_task/environment/public/{policy.md,tools.md,clinic.py}` | Public docs and the CLI (copied into the agent image) | Yes |
| `chartr_task/environment/Dockerfile`, `.dockerignore`, `docker-compose.yaml` | Agent image (allow-listed build context) and sidecar/network wiring | No |
| `chartr_task/environment/service/` | Clinic service: `server.py` (HTTP), `store.py` (SQLite, validation, audit, collect/freeze), `fhir.py` (R4 helpers, VERSION, schema checksum), `control.py` (controller-only attest/collect), `fixture.json` (generated), `schema/` | Only through the API |
| `chartr_task/tests/` | Private verifier: `grade.py` (EXPECTED evidence groups), `baseline.json` (initial digest, Q102), `test.sh`, Dockerfile | No |
| `chartr_task/solution/` | Deterministic reference (`reference.py`, `solve.sh`), oracle runs only | No |
| `qa/build_fixture.py` | **Canonical fixture generator.** It regenerates `fixture.json` and `tests/baseline.json`. Edit it, never the JSON. | No |
| `qa/test_clinic.py`, `qa/test_adapter.py` | Offline tests (`./.venv/bin/python -m unittest discover -s qa -p 'test_*.py' -v`) | No |
| `qa/agents.py`, `qa/transfer_smoke.py`, `qa/summarize.py` | QA agents, the sidecar-transfer smoke test, and the run-summary builder | No |
| `anthropic_agent.py` | Direct Messages-API agent loop (limits, logging, redaction, termination reasons) | No (controller side) |
| `chartr_environment.py`, `chartr_job.yaml` | Custom Docker provider: removes host mounts, attests start state, enforces stop-before-collect, trusted snapshot read | No |
| `jobs/chartr/` | All saved runs and QA evidence (gitignored) | No |
| `habor_tutorial/` | Original Harbor tutorial task; leave it alone | — |

## 5. What I want from you: a read-only audit

**Ground rules**
- **Do not change any files.** That includes the task, fixture, docs, grader, reference,
  tests, harness and provider. If you find something that needs fixing, report it.
- **Do not run anything that calls the Anthropic API** (any `harbor run` with
  `anthropic_agent`) without asking me first. Those runs cost money.
- You may run the offline tests, and no-cost Harbor runs such as the oracle and
  no-op/QA agents, to verify behavior. Write them to a clearly named new directory
  under `jobs/chartr/` (e.g. `audit-0.1.4-<timestamp>/`), never over existing runs.
- Do not upgrade `.venv` or any pinned dependency (Harbor 0.23.0, anthropic 1.8.0,
  jsonschema 4.26.0).
- Start with `git status` so you know which changes are uncommitted.
- **Do not suggest changes to task difficulty yet.** I will work on difficulty next,
  separately. If a finding touches difficulty, report it as an observation only.

**Scope.** Check that the current Harbor task and harness behave as
`chartr_task1_conceptual_framework_v0_1.md` specifies, apart from the deliberate
divergences in section 2. Cover at least:

1. **Task boundary and completion (§1, §2):** the agent must change saved state for the
   task to count; a chat answer alone must not count.
2. **State and data contract (§5):** entity fields; text and metadata agree; Q102
   identity and creation metadata are preserved; new IDs are service-generated; audit
   history is kept.
3. **Tool contract (§6):** CLI operations and errors match `tools.md`; validation
   (enums, patient/episode/evidence ownership); duplicates allowed by the API; no
   reset/admin/export/delete routes; lost-write behavior; complete, deterministic reads.
4. **Runtime and access boundaries (§7, §13):**
   - The agent image contains only the public files.
   - No private files end up in any image layer, including the service image.
   - Network isolation between agent and service is as intended. `task.toml` sets
     `network_mode = "public"` while the compose network is `internal`, so check what
     the agent container can actually reach.
   - No bind mounts, and no Docker socket.
5. **Lifecycle, reset and evidence capture (§8):**
   - Each trial gets a fresh DB.
   - The start digest is attested against `tests/baseline.json`.
   - The agent is stopped before collection.
   - The snapshot is frozen and collected only through the controller.
   - The separate verifier receives evidence explicitly.
   - Invalid runs are not turned into a reward of 0.
6. **Expected results and evidence acceptance (§9):**
   - `grade.py` EXPECTED matches the intended dispositions.
   - The required/allowed evidence groups are sound now that the 0.1.4 extraneous
     records exist.
   - Evidence is treated as a set.
7. **Scoring and diagnostics (§10):** binary pass plus per-check diagnostics; the
   global invariants; the limits on grading explanations.
8. **Reference and QA matrix (§11):** each QA case in the framework table has a
   corresponding test or run artifact. List the ones that are missing or stale after
   0.1.2–0.1.4.
9. **Failure attribution and saved results (§12):** validity classification,
   termination reasons, and what each attempt saves. Confirm credentials never appear
   in logs or artifacts.
10. **Version and record-keeping consistency:**
    - `task.toml`, `fhir.py` VERSION, `fixture.json`, `baseline.json`, the README and
      `PROGRESS.md` all agree on 0.1.4.
    - Regenerating with `qa/build_fixture.py` reproduces the committed fixture and
      baseline exactly.

**Deliverable.** Save a report as `AUDIT_0.1.4.md` in the project root (this new file
is the only thing you may create outside `jobs/`). Include:
- **Conformance table:** each framework section, rated *Conforms* / *Intentional
  divergence* / *Gap*, with file:line or run-artifact evidence.
- **Weak spots and areas for improvement,** ranked by severity (evaluation validity
  first, then trust boundary, grading fairness, reproducibility, maintainability). For
  each: what you observed, why it matters, and how you confirmed it (tested vs.
  inferred from reading).
- **What you ran:** commands, output locations, results.
- **Open questions** for me, where the framework is ambiguous or intent is unclear.

Keep difficulty recommendations out of the report.
