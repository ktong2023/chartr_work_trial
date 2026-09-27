# ChartR review-queue task — v0.2.0

One Harbor task contains ten synthetic patients (P101–P110) and two review categories:
treatment review and follow-up.
The original `task_1` tutorial is unchanged. The existing `-a anthropic_agent` import
continues to work. Development uses the existing `.venv`: Harbor **0.23.0**, Anthropic
SDK **1.8.0**, jsonschema **4.26.0**. No installed dependency was upgraded.

## Revision 0.2.0 — follow-up category, ten patients, anti-shortcut fixture

Difficulty revision. Adds a `follow_up` category (destination `follow_up_coordination`;
reasons `OVERDUE_FOLLOW_UP` → `open`, `FOLLOW_UP_TIMING_UNCLEAR` → `needs_clarification`)
next to the unchanged treatment rules, and seven new patients (P104–P110). The starting
queue grows from one item to four: Q102 is now Q2146, plus Q2081, Q2203 and Q2217.
Expected final state: 9 items, graded per (patient, category); every other pair must be
empty. Each new case isolates one reasoning skill with one plausible wrong answer: date
arithmetic from a named anchor, booked-after-due, unrelated recent visit, completion after
the due date, staff removal or patient self-report, unreconciled plans, and a clinician
replacement that follows re-treatment. The private case sheet is
`../chartr_task1_cases_v0_2.md`.

Anti-shortcut changes: every record ID is an opaque hash (no chronology, patient, type or
relevance signal; this removes the 0.1.4 tell where routine records were always X06–X08),
and routine content now includes orders, results, visits and signed clinician notes.
`qa/test_clinic.py` enforces that ID order never separates citable from routine records
and that every type, role, label and author on a citable record also appears on a
routine one. New record types: ServiceRequest plans (`intent: plan`, optional `due-by`),
MedicationAdministration, Observation and Encounter. S04 gains `authoredOn`; orders gain
`requester`. The service rejects mismatched category/destination/reason combinations.

Budgets raised so the larger cohort cannot fail on limits: 100 turns, 4,096 output
tokens, 1,170 s adapter wall time (Harbor agent timeout 1,200 s), 50,000 tool-output
characters. Every chart stays under 20,000 characters (generator and test check).
QA: 18 clinic tests, including a failing variant for every tempting wrong answer
(each confirmed to fail on its intended check), plus 11 adapter tests. Offline
reference = 1 in both evidence variants; no-op = 0.

## Revision 0.1.4 — extraneous records; evidence relevance now enforceable

Each episode gains three routine same-episode records with no bearing on any
treatment-review concern (S06–S08, D06–D08, M06–M08: registration, vital signs,
portal/administrative messages), written with the same note shape, roles and authors as
case records. They are outside the grader's allowed evidence sets, so citing any of them
now fails the evidence check (previously the allowed set was the whole chart). The
records endpoint returns a chart in event-time order so routine entries interleave with
case records. Policy evidence line reduced to its first sentence plus "Cite only records
relevant to the issue." Grader logic, expected dispositions and required evidence groups
unchanged. New QA: extraneous citation fails; all-relevant citation passes; whole-chart
citation fails; records are chronological. 17 clinic tests pass; oracle (both variants)
= 1; no-op = 0.

## Revision 0.1.3 — public documentation reduced to rules the model cannot infer

`instruction.md` keeps only the cohort/evaluation time, the authority to resolve
existing items, the persisted-queue completion rule and doc/tool pointers.
`policy.md` keeps the TR1/TR2 table, the TR1+TR2 single-item convention, the
evidence guidance (under review: its "entire chart" clause is not enforced by the
current fixture), one-item-per-issue and the status table; the other policy-detail
bullets and the reopening note were removed. `tools.md` dropped duplicate-item
warnings, the signed-note explanation, and FHIR order/draft semantics (custom
cancellation extensions are listed only). Fixture content, grader and expected state
unchanged; fixture/baseline regenerated for the version string. Offline tests pass;
oracle (both variants) = 1, no-op = 0.

## Revision 0.1.2 — agent-visible content leak cleanup

Record text now carries only clinical content. Removed record-ID citations and
restated status/link/cancellation history from order and note prose (D01, D03, D04,
S02, M02, M04), and removed sentences written only to rule out wrong answers (S05,
M05, D05). DocumentReference `type` no longer says "Signed clinician note"; note
types are realistic (Progress/Nursing note, Telephone encounter, Scheduling note)
and `author.display` holds fictional names instead of role strings, so signature and
authority must be read from `docStatus`, `authenticator` and `author-role`.
`instruction.md` dropped its per-case warnings; `tools.md` dropped repeated policy
reasoning; `policy.md` dropped the "at most one issue per episode" statement.
Structured facts (statuses, intents, dates, links, cancellation extensions, regimens),
Q102, dispositions and accepted evidence sets are unchanged; the grader is unchanged.
Fixture and private baseline regenerated; offline tests, oracle (both evidence
variants) = 1 and no-op = 0. 0.1.1 run artifacts remain historical evidence.

## Revision 0.1.1 — public hint cleanup

CLI examples now use labeled placeholders. Public documentation explains clinician
authority through `author-role` metadata and contains no named-case commentary or
statements about which transitions the starting fixture requires. Both signed
Morgan assessments retain distinct author identities and share the same
`treating-clinician` role. Editorial sentences announcing absent replacement links
or commenting on order history were removed from the canonical fixture generator;
the fixtures and private integrity digests were regenerated after a fact comparison.
Clinical dates, status fields, regimens, genuine replacement links, the initial
queue, intended dispositions, and the grader's evidence alternatives are unchanged.
This is a documentation/fixture revision, not a new difficulty case or architecture.
Existing run artifacts, including the earlier successful pilot, remain historical
evidence for 0.1.0 and must not be overwritten or relabeled as 0.1.1 results.

## Run from the project root

Docker Desktop must be running. Always include `-c chartr_job.yaml` for ChartR:
stock Harbor Docker adds writable host log mounts, contrary to this task's boundary.
Use an absolute jobs directory to avoid this Harbor version's relative Docker-copy
path issue. No credentials are needed for oracle or no-op runs.

```sh
# Deterministic reference on fresh state
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task -a oracle --jobs-dir "$PWD/jobs/chartr"

# Fresh initial state must score zero
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task -a nop --jobs-dir "$PWD/jobs/chartr"

# ONE paid pilot, only when you decide to run it; not executed during implementation.
# ANTHROPIC_API_KEY must already be exported on the host. Do not use --agent-env for it.
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task -a anthropic_agent:AnthropicAgent -m claude-opus-5 --ak max_turns=100 --ak max_tokens=4096 --ak wall_timeout_sec=1170 --jobs-dir "$PWD/jobs/chartr"
```

The model default preserves the original `claude-opus-5` value. `-m` overrides it;
otherwise `ANTHROPIC_MODEL` overrides the default. `--ak max_turns`, `max_tokens`,
`wall_timeout_sec`, `api_timeout_sec`, `tool_timeout_sec`, `max_tool_chars` configure
limits. `ANTHROPIC_MAX_TURNS` and `ANTHROPIC_MAX_TOKENS` are optional host fallbacks.
Harbor allows 1,200 seconds for the agent, 600 for builds, and 120 for verification.
The adapter uses the ordinary Messages API and no new organization-dependent API
features. Earlier pilot artifacts are retained under their own version labels.

## Architecture and trust boundary

* **Agent container:** Python shell, `clinic` CLI, public policy and tool docs only.
  Its build context is explicitly filtered; no tests, solutions, fixture database,
  repository history, or complete conceptual framework ever enter its image layers.
* **Clinic service:** Python standard-library HTTP server, SQLite persistence, public
  fixtures, pinned R4 schema, operational validation and append-only API audit. The
  service is read-only except per-trial tmpfs state/evidence. No host ports or shared
  volumes. The agent and service use an internal Docker network; the verifier has
  no network. The host performs model requests.
* **Controller:** `chartr_environment.py` removes Harbor's host bind mounts, checks
  actual container mounts, binds a fresh service nonce to the trial UUID, and checks
  the starting digest against a private baseline before agent execution. It stops
  the main container (including children), confirms it is stopped, then invokes the
  service-only collector over Docker exec. A SQLite transaction freezes further
  operations and exports a consistent snapshot/audit. In-flight transactions settle
  before collection. The API exposes no collector, reset, database, or admin route.
* **Private verifier:** Harbor creates it after stopping the evaluated environment.
  The snapshot is copied from the service and the start attestation from the host.
  The independent grader checks trial/fixture identity, frozen state, service faults,
  audit continuity, unchanged sources, Q102 identity/creation, item counts,
  dispositions and evidence groups. A valid incorrect queue gets 0; missing or
  invalid evidence/service/API faults produce diagnostics and **no reward file**.

Harbor 0.23.0 natively supports `[[verifier.collect]]`, sidecar `artifacts.service`,
main-stop-before-sidecars, and `environment_mode = "separate"`. The small custom
provider is still necessary: default log mounts violate the boundary, recovery
collection needs explicit stop ordering, and Docker Desktop 29.8.0's `docker cp`
could not read the service tmpfs snapshot. The provider reads that exact JSON file
through sidecar exec instead. It never accepts an agent-written snapshot.

The minimal unrelated transfer proof is `qa/transfer_smoke.py`: service counter 7
passes while an agent-created counter 999 at the same path is ignored. The real
clinical boundary probe also plants a forgery in both the agent's `/evidence` and
its published artifacts directory; neither shadows the trusted service evidence.

Every new trial gets an empty SQLite database, the four seeded items, fresh nonce, ID counter and
audit. Reusing an existing database is rejected. Reset means tearing down the
per-trial containers and launching a new trial, never calling an agent admin API.

## FHIR representation

See [public tools and mapping](environment/public/tools.md) for exact commands,
return shapes, local extensions, episode/evidence links, timestamps and status
mapping. Patient, EpisodeOfCare, DocumentReference, MedicationRequest,
MedicationAdministration, ServiceRequest, Observation, Encounter, Organization and Task
resources are stored as JSON. This is a
limited representation, **not full FHIR REST/API conformance**. The official R4
4.0.1 JSON schema is vendored and checksum checked; see
[schema provenance](environment/service/schema/README.md).

S04 is an outstanding request, with no fabricated result. D01 retains its August
31 authorship and September 1 cancellation; D04 explicitly replaces it. D04 stays
an active recorded order because D05 reports patient completion without documenting
an order-status closure. Both Morgan orders retain active status and their distinct
supporting notes. Follow-up plans are ServiceRequest `intent: plan`; a revoked plan
carries `cancelled-at`/`cancelled-by`/`replaced-by` like D01.

Custom `open`/`needs_clarification`/`resolved` codes live in Task.businessStatus;
Task.status uses R4 `requested`/`requested`/`completed`. The source fixture has 138
resources including the four seeded items. New/updated tasks are schema validated before commit.
FHIR schema validation is structural; it is not complete terminology, profile,
reference-resolution or FHIRPath conformance validation.

## Reference and grading

`solution/reference.py` reads and writes only through the same `clinic` CLI. Harbor
uploads it for dedicated oracle runs only. `tests/grade.py` imports neither the
reference nor the backend. `EXPECTED` is keyed by (patient, category) with role-based
required groups and allowed sets (see the private case sheet); relevant additional
references and different action ordering are allowed. Explanation text must be nonempty, but its factual prose requires
human QA. The backend intentionally permits duplicate and semantically incorrect
items; the grader detects them. Seeded items cannot be reassigned, deleted or replaced.

## Evidence and attribution

Each Harbor trial saves:

* `controller/attestation.json`: trusted initial digest, nonce and trial identity.
* `controller/run-manifest.json`: task file hashes, provider hash, runtime versions
  and container image names; Dockerfiles pin their common base image digest.
* `controller/anthropic/events.jsonl` and `termination.json`: durable observable
  messages, tool calls/full results, usage, limits and termination (model runs).
  This sibling directory is never mirrored into or mounted by the agent. Known
  host secrets and Anthropic key patterns are redacted; headers/credential values
  and provider exception bodies are never recorded.
* `artifacts/evidence/snapshot.json`: authoritative frozen FHIR sources, queue,
  service metadata and complete API audit with before/after queue states.
* `verifier/diagnostics.json`, `verifier/reward.txt`, `result.json`, and `config.json`:
  checks, reward when valid, timings and Harbor configuration.

`max_tokens`, turn exhaustion and adapter time/tool limits save the current state
and remain valid budget-limited attempts. API errors are invalid. Cancellation is
explicitly recorded as interrupted; recovery stops the agent and preserves evidence.
Harbor's outer timeout/cancellation may have no valid grade and should not be counted
as a clean model failure. The adapter's shorter wall budget normally avoids this.
No automatic API or transport write retry is performed. Inspect queue after an
ambiguous write failure. Retain failed attempts; don't silently include exceptions
as score zero or discard valid unsuccessful runs.

```sh
# No external model calls; clinic tests use an ephemeral loopback HTTP listener.
./.venv/bin/python -m unittest discover -s qa -p 'test_*.py' -v
./.venv/bin/python qa/transfer_smoke.py
./.venv/bin/python qa/summarize.py jobs/chartr

# Runtime privacy and invalid-attempt checks (mocked / no model charges)
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task -a qa.agents:BoundaryProbe --jobs-dir "$PWD/jobs/chartr"
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task -a qa.agents:MockAPIError --jobs-dir "$PWD/jobs/chartr"
PYTHONPATH="$PWD" ./.venv/bin/harbor run -c chartr_job.yaml -p chartr_task -a qa.agents:MockBudget --ak max_turns=1 --jobs-dir "$PWD/jobs/chartr"
```

Full development results stay under ignored `jobs/chartr/`; see
`verification-summary.json` and `offline-tests.log` there. No benchmark pass rate or
real-model performance is claimed. Once a paid pilot is authorized and reviewed,
freeze a version before running the eventual ten-trial batch.

## Files and dependencies

`environment/public/`: agent-visible CLI/policy/docs. `environment/service/`: public
fixtures, schema, persistence/API and controller-only collection code.
`solution/`: private oracle. `tests/`: private baseline/grader/verifier image.
`qa/`: private focused acceptance tests and no-credit Harbor probes.
`chartr_environment.py`, `chartr_job.yaml`: trusted Harbor integration.
`anthropic_agent.py`: direct async adapter. `PROGRESS.md`: resume notes.

Host pins are in `requirements.txt`; container validation dependencies are pinned in
`environment/service/requirements.txt`. Images use Python 3.13.7 slim Bookworm at a
fixed digest. Docker builds install dependencies; grading never downloads packages.
Use the existing `.venv`. The vendored schema makes validation independent of HL7
availability. `qa/build_fixture.py` is a designer-only regeneration helper that also
updates the private integrity baseline; rerun it only when intentionally revising
and reviewing fixture facts, not during trials.
