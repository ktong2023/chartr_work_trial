# ChartR agent tasks

This repository builds, validates and benchmarks **two long-horizon clinical-review tasks for evaluating AI agents**, packaged
for the [Harbor](https://github.com/laude-institute/harbor) evaluation framework.

**What the agent does.**
- It works inside a sandboxed clinic record system through a command-line tool.
- It reads every patient's chart, applies a written clinic policy and current clinical guidelines, and saves structured
  decisions.

**How it is scored.** A private, deterministic grader compares the saved decisions with an answer key. A run passes only if
every graded decision is right.

**Target difficulty:** Claude Opus 5 should pass **2–7 of 10** attempts. Every failure should be a genuine reasoning or reading error, not a task or grader defect.

| Task | What the agent does | README |
|---|---|---|
| **Task 3: cohort audit with calibrated abstention** | Audits the syphilis care of 200 synthetic patients against the CDC 2021 guidelines. It must abstain with a stated reason exactly where the records leave a fact unresolved, and carry facts across issues and across patients' charts | [`chartr_task3/README.md`](chartr_task3/README.md) |
| **Task 4: cardiology population review with raw ECGs** | Reviews a 100-patient population built on real MIMIC-IV data for anticoagulation, QT-safety, follow-up and documentation issues, and interprets each living patient's latest raw 12-lead ECG | [`chartr_task4/README.md`](chartr_task4/README.md) |

## Contents

- [Final results](#final-results)
- [Repository layout](#repository-layout)
  - [Inside each task](#inside-each-task)
- [Running](#running)
- [Licensing and citations](#licensing-and-citations)
- [Discussion](#discussion)

## Final results

Each task was confirmed with one ten-attempt batch of `claude-opus-5`. The protocol for each batch was predeclared and
committed before it ran: frozen files, exact command, budgets and counting rules.

| Task | Version | Passes | Main failure modes | Triage |
|---|---|---|---|---|
| Task 3 | 0.3.1 | **5/10** | Unresolved specimen identity or a misfiled result not carried into the dependent follow-up decision | [triage](results/confirm-task3-0.3.1-20260928T232731Z/TRIAGE.md) |
| Task 4 | 0.4.2 | **3/10** | Hidden AF missed (4 runs); QTc and rate measurement errors (4); non-AF records cited as AF evidence (2) | [triage](results/confirm-task4-0.4.2-20260929T050729Z/TRIAGE.md) |

- **Validity.** All 20 attempts were valid: no reruns, no budget failures, and every trial's provenance matched its frozen
  commit. No failure was a task or grader defect.
- **Task 4 history.** Its previous version, 0.4.1, scored
  [1/10](results/confirm-task4-0.4.1-20260928T235846Z/TRIAGE.md). That stands as that version's result. 0.4.2 is an
  announced calibration, described in the Task 4 README.
- **Full logs.** Trial logs and agent trajectories for every pilot and confirmation batch are on the `task3-pilot-results`
  and `task4-pilot-results` branches.

## Repository layout

```text
.
├── chartr_task3/              Task 3 (Harbor task directory)
├── chartr_task4/              Task 4 (Harbor task directory)
├── anthropic_agent.py         Agent adapter: Claude via the Anthropic Messages API with one bash tool
├── chartr_environment.py      Harbor environment provider: builds and runs the task containers
├── chartr_job.yaml            Harbor job configuration
├── requirements.txt           Direct dependency pins (Harbor 0.23.0, anthropic 1.8.0, jsonschema)
├── requirements.lock.txt      Exact pins of the working environment
├── qa/                        Private tooling, never copied into a task image
│   ├── build_task3.py, task3_*.py     Task 3 cohort generator, rules engine, review packets, preflight
│   ├── build_task4.py, task4_*.py     Task 4 overlay builder, ECG catalog and labelling, answer key, preflight
│   ├── test_task3.py, test_task4.py   Test suites: reference passes, wrong algorithms fail, leakage and integrity checks
│   ├── test_adapter.py, test_preflight.py
│   ├── confirm_summary.py              Scores a confirmation batch under its protocol
│   ├── agents.py, audit_task4_probe.py Free boundary probes (no model calls)
│   └── reviews/                        Independent model reviews of Task 3 charts
├── results/                   Triage and score summaries of the three confirmation batches
├── docs/                      Design principles, independent audits, release validation, build history
└── archive/                   Earlier task prototypes and probes (not part of the final tasks)
```

### Inside each task

Both tasks follow Harbor's task layout. Everything under `environment/public/` is what the agent sees; `tests/` and
`solution/` never enter the agent's container.

```text
chartr_task3/                            chartr_task4/
├── task.toml        name, version, resources    ├── task.toml
├── instruction.md   the prompt (80 words)       ├── instruction.md          (81 words)
├── environment/                                 ├── environment/
│   ├── docker-compose.yaml  main + clinic,      │   ├── docker-compose.yaml
│   │                        internal network    │   ├── agent-requirements.txt  pinned numpy/scipy/wfdb/neurokit2
│   ├── Dockerfile           agent container     │   ├── Dockerfile
│   ├── public/  clinic.py, policy.md, tools.md  │   ├── public/  clinic.py, policy.md, tools.md
│   └── service/ record service                  │   └── service/ record service
│       ├── server.py, store.py, control.py      │       ├── server.py, store.py, control.py
│       ├── fhir.py, schema/  FHIR R4 checks     │       ├── fetch.py      pinned PhysioNet download
│       └── fixture.json      the 200-patient    │       ├── assemble.py   builds the database
│                             cohort             │       └── overlay/      re-dating, synthetic records,
├── tests/                                       │                         ECG catalog and edits, hashes
│   ├── grade.py        deterministic grader     ├── tests/
│   ├── expected.json   answer key               │   ├── grade.py, expected.json
│   ├── baseline.json   source digest            │   └── baseline.json, test.sh, Dockerfile
│   └── test.sh, Dockerfile, docker-compose.yaml └── solution/
└── solution/                                        └── reference.py, readings.json, solve.sh
    └── reference.py, answers.json, solve.sh
```

**How a trial runs.**
1. Harbor starts two containers on an internal network: the agent's `main` container and a read-only `clinic` record
   service.
2. The agent works through the `clinic` CLI.
3. At the end, a separate verifier collects a controller-attested snapshot of the saved items.
4. `tests/grade.py` scores the snapshot against `tests/expected.json`.

**Evaluated files and frozen paths.** The evaluated files are `chartr_task3/`, `chartr_task4/`, `anthropic_agent.py`,
`chartr_environment.py`, `chartr_job.yaml` and `requirements.lock.txt`. They must stay at these paths: each protocol's
frozen-file check diffs them against the frozen commit (`19edc3b` for Task 3, `98a881a` for Task 4).

## Running

**Setup.**
- Create a fresh virtual environment from `requirements.lock.txt` (Harbor 0.23.0, anthropic 1.8.0).
- Paid batches also need:
  - Docker with at least 10 CPUs and 8 GB;
  - an `.env` file with the Anthropic API key;
  - no other ChartR trial running.

**Offline checks** (no API key, no model calls):

```bash
.venv/bin/python -m unittest qa.test_task3 qa.test_task4 qa.test_preflight qa.test_adapter
```

**Reference and no-op runs** (Docker, free). The reference solution should score 1 and the no-op 0:

```bash
PYTHONPATH="$PWD" .venv/bin/harbor run -c chartr_job.yaml -p chartr_task4 -a oracle --job-name oracle --jobs-dir "$PWD/jobs/chartr"
PYTHONPATH="$PWD" .venv/bin/harbor run -c chartr_job.yaml -p chartr_task4 -a nop --job-name nop --jobs-dir "$PWD/jobs/chartr"
```

**A confirmation batch** (paid). Follow the "Final confirmation protocol" section of the task README exactly. In outline,
for Task 4:

```bash
python3 qa/task4_preflight.py 0.4.2          # every line must be ok
D="$PWD/jobs/chartr/confirm-task4-0.4.2-$(date -u +%Y%m%dT%H%M%SZ)"; mkdir -p "$D"
caffeinate -dims env PYTHONPATH="$PWD" .venv/bin/harbor run -c chartr_job.yaml -p chartr_task4 -a anthropic_agent:AnthropicAgent -m claude-opus-5 -k 10 -n 10 --ak max_turns=300 --ak max_tokens=64000 --ak api_timeout_sec=1800 --ak wall_timeout_sec=7000 --ak tool_timeout_sec=900 --ak prompt_cache=true --env-file .env --job-name batch --jobs-dir "$D"
python3 qa/confirm_summary.py chartr_task4 "$D"
```

Task 3 uses `qa/task3_preflight.py 0.3.1`, `-p chartr_task3`, `--ak max_turns=250`, and no `tool_timeout_sec` override.
Its README has the exact command.

**Rebuilding a task** (only to change it, which creates a new version):
- Task 3: `.venv/bin/python qa/build_task3.py`.
- Task 4: the ECG labelling scripts need numpy and neurokit2 in a separate venv. The steps are in the Task 4 build log.

## Licensing and citations

- **Task 4 data.** Task 4 uses open-access PhysioNet data under the **Open Data Commons Open Database License v1.0
  (ODbL)**:
  - MIMIC-IV Clinical Database Demo on FHIR v2.1.0;
  - MIMIC-IV-ECG Demo v0.1;
  - the MIMIC-IV-ECG v1.0 machine measurements, used only as one labelling reader and not shipped.

  The data is fetched at image build time and checksum-verified against pinned hashes. It is not redistributed in this
  repository. The derived database is re-dated, extended with synthetic records, shared under the ODbL, and not for
  clinical use. Full dataset and paper citations are in the
  [Task 4 README](chartr_task4/README.md#licensing-and-citations).
- **Task 3 data** is entirely synthetic, with no real patient data.
- **Clinical standards.** Task 3 uses the CDC *Sexually Transmitted Infections Treatment Guidelines, 2021*
  (MMWR Recomm Rep 2021;70(RR-4)). Task 4 uses the *2023 ACC/AHA/ACCP/HRS Guideline for the Diagnosis and Management of
  Atrial Fibrillation*. Both are cited in full in the task READMEs.
- **Third-party software.** The tasks use Harbor, the Anthropic Python SDK, NeuroKit2 and WFDB under their own licences.

## Discussion
**What surprised me?**
- Having to grapple with Claude Code/Codex struggling to balance my different requireemnts/preferences for the task creation (ie unambiguity vs. bare-bones instructions)
- How much I underestimated the reasoning capabilities of the model
- how easy AI was at scaling

**What you'd change**
- deep diving into specific grading schema to find what was really made "too easy" in the name of fairness
- diversifying reasoning for task failures

**What you'd do next with more time.**
- expert review of clinical metrics/data
- larger confirmation runs and more developed realistic EHR database
- testing with different models to see gaps in specific capabilities
- fine-tuned LLM-as-a-judge explanation judgements












